"""
app.py - Flask REST API Backend
================================
Provides classification endpoints for the Spam SMS Classifier project.

Run:
    python app.py

Endpoints:
    GET  /                      -> API status
    POST /api/predict           -> Classify an SMS message
    GET  /api/history           -> Previous predictions from DB
    GET  /api/stats             -> Aggregate statistics
    GET  /api/model-performance -> Model evaluation metrics
"""

import os
import sys
import subprocess

# ---------------------------------------------
# AUTO-FALLBACK: ensure 64-bit Python if 32-bit lacks packages
# ---------------------------------------------
def _check_and_reexec():
    try:
        import joblib
        import flask
        import flask_cors
        import sklearn
        return
    except ImportError:
        pass

    if sys.platform == "win32":
        candidates = [
            ["py", "-V:3.13"],
            [os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python313\python.exe")],
            [r"C:\Users\Asus\AppData\Local\Programs\Python\Python313\python.exe"],
        ]
        for cmd in candidates:
            try:
                test = subprocess.run(cmd + ["-c", "import sklearn, flask"], capture_output=True)
                if test.returncode == 0:
                    ret = subprocess.run(cmd + [os.path.abspath(__file__)] + sys.argv[1:])
                    sys.exit(ret.returncode)
            except Exception:
                continue

_check_and_reexec()

import re
import json
import joblib
import numpy as np
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import database as db

# ---------------------------------------------
# APP SETUP
# ---------------------------------------------
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = BASE_DIR

FRONTEND_DIR = BASE_DIR
TEMPLATE_DIR = BASE_DIR
STATIC_DIR   = BASE_DIR
MODEL_DIR    = os.path.join(BASE_DIR, "model")
MODEL_PATH   = os.path.join(MODEL_DIR, "spam_model.pkl")
VECTOR_PATH  = os.path.join(MODEL_DIR, "vectorizer.pkl")
RESULTS_PATH = os.path.join(MODEL_DIR, "model_results.json")

MAX_MSG_LEN  = 1000  # character limit

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
CORS(app, resources={r"/*": {"origins": "*"}})

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# LOAD MODEL
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_model      = None
_vectorizer = None
_model_name = "Unknown"
_model_load_error = "Model is unavailable. Check the trained model and vectorizer files."


def load_model():
    global _model, _vectorizer, _model_name, _model_load_error

    if not os.path.exists(MODEL_PATH):
        _model_load_error = "Model file not found. Please run: python backend/train_model.py"
        return False, _model_load_error
    if not os.path.exists(VECTOR_PATH):
        _model_load_error = "Vectorizer file not found. Please run: python backend/train_model.py"
        return False, _model_load_error

    try:
        _model      = joblib.load(MODEL_PATH)
        _vectorizer = joblib.load(VECTOR_PATH)

        # Retrieve model name from results JSON
        if os.path.exists(RESULTS_PATH):
            with open(RESULTS_PATH) as f:
                results = json.load(f)
            for r in results:
                if r.get("is_best"):
                    _model_name = r["model_name"]
                    break

        _model_load_error = ""
        return True, "Model loaded successfully."
    except Exception as e:
        _model_load_error = f"Error loading model: {str(e)}"
        return False, _model_load_error


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# NLP PREPROCESSING  (mirrors train_model.py)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def preprocess(text: str) -> str:
    text = str(text).lower()
    text = re.sub(r"http\S+|www\S+", " url ", text)
    text = re.sub(r"\d+", " num ", text)
    text = re.sub(r"[^a-z\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# ROUTES: MULTI-PAGE FRONTEND
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/classifier")
def classifier_page():
    return render_template("classifier.html")


@app.route("/dashboard")
def dashboard_page():
    return render_template("dashboard.html")


@app.route("/history")
def history_page():
    return render_template("history.html")


@app.route("/performance")
def performance_page():
    return render_template("performance.html")


@app.route("/about")
def about_page():
    return render_template("about.html")


@app.route("/style.css")
def legacy_style():
    return send_from_directory(STATIC_DIR, "style.css")


@app.route("/script.js")
def legacy_script():
    return send_from_directory(STATIC_DIR, "script.js")


@app.route("/chart.umd.min.js")
def legacy_chart_script():
    return send_from_directory(STATIC_DIR, "chart.umd.min.js")


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# ROUTES: API
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.route("/api/predict", methods=["POST"])
def predict():
    """
    Classify an SMS message.
    Body: { "message": "..." }
    """
    # â”€â”€ Validate model is loaded â”€â”€
    if _model is None or _vectorizer is None:
        return jsonify({"error": _model_load_error}), 503

    # â”€â”€ Parse request â”€â”€
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Missing request data."}), 400

    message = data.get("message")
    if message is None:
        message = data.get("text")

    if message is None:
        return jsonify({"error": "Missing 'message' or 'text' field in request body."}), 400

    message = str(message).strip()
    if not message:
        return jsonify({"error": "Please enter an SMS message."}), 400
    if len(message) > MAX_MSG_LEN:
        return jsonify({"error": f"Message too long (max {MAX_MSG_LEN} characters)."}), 400

    try:
        # â”€â”€ Preprocess & vectorize â”€â”€
        clean    = preprocess(message)
        features = _vectorizer.transform([clean])

        # â”€â”€ Predict â”€â”€
        pred_int    = int(_model.predict(features)[0])
        prediction  = "spam" if pred_int == 1 else "ham"

        # â”€â”€ Confidence â”€â”€
        if not hasattr(_model, "predict_proba"):
            return jsonify({"error": "The trained model does not provide confidence probabilities."}), 503
        proba = _model.predict_proba(features)[0]
        confidence = float(proba[list(_model.classes_).index(pred_int)])
        risk_level = "HIGH" if prediction == "spam" else "LOW"

        # â”€â”€ Store in DB â”€â”€
        try:
            prediction_id = db.insert_prediction(message, prediction, confidence, _model_name, risk_level)
        except Exception as e:
            app.logger.error(f"Prediction database error: {e}")
            return jsonify({"error": "Database connection error. Check that MySQL is running and configured."}), 503

        return jsonify({
            "id":          prediction_id,
            "message":    message,
            "prediction": prediction,
            "confidence": round(confidence, 4),
            "risk_level": risk_level,
            "created_at":  datetime.now().astimezone().isoformat(timespec="seconds"),
            "model":      _model_name,
        })

    except Exception as e:
        app.logger.error(f"Prediction error: {e}")
        return jsonify({"error": "An error occurred during classification."}), 500


@app.route("/api/history", methods=["GET"])
def history():
    """Return classification history from the database."""
    try:
        records = db.get_all_predictions(limit=500)
        return jsonify(records)
    except Exception as e:
        app.logger.error(f"History error: {e}")
        return jsonify({"error": "Database connection error. History is unavailable until MySQL is reachable."}), 503


@app.route("/api/stats", methods=["GET"])
def stats():
    """Return aggregate classification statistics."""
    try:
        data = db.get_statistics()
        return jsonify(data)
    except Exception as e:
        app.logger.error(f"Stats error: {e}")
        return jsonify({"error": "Database connection error. Statistics are unavailable until MySQL is reachable."}), 503


@app.route("/api/model-performance", methods=["GET"])
def model_performance():
    """Return model evaluation metrics."""
    try:
        perf = db.get_model_performance()
        if not perf:
            return jsonify({"error": "No model performance data found. Train the model first."}), 404
        return jsonify(perf)
    except Exception as e:
        app.logger.error(f"Model performance error: {e}")
        return jsonify({"error": "Database connection error. Model performance is unavailable until MySQL is reachable."}), 503


# Initialize database & load model at import time
try:
    db.initialize_database()
except Exception as e:
    app.logger.warning(f"Database init warning: {e}")

load_model()


# ---------------------------------------------
# STARTUP
# ---------------------------------------------
if __name__ == "__main__":
    print("=" * 55)
    print("  SPAM SMS CLASSIFIER - FLASK BACKEND")
    print("=" * 55)
    print(f"[*] ML Model loaded: {_model_name}")
    print(f"[*] Serving frontend from: {FRONTEND_DIR}")
    print("[*] Starting Flask on http://127.0.0.1:5000\n")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=False)

