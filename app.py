import base64
from flask import send_from_directory
from report_generator import generate_pdf
from flask import send_file
from zipfile import ZipFile
from flask import Flask, request, render_template, jsonify, redirect, url_for
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
import tensorflow as tf
import numpy as np
import os
import sqlite3


from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image

from util import base64_to_pil
from grad_cam import generate_gradcam
from database import (
    init_db,
    get_doctor,
    add_doctor,
    save_prediction,
    get_history,
    get_all_doctors
)

from auth import User




DB_NAME = "predictions.db"

app = Flask(__name__)
app.secret_key = "supersecretappkey123"

# Login manager setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


# Load ML model
MODEL_PATH = "models/oldModel.h5"
model = load_model(MODEL_PATH)

print("🔥 Model Loaded Successfully.")


# ------------------------------
# ROUTES
# ------------------------------

@app.route("/")
@login_required
def index():
    return render_template("index.html")

@app.route('/uploads/<path:filename>')
def uploaded_files(filename):
    return send_from_directory('uploads', filename)

@app.route("/download-batch-report")
@login_required
def download_batch_report():
    zip_path = "uploads/batch_reports.zip"

    # Create ZIP file
    with ZipFile(zip_path, 'w') as zipf:
        conn = sqlite3.connect("predictions.db")
        c = conn.cursor()
        c.execute("SELECT image_path, heatmap_path FROM history WHERE user=?", (current_user.id,))
        rows = c.fetchall()
        conn.close()

        for i, (img, heat) in enumerate(rows):
            if os.path.exists(img):
                zipf.write(img, f"image_{i}.jpg")
            if os.path.exists(heat):
                zipf.write(heat, f"heatmap_{i}.jpg")

    return send_file(zip_path, as_attachment=True)

@app.route("/restore-admin")
def restore_admin():
    conn = sqlite3.connect("predictions.db")
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO doctors (username, password, name, specialization, role)
        VALUES ('admin', 'admin', 'Super Admin', 'N/A', 'admin')
    """)

    conn.commit()
    conn.close()
    return "✔ Admin restored!"


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        rec = get_doctor(username)

        if rec and rec[1] == password:
            user = User(rec[0], rec[2])
            login_user(user)
            return redirect("/")
        else:
            return render_template("login.html", error="Invalid Credentials")
    return render_template("login.html")



@app.route("/download-report")
@login_required
def download_report():
    output_path = "uploads/report.pdf"

    # last prediction for this user
    history = get_history(current_user.id)
    if len(history) == 0:
        return "No report available"

    last = history[0]
    result, confidence, img_path, heatmap_path, _ = last

    generate_pdf(result, confidence, img_path, heatmap_path, output_path)

    return send_file(output_path, as_attachment=True)

@app.route("/delete-doctor/<int:doc_id>")
@login_required
def delete_doctor(doc_id):
    if current_user.role != "admin":
        return redirect("/")

    conn = sqlite3.connect("predictions.db")
    cur = conn.cursor()

    cur.execute("DELETE FROM doctors WHERE id=?", (doc_id,))
    conn.commit()
    conn.close()

    return redirect("/admin")



@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login")


# ------------------------------
# PREDICTION API
# ------------------------------

@app.route("/predict", methods=["POST"])
@login_required
def predict():
    data = request.get_json()
    base64_img = data.get("image")

    img = base64_to_pil(base64_img)
    img.save("uploads/temp.jpg")

    # Model prediction
    loaded = image.load_img("uploads/temp.jpg", target_size=(64, 64))
    x = image.img_to_array(loaded)
    x = np.expand_dims(x, axis=0)
    x = preprocess_input(x, mode='tf')

    preds = model.predict(x)
    conf_raw = float(preds[0][0])

    # Proper confidence logic
    if conf_raw > 0.5:
        result = "PNEUMONIA"
        confidence = round(conf_raw * 100, 2)
    else:
        result = "NORMAL"
        confidence = round((1 - conf_raw) * 100, 2)

    # Heatmap generation
    heatmap_path = generate_heatmap("uploads/temp.jpg")


    # SAVE TO DB
    save_prediction(
        current_user.id,
        result,
        f"{confidence}%",
        "uploads/temp.jpg",
        heatmap_path
    )

    return jsonify({
        "result": result,
        "confidence": f"{confidence}%"
    })


@app.route("/batch-predict", methods=["POST"])
@login_required
def batch_predict():
    data = request.get_json()
    images = data["images"]

    results = []

    os.makedirs("uploads/batch/", exist_ok=True)

    for idx, base64_img in enumerate(images):
        img = base64_to_pil(base64_img)

        img_path = f"uploads/batch/image_{idx}.jpg"
        heatmap_path = f"uploads/batch/heatmap_{idx}.jpg"

        img.save(img_path)

        # Preprocess
        loaded = tf.keras.preprocessing.image.load_img(img_path, target_size=(64, 64))
        x = tf.keras.preprocessing.image.img_to_array(loaded)
        x = np.expand_dims(x, axis=0)

        pred = model.predict(x)[0][0]

        if pred > 0.5:
            label = "PNEUMONIA"
            conf = pred * 100
        else:
            label = "NORMAL"
            conf = (1 - pred) * 100

        conf = f"{conf:.2f}%"

        # Heatmap with bounding box
        generate_gradcam(model, img_path, heatmap_path)

        # Save for dashboard
        save_prediction(current_user.id, label, conf, img_path, heatmap_path)

        # Return to frontend
        with open(heatmap_path, "rb") as f:
            heatmap_b64 = base64.b64encode(f.read()).decode()

        results.append({
            "result": label,
            "confidence": conf,
            "heatmap": heatmap_b64,
            "image": base64_img
        })

    return jsonify({"batch_results": results})

# ------------------------------
# DASHBOARD (HISTORY)
# ------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Get user-specific history if doctor, all history if admin
    if current_user.role == "admin":
        c.execute("SELECT result, confidence, image_path, heatmap_path, timestamp FROM history ORDER BY timestamp DESC")
    else:
        c.execute("SELECT result, confidence, image_path, heatmap_path, timestamp FROM history WHERE user=? ORDER BY timestamp DESC",
                  (current_user.id,))

    history = c.fetchall()

    # Count normal & pneumonia
    normals = sum(1 for row in history if row[0] == "NORMAL")
    pneu    = sum(1 for row in history if row[0] == "PNEUMONIA")

    # Accuracy (dummy approximation)
    total = len(history)

    if total > 0:
        healthy_percent = round((normals / total) * 100, 2)
    else:
        healthy_percent = 0
    # DAILY prediction chart
    if current_user.role == "admin":
        c.execute("SELECT date(timestamp), COUNT(*) FROM history GROUP BY date(timestamp)")
    else:
        c.execute("SELECT date(timestamp), COUNT(*) FROM history WHERE user=? GROUP BY date(timestamp)",
                  (current_user.id,))

    daily = c.fetchall()
    conn.close()

    daily_counts = {row[0]: row[1] for row in daily}

    return render_template(
        "dashboard.html",
        history=history,
        normals=normals,
        pneu=pneu,
        healthy_percent=healthy_percent,
        daily_counts=daily_counts
    )




@app.route("/register", methods=["GET", "POST"])
@login_required
def register():
    if current_user.role != "admin":
        return "Unauthorized"

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        name = request.form["name"]
        specialty = request.form["specialization"]

        add_doctor(username, password, name, specialty)

        return redirect("/admin")

    return render_template("register.html")


@app.route("/admin")
@login_required
def admin():
    if current_user.role != "admin":
        return "Unauthorized"

    doctors = get_all_doctors()
    return render_template("admin.html", doctors=doctors)


@app.route("/chart-data")
@login_required
def chart_data():
    # Only show full hospital analytics to ADMIN
    if current_user.role != "admin":
        user = current_user.id
        query = "SELECT result, confidence, timestamp FROM history WHERE user=?"
        params = (user,)
    else:
        query = "SELECT result, confidence, timestamp FROM history"
        params = ()

    conn = sqlite3.connect("predictions.db")
    c = conn.cursor()
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()

    # Prepare data
    total_normal = sum(1 for r in rows if r[0] == "NORMAL")
    total_pneumonia = sum(1 for r in rows if r[0] == "PNEUMONIA")

    # Line chart
    daily_counts = {}
    for r in rows:
        date = r[2].split(" ")[0]
        daily_counts[date] = daily_counts.get(date, 0) + 1

    line_labels = list(daily_counts.keys())
    line_values = list(daily_counts.values())

    # Confidence histogram
    conf_values = [float(r[1].replace("%", "")) for r in rows]
    conf_labels = ["0-20", "20-40", "40-60", "60-80", "80-100"]
    conf_bins = [0, 0, 0, 0, 0]

    for v in conf_values:
        if v <= 20: conf_bins[0] += 1
        elif v <= 40: conf_bins[1] += 1
        elif v <= 60: conf_bins[2] += 1
        elif v <= 80: conf_bins[3] += 1
        else: conf_bins[4] += 1

    return jsonify({
        "pie": {
            "labels": ["Normal", "Pneumonia"],
            "data": [total_normal, total_pneumonia]
        },
        "line": {
            "labels": line_labels,
            "data": line_values
        },
        "bar": {
            "labels": conf_labels,
            "data": conf_bins
        }
    })



# ------------------------------
# RUN SERVER
# ------------------------------

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5002)
