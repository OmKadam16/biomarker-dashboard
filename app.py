from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

NORMAL_RANGES = {
    "glucose":     {"min":70, "max": 100, "unit": "mg/dL"},
    "bmi":         {"min":18.5, "max": 24.9, "unit": ""},
    "bp":          {"min":90, "max": 120, "unit": "mmHg"},
    "cholesterol": {"min":0, "max": 200, "unit": "mg/dL"},     
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
    return jsonify({"results": results, "score": score})


if __name__ == "__main__":
    app.run(debug=True, port=8080)