from flask import Flask, render_template, request, jsonify
import sqlite3
import json
from datetime import datetime

app = Flask(__name__)

NORMAL_RANGES = {
    "glucose":     {"min":70, "max": 100, "unit": "mg/dL"},
    "bmi":         {"min":18.5, "max": 24.9, "unit": ""},
    "bp":          {"min":90, "max": 120, "unit": "mmHg"},
    "cholesterol": {"min":0, "max": 200, "unit": "mg/dL"},     
}

def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute(
        "CREATE TABLE IF NOT EXISTS analyses "
        "(id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "name TEXT, age INTEGER, gender TEXT, conditions TEXT, "
        "glucose REAL, bmi REAL, bp REAL, cholesterol REAL, "
        "score INTEGER, date TEXT)"
    )
    conn.commit()
    conn.close()

def get_status(value, min_val, max_val):
    if value < min_val or value > max_val:
        return "⚠️ Out of range"
    return "✅ Normal"

def calculate_score(results):
    total = 0
    for marker, info in results.items():
        value = info["value"]
        min_val = info["min"]
        max_val = info["max"]
        midpoint = (min_val + max_val) / 2
        range_size = (max_val - min_val) / 2

        if range_size == 0:
            marker_score = 100
        else:
            deviation = abs(value - midpoint) / range_size
            marker_score = max(0, 100 - (deviation * 50))

        total += marker_score

    return round(total / len(results))

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    results = {}

    for marker, ranges in NORMAL_RANGES.items():
        value = float(data.get(marker, 0))
        status = get_status(value, ranges["min"], ranges["max"])
        results[marker] = {
            "value": value,
            "status": status,
            "min": ranges["min"],
            "max": ranges["max"],
            "unit": ranges["unit"]
        }

    score = calculate_score(results)

    patient = data.get("patient", {})
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute('''
       INSERT INTO analyses (name, age, gender, conditions, glucose, bmi, bp, cholesterol, score, date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) 
    ''', (
        patient.get("name", ""),
        patient.get("age", 0),
        patient.get("gender", ""),
        patient.get("conditions", ""),
        float(data.get("glucose", 0)),
        float(data.get("bmi", 0)),
        float(data.get("bp", 0)),
        float(data.get("cholesterol", 0)),
        score,
        datetime.now().strftime("%b %d, %Y")
    ))
    conn.commit()
    conn.close()

    return jsonify({"results": results, "score": score})

@app.route("/history", methods=["GET"])
def history():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT name, age, gender, glucose, bmi, bp, cholesterol, score, date FROM analyses ORDER BY id DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()

    entries = []
    for row in rows:
        entries.append({
            "name": row[0],
            "age": row[1],
            "gender": row[2],
            "glucose": row[3],
            "bmi": row[4],
            "bp": row[5],
            "cholesterol": row[6],
            "score": row[7],
            "date": row[8]
        })
    return jsonify(entries)

init_db()

if __name__ == "__main__":
    app.run(debug=True, port=8080)