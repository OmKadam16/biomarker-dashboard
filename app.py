from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

NPRMAL_RANGES = {
    "glucose":     {"min":70, "max": 100, "unit": "mg/dL"},
    "bmi":         {"min":18.5, "max": 24.9, "unit": ""},
    "bp":          {"min":90, "max": 120, "unit": "mmHg"},
    "cholesterol": {"min":0, "max": 200, "unit": "mg/dL"},     
}

def get_status(value, min, max):
    if value < min or value > max:
        return "⚠️ Out of range"
    return "✅ Normal"

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    results = {}

    for marker, ranges in NPRMAL_RANGES.items():
        value = float(data.get(marker, 0))
        status = get_status(value, ranges["min"], ranges["max"])
        results[marker] = {
            "value": value,
            "status": status,
            "min": ranges["min"],
            "max": ranges["max"],
            "unit": ranges["unit"]
        }

    return jsonify(results)

if __name__ == "__main__":
    app.run(debug=True, port=8080)