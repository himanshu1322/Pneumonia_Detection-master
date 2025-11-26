from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import datetime
from reportlab.lib.utils import ImageReader


def generate_pdf(result, confidence, image_path, heatmap_path, output_path):
    c = canvas.Canvas(output_path, pagesize=letter)

    # Title
    c.setFont("Helvetica-Bold", 20)
    c.drawString(50, 750, "PneumoAI – Medical Report")

    # Timestamp
    c.setFont("Helvetica", 12)
    c.drawString(50, 725, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Prediction Section
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 680, "Prediction Result:")

    c.setFont("Helvetica", 14)
    c.drawString(70, 655, f"Diagnosis: {result}")
    c.drawString(70, 635, f"Confidence: {confidence}")

    # Add input X-ray image
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 600, "Input Chest X-Ray:")

    try:
        c.drawImage(ImageReader(image_path), 50, 400, width=200, height=200)
    except:
        c.drawString(50, 400, "(Unable to load image)")

    # Add Grad-CAM heatmap
    c.setFont("Helvetica-Bold", 14)
    c.drawString(300, 600, "AI Heatmap Visualization:")

    try:
        c.drawImage(ImageReader(heatmap_path), 300, 400, width=200, height=200)
    except:
        c.drawString(300, 400, "(Unable to load heatmap)")

    # AI Suggestion
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 360, "AI Notes:")
    
    c.setFont("Helvetica", 12)
    if result == "PNEUMONIA":
        c.drawString(70, 335, "- Pneumonia detected. Immediate clinical evaluation recommended.")
        c.drawString(70, 315, "- Consider CBC test, Chest CT scan.")
    else:
        c.drawString(70, 335, "- No pneumonia detected.")
        c.drawString(70, 315, "- If symptoms persist, consult physician.")

    c.save()
