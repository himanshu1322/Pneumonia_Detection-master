import sqlite3
import os

DB_NAME = "predictions.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Prediction history table
    c.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT,
            result TEXT,
            confidence TEXT,
            image_path TEXT,
            heatmap_path TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Doctors table
    c.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            name TEXT,
            specialization TEXT,
            role TEXT DEFAULT 'doctor'
        )
    """)

    # Create default admin if not exists
    c.execute("""
        INSERT OR IGNORE INTO doctors (username, password, name, specialization, role)
        VALUES ('admin', 'admin123', 'Administrator', 'System Admin', 'admin')
    """)

    conn.commit()
    conn.close()


def save_prediction(user, result, confidence, img_path, heatmap_path):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO history (user, result, confidence, image_path, heatmap_path)
        VALUES (?, ?, ?, ?, ?)
    """, (user, result, confidence, img_path, heatmap_path))
    conn.commit()
    conn.close()



def get_history(user):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT result, confidence, image_path, heatmap_path, timestamp
        FROM history WHERE user=? ORDER BY timestamp DESC
    """, (user,))
    rows = c.fetchall()
    conn.close()
    return rows


def get_all_doctors():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, username, name, specialization, role FROM doctors")
    rows = c.fetchall()
    conn.close()
    return rows


def add_doctor(username, password, name, specialization):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO doctors (username, password, name, specialization, role)
        VALUES (?, ?, ?, ?, 'doctor')
    """, (username, password, name, specialization))
    conn.commit()
    conn.close()


def get_doctor(username):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT username, password, role FROM doctors WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    return row
