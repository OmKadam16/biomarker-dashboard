from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import sqlite3
import bcrypt
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from flask import send_file
import io

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
        "CREATE TABLE IF NOT EXISTS profiles "
        "(id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "user_id INTEGER UNIQUE, name TEXT, birthdate TEXT, gender TEXT, conditions TEXT, "
        "FOREIGN KEY(user_id) REFERENCES users(id))"
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
        c.execute("SELECT id, email FROM users WHERE email = ?", (email,))
        row = c.fetchone()
        conn.close()
        user = User(row[0], row[1])
        login_user(user)
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

@app.route("/export-pdf", methods=["POST"])
@login_required
def export_pdf():
    data = request.get_json()
    patient = data.get("patient", {})
    results = data.get("results", {})
    score = data.get("score", 0)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle("title", fontSize=22, fontName="Helvetica-Bold", textColor=colors.HexColor("#1b4332"), spaceAfter=4)
    subtitle_style = ParagraphStyle("subtitle", fontSize=10, fontName="Helvetica", textColor=colors.HexColor("#888888"), spaceAfter=20)
    story.append(Paragraph("🧬 Biomarker Health Dashboard", title_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Clinical Health Marker Analysis Report", subtitle_style))
    story.append(Spacer(1, 10))

    # Patient Info
    info_style = ParagraphStyle("info", fontSize=11, fontName="Helvetica", textColor=colors.HexColor("#2d2d2d"), spaceAfter=6)
    header_style = ParagraphStyle("header", fontSize=10, fontName="Helvetica-Bold", textColor=colors.HexColor("#2d6a4f"), spaceAfter=8, spaceBefore=16)
    story.append(Paragraph("PATIENT INFORMATION", header_style))
    story.append(Paragraph(f"Name: {patient.get('name', '')}", info_style))
    story.append(Paragraph(f"Age: {patient.get('age', '')}  |  Gender: {patient.get('gender', '')}", info_style))
    if patient.get("conditions"):
        story.append(Paragraph(f"Known Conditions: {patient.get('conditions')}", info_style))
    story.append(Paragraph(f"Health Score: {score}/100", info_style))
    story.append(Spacer(1, 16))

    # Results Table
    story.append(Paragraph("ANALYSIS RESULTS", header_style))
    table_data = [["Marker", "Your Value", "Normal Range", "Status"]]
    labels = {"glucose": "Glucose", "bmi": "BMI", "bp": "Blood Pressure", "cholesterol": "Cholesterol"}
    for marker, info in results.items():
        status = "✓ Normal" if "Normal" in info["status"] else "✗ Out of Range"
        normal_range = f"{info['min']} – {info['max']} {info['unit']}"
        table_data.append([
            labels.get(marker, marker),
            f"{info['value']} {info['unit']}",
            normal_range,
            status
        ])

    table = Table(table_data, colWidths=[140, 120, 150, 120])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2d6a4f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
        ("TOPPADDING", (0, 0), (-1, 0), 10),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#faf7f2")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#faf7f2"), colors.white]),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 8),
        ("TOPPADDING", (0, 1), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e8e0d0")),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    story.append(table)
    story.append(Spacer(1, 20))

    # Footer
    footer_style = ParagraphStyle("footer", fontSize=8, fontName="Helvetica", textColor=colors.HexColor("#aaaaaa"))
    story.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y')} · Reference ranges based on standard clinical guidelines.", footer_style))

    doc.build(story)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="biomarker_report.pdf", mimetype="application/pdf")

@app.route("/get-profile")
@login_required
def get_profile():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT name, birthdate, gender, conditions FROM profiles WHERE user_id = ?", (current_user.id,))
    row = c.fetchone()
    conn.close()
    if row:
        # Calculate age from birthdate
        from datetime import date
        birthdate = datetime.strptime(row[1], "%Y-%m-%d").date()
        today = date.today()
        age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
        return jsonify({
            "found": True,
            "name": row[0],
            "birthdate": row[1],
            "age": age,
            "gender": row[2],
            "conditions": row[3]
        })
    return jsonify({"found": False})

@app.route("/save-profile", methods=["POST"])
@login_required
def save_profile():
    data = request.get_json()
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute(
        "INSERT INTO profiles (user_id, name, birthdate, gender, conditions) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET "
        "name=excluded.name, birthdate=excluded.birthdate, "
        "gender=excluded.gender, conditions=excluded.conditions",
        (
            current_user.id,
            data.get("name"),
            data.get("birthdate"),
            data.get("gender"),
            data.get("conditions", "")
        )
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})

init_db()

if __name__ == "__main__":
    app.run(debug=True, port=8080)