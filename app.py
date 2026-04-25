from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import sqlite3
import bcrypt
from datetime import datetime

app = Flask(__name__)
app.secret_key = "biomarker_secret_key_2026"

login_manager = LoginManager()
login_manager.init_app(app)



def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute(
        "CREATE TABLE IF NOT EXISTS users "
        "(id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "email TEXT UNIQUE, password TEXT)"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS analyses "
        "(id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "user_id INTEGER, name TEXT, age INTEGER, gender TEXT, conditions TEXT, "
        "glucose REAL, bmi REAL, bp REAL, cholesterol REAL, "
        "score INTEGER, date TEXT, "
        "FOREIGN KEY(user_id) REFERENCES users(id))"
    )
    conn.commit()
    conn.close()



class User(UserMixin):
    def __init__(self, id, email):
        self.id = id
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT id, email FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return User(row[0], row[1])
    return None



@app.route("/")
def index():
    if current_user.is_authenticated:
        return render_template("index.html", email=current_user.email)
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT id, email, password FROM users WHERE email = ?", (email,))
    row = c.fetchone()
    conn.close()
    if row and bcrypt.checkpw(password.encode(), row[2]):
        user = User(row[0], row[1])
        login_user(user)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Invalid email or password"})

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    try:
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, hashed))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "error": "Email already exists"})

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("login"))



NORMAL_RANGES = {
    "glucose":     {"min": 70,  "max": 100, "unit": "mg/dL"},
    "bmi":         {"min": 18.5,"max": 24.9, "unit": ""},
    "bp":          {"min": 90,  "max": 120, "unit": "mmHg"},
    "cholesterol": {"min": 0,   "max": 200, "unit": "mg/dL"},
}

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

@app.route("/analyze", methods=["POST"])
@login_required
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
    c.execute(
        "INSERT INTO analyses (user_id, name, age, gender, conditions, glucose, bmi, bp, cholesterol, score, date) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            current_user.id,
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
        )
    )
    conn.commit()
    conn.close()
    return jsonify({"results": results, "score": score})

@app.route("/history")
@login_required
def history():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute(
        "SELECT name, age, gender, glucose, bmi, bp, cholesterol, score, date "
        "FROM analyses WHERE user_id = ? ORDER BY id DESC LIMIT 10",
        (current_user.id,)
    )
    rows = c.fetchall()
    conn.close()
    entries = []
    for row in rows:
        entries.append({
            "name": row[0], "age": row[1], "gender": row[2],
            "glucose": row[3], "bmi": row[4], "bp": row[5],
            "cholesterol": row[6], "score": row[7], "date": row[8]
        })
    return jsonify(entries)

init_db()

if __name__ == "__main__":
    app.run(debug=True, port=8080)