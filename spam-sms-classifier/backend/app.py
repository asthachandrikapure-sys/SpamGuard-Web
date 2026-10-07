"""
app.py — SpamGuard Flask Backend
=================================
AI-powered SMS Security Platform

Endpoints:
    GET  /                         -> Landing / home page
    GET  /login                    -> Login page
    GET  /signup                   -> Signup page
    POST /api/auth/login           -> Authenticate user
    POST /api/auth/signup          -> Register user
    POST /api/auth/logout          -> Logout
    GET  /dashboard                -> Main dashboard (auth required)
    GET  /inbox                    -> SMS Inbox (auth required)
    GET  /protection               -> Live Protection (auth required)
    GET  /analytics                -> Analytics (auth required)
    GET  /devices                  -> Devices (auth required)
    GET  /settings                 -> Settings (auth required)
    POST /api/predict              -> Classify SMS
    GET  /api/history              -> SMS history
    GET  /api/stats                -> Statistics
    GET  /api/analytics            -> Analytics data
    GET  /api/protection-status    -> Device connection status
    POST /api/device/heartbeat     -> Device heartbeat
    GET  /api/model-performance    -> Model metrics
"""

import os
import sys
import re
import json
import hashlib
import secrets
import subprocess
from datetime import datetime

# ─────────────────────────────────────────────
# AUTO-FALLBACK: ensure 64-bit Python if 32-bit lacks packages
# ─────────────────────────────────────────────
def _check_and_reexec():
    try:
        import joblib, flask, flask_cors, sklearn
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

# ─────────────────────────────────────────────
# LOAD .env
# ─────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    # Manual .env loader (no python-dotenv needed)
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())

import joblib
import numpy as np
from flask import (
    Flask, request, jsonify, render_template, redirect,
    url_for, session, send_from_directory
)
from flask_cors import CORS

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import database as db

# ─────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
TEMPLATE_DIR = os.path.join(PROJECT_ROOT, "templates")
STATIC_DIR   = os.path.join(PROJECT_ROOT, "static")
MODEL_DIR    = os.path.join(BASE_DIR, "model")
MODEL_PATH   = os.path.join(MODEL_DIR, "spam_model.pkl")
VECTOR_PATH  = os.path.join(MODEL_DIR, "vectorizer.pkl")
RESULTS_PATH = os.path.join(MODEL_DIR, "model_results.json")

MAX_MSG_LEN = 1000

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "spamguard-dev-secret-change-in-prod")
CORS(app, resources={r"/api/*": {"origins": "*"}})


# ─────────────────────────────────────────────
# LOAD MODEL
# ─────────────────────────────────────────────
_model          = None
_vectorizer     = None
_model_name     = "Unknown"
_model_load_error = "Model is unavailable. Run: python backend/train_model.py"


def load_model():
    global _model, _vectorizer, _model_name, _model_load_error

    if not os.path.exists(MODEL_PATH):
        _model_load_error = "Model file not found. Run: python backend/train_model.py"
        return False, _model_load_error
    if not os.path.exists(VECTOR_PATH):
        _model_load_error = "Vectorizer file not found. Run: python backend/train_model.py"
        return False, _model_load_error

    try:
        _model      = joblib.load(MODEL_PATH)
        _vectorizer = joblib.load(VECTOR_PATH)

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
        _model_load_error = f"Error loading model: {e}"
        return False, _model_load_error


# ─────────────────────────────────────────────
# NLP PREPROCESSING
# ─────────────────────────────────────────────
def preprocess(text: str) -> str:
    text = str(text).lower()
    text = re.sub(r"http\S+|www\S+", " url ", text)
    text = re.sub(r"\d+", " num ", text)
    text = re.sub(r"[^a-z\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ─────────────────────────────────────────────
# AUTH HELPERS
# ─────────────────────────────────────────────
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{hashed}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, hashed = stored_hash.split(":", 1)
        return hashlib.sha256((salt + password).encode()).hexdigest() == hashed
    except Exception:
        return False


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    if "user_id" not in session:
        return None
    try:
        return db.get_user_by_id(session["user_id"])
    except Exception:
        return None


# ─────────────────────────────────────────────
# FRONTEND PAGE ROUTES
# ─────────────────────────────────────────────
@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard_page"))
    return render_template("index.html")


@app.route("/login")
def login_page():
    if "user_id" in session:
        return redirect(url_for("dashboard_page"))
    return render_template("login.html")


@app.route("/signup")
def signup_page():
    if "user_id" in session:
        return redirect(url_for("dashboard_page"))
    return render_template("signup.html")


@app.route("/forgot-password")
def forgot_password_page():
    if "user_id" in session:
        return redirect(url_for("dashboard_page"))
    return render_template("forgot_password.html")


@app.route("/dashboard")
@login_required
def dashboard_page():
    user = get_current_user()
    return render_template("dashboard.html", user=user)


@app.route("/inbox")
@login_required
def inbox_page():
    user = get_current_user()
    return render_template("inbox.html", user=user)


@app.route("/analytics")
@login_required
def analytics_page():
    user = get_current_user()
    return render_template("analytics.html", user=user)


@app.route("/protection")
@login_required
def protection_page():
    user = get_current_user()
    return render_template("protection.html", user=user)


@app.route("/devices")
@login_required
def devices_page():
    user = get_current_user()
    return render_template("devices.html", user=user)


@app.route("/settings")
@login_required
def settings_page():
    user = get_current_user()
    return render_template("settings.html", user=user)


# Legacy redirects for old routes
@app.route("/history")
def history_page():
    return redirect(url_for("inbox_page"))

@app.route("/performance")
def performance_page():
    return redirect(url_for("analytics_page"))

@app.route("/about")
def about_page():
    return redirect(url_for("home"))

@app.route("/classifier")
def classifier_page():
    return redirect(url_for("home"))


# ─────────────────────────────────────────────
# AUTH API ROUTES
# ─────────────────────────────────────────────
@app.route("/api/auth/signup", methods=["POST"])
@app.route("/api/auth/register", methods=["POST"])
def api_signup():
    data = request.get_json(silent=True) or {}
    name  = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    mobile_number = str(data.get("mobile_number") or data.get("phone") or "").strip()
    password = str(data.get("password", ""))
    confirm_password = str(data.get("confirm_password", ""))

    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are required."}), 400
    if len(name) < 2:
        return jsonify({"error": "Name must be at least 2 characters."}), 400
    if "@" not in email or "." not in email:
        return jsonify({"error": "Please enter a valid email address."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400
    if confirm_password and confirm_password != password:
        return jsonify({"error": "Passwords do not match."}), 400

    try:
        existing = db.get_user_by_email(email)
        if existing:
            return jsonify({"error": "An account with this email already exists."}), 409
        if mobile_number:
            existing_mob = db.get_user_by_mobile(mobile_number)
            if existing_mob:
                return jsonify({"error": "An account with this mobile number already exists."}), 409

        password_hash = hash_password(password)
        user_id = db.create_user(name, email, password_hash, mobile_number=mobile_number or None)
        session["user_id"] = user_id
        session["user_name"] = name
        session["user_email"] = email
        session["user_mobile"] = mobile_number
        return jsonify({"success": True, "message": "Account created successfully.", "redirect": "/dashboard"})
    except Exception as e:
        app.logger.error(f"Signup error: {e}")
        return jsonify({"error": "Database connection error. Please ensure MySQL is running."}), 503


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    identifier = str(data.get("identifier") or data.get("email") or data.get("mobile_number") or data.get("mobile") or "").strip().lower()
    password = str(data.get("password", ""))

    if not identifier or not password:
        return jsonify({"error": "Email or mobile number, and password are required."}), 400

    try:
        user = db.get_user_by_login(identifier)
        if not user or not verify_password(password, user.get("password_hash", "")):
            return jsonify({"error": "Invalid email/mobile number or password."}), 401

        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_email"] = user["email"]
        session["user_mobile"] = user.get("mobile_number", "")
        return jsonify({"success": True, "message": "Login successful.", "redirect": "/dashboard"})
    except Exception as e:
        app.logger.error(f"Login error: {e}")
        return jsonify({"error": "Database connection error. Please ensure MySQL is running."}), 503


@app.route("/api/auth/forgot-password", methods=["POST"])
@app.route("/api/auth/reset-password", methods=["POST"])
def api_forgot_password():
    data = request.get_json(silent=True) or {}
    identifier = str(data.get("identifier") or data.get("email") or data.get("mobile_number") or "").strip().lower()
    new_password = str(data.get("password") or data.get("new_password") or "")
    confirm_password = str(data.get("confirm_password") or "")

    if not identifier or not new_password:
        return jsonify({"error": "Email or mobile number, and new password are required."}), 400
    if len(new_password) < 6:
        return jsonify({"error": "New password must be at least 6 characters."}), 400
    if confirm_password and confirm_password != new_password:
        return jsonify({"error": "Passwords do not match."}), 400

    try:
        new_hash = hash_password(new_password)
        success = db.reset_user_password(identifier, new_hash)
        if not success:
            return jsonify({"error": "No account found with this email or mobile number."}), 404
        return jsonify({"success": True, "message": "Password reset successfully. You can now login.", "redirect": "/login"})
    except Exception as e:
        app.logger.error(f"Forgot password error: {e}")
        return jsonify({"error": f"Failed to reset password: {e}"}), 500


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"success": True, "redirect": "/login"})


@app.route("/api/auth/me", methods=["GET"])
def api_me():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated."}), 401
    return jsonify({
        "id": session.get("user_id"),
        "name": session.get("user_name"),
        "email": session.get("user_email"),
        "mobile_number": session.get("user_mobile"),
    })


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    user_id = session.get("user_id") or 1
    if request.method == "GET":
        try:
            return jsonify(db.get_user_settings(user_id))
        except Exception as e:
            app.logger.error(f"Get settings error: {e}")
            return jsonify(db.DEFAULT_SETTINGS)
    data = request.get_json(silent=True) or {}
    try:
        updated = db.save_user_settings(user_id, data)
        return jsonify({"success": True, "settings": updated})
    except Exception as e:
        app.logger.error(f"Save settings error: {e}")
        return jsonify({"error": "Failed to save settings."}), 500


@app.route("/api/account/update", methods=["POST"])
def api_account_update():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated."}), 401
    user_id = session["user_id"]
    data = request.get_json(silent=True) or {}
    action = data.get("action")
    if action == "profile":
        name = str(data.get("name", "")).strip()
        if not name or len(name) < 2:
            return jsonify({"error": "Name must be at least 2 characters."}), 400
        try:
            db.update_user_name(user_id, name)
            session["user_name"] = name
            return jsonify({"success": True, "message": "Profile updated."})
        except Exception as e:
            return jsonify({"error": f"Failed to update profile: {e}"}), 500
    elif action == "password":
        current_pw = str(data.get("current_password", ""))
        new_pw = str(data.get("new_password", ""))
        confirm_pw = str(data.get("confirm_password", ""))
        if not current_pw or not new_pw:
            return jsonify({"error": "Please provide current and new passwords."}), 400
        if len(new_pw) < 6:
            return jsonify({"error": "New password must be at least 6 characters."}), 400
        if new_pw != confirm_pw:
            return jsonify({"error": "New passwords do not match."}), 400
        try:
            conn = db.get_connection()
            cur = db._cursor(conn)
            cur.execute(db._ph("SELECT password_hash FROM users WHERE id = ?"), (user_id,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if not row or not verify_password(current_pw, row["password_hash"]):
                return jsonify({"error": "Current password is incorrect."}), 400
            new_hash = hash_password(new_pw)
            db.update_user_password(user_id, new_hash)
            return jsonify({"success": True, "message": "Password changed successfully."})
        except Exception as e:
            return jsonify({"error": f"Failed to update password: {e}"}), 500
    return jsonify({"error": "Unknown action."}), 400


@app.route("/api/sms/<int:sms_id>", methods=["GET"])
def api_get_sms(sms_id):
    user_id = session.get("user_id")
    try:
        sms = db.get_sms_by_id(sms_id, user_id=user_id)
        if not sms:
            return jsonify({"error": "SMS not found."}), 404
        return jsonify(sms)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sms/<int:sms_id>/read", methods=["POST"])
def api_mark_sms_read(sms_id):
    user_id = session.get("user_id")
    try:
        db.mark_sms_read(sms_id, user_id=user_id, is_read=1)
        return jsonify({"success": True, "is_read": 1})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sms/<int:sms_id>/unread", methods=["POST"])
def api_mark_sms_unread(sms_id):
    user_id = session.get("user_id")
    try:
        db.mark_sms_read(sms_id, user_id=user_id, is_read=0)
        return jsonify({"success": True, "is_read": 0})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sms/<int:sms_id>/important", methods=["POST"])
def api_mark_sms_important(sms_id):
    user_id = session.get("user_id")
    data = request.get_json(silent=True) or {}
    is_important = data.get("is_important")
    try:
        new_val = db.mark_sms_important(sms_id, user_id=user_id, is_important=is_important)
        return jsonify({"success": True, "is_important": new_val})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sms/<int:sms_id>/trash", methods=["POST"])
def api_trash_sms(sms_id):
    user_id = session.get("user_id")
    data = request.get_json(silent=True) or {}
    is_trashed = int(data.get("is_trashed", 1))
    try:
        db.trash_sms(sms_id, user_id=user_id, is_trashed=is_trashed)
        return jsonify({"success": True, "is_trashed": is_trashed})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sms/<int:sms_id>", methods=["DELETE"])
def api_delete_sms(sms_id):
    user_id = session.get("user_id")
    try:
        db.trash_sms(sms_id, user_id=user_id, is_trashed=1)
        return jsonify({"success": True, "message": "Moved to trash"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# DEVICES API ROUTES
# ─────────────────────────────────────────────
@app.route("/api/devices", methods=["GET"])
def api_devices():
    user_id = session.get("user_id") or 1
    try:
        devices = db.get_user_devices(user_id)
        return jsonify(devices)
    except Exception as e:
        app.logger.error(f"Get devices error: {e}")
        return jsonify({"error": "Failed to load devices."}), 500


@app.route("/api/devices/register", methods=["POST"])
def api_devices_register():
    user_id = session.get("user_id") or 1
    data = request.get_json(silent=True) or {}
    device_name = str(data.get("device_name", "Android Phone")).strip()
    mobile_number = str(data.get("mobile_number", "")).strip() or None
    device_token = str(data.get("device_token", "")).strip() or None

    try:
        dev = db.register_device(user_id, device_name, mobile_number, device_token)
        return jsonify({"success": True, "device": dev})
    except Exception as e:
        app.logger.error(f"Register device error: {e}")
        return jsonify({"error": f"Failed to register device: {e}"}), 500


@app.route("/api/devices/<int:device_id>", methods=["DELETE"])
def api_devices_delete(device_id):
    user_id = session.get("user_id") or 1
    try:
        db.delete_device(device_id, user_id)
        return jsonify({"success": True})
    except Exception as e:
        app.logger.error(f"Delete device error: {e}")
        return jsonify({"error": f"Failed to delete device: {e}"}), 500


# ─────────────────────────────────────────────
# SMS / CLASSIFICATION API ROUTES
# ─────────────────────────────────────────────
@app.route("/api/predict", methods=["POST"])
def predict():
    """Classify an SMS message and link to user/device."""
    if _model is None or _vectorizer is None:
        return jsonify({"error": _model_load_error}), 503

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Missing request data."}), 400

    message = data.get("message") or data.get("text")
    if message is None:
        return jsonify({"error": "Missing 'message' field in request body."}), 400

    message = str(message).strip()
    if not message:
        return jsonify({"error": "Please provide an SMS message."}), 400
    if len(message) > MAX_MSG_LEN:
        return jsonify({"error": f"Message too long (max {MAX_MSG_LEN} characters)."}), 400

    try:
        clean    = preprocess(message)
        features = _vectorizer.transform([clean])

        pred_int    = int(_model.predict(features)[0])
        prediction  = "spam" if pred_int == 1 else "ham"

        if not hasattr(_model, "predict_proba"):
            return jsonify({"error": "The trained model does not provide confidence probabilities."}), 503

        proba = _model.predict_proba(features)[0]
        confidence = float(proba[list(_model.classes_).index(pred_int)])
        risk_level = "HIGH" if prediction == "spam" else "LOW"

        # Resolve user_id and device_id
        user_id = session.get("user_id") or data.get("user_id")
        device_id = data.get("device_id")
        device_token = data.get("device_token")
        mobile_number = data.get("mobile_number") or data.get("mobile")

        if device_token:
            dev = db.find_device_by_token(device_token)
            if dev:
                device_id = dev["id"]
                if not user_id:
                    user_id = dev["user_id"]

        if not user_id and mobile_number:
            u = db.get_user_by_mobile(str(mobile_number).strip())
            if u:
                user_id = u["id"]
                if not device_id:
                    dev = db.find_device_by_mobile(str(mobile_number).strip())
                    if dev:
                        device_id = dev["id"]
        try:
            sender = data.get("sender")
            prediction_id = db.insert_prediction(
                message, prediction, confidence, _model_name, risk_level, sender,
                user_id=user_id, device_id=device_id
            )
            print(f"[SPAMGUARD BACKEND] Real SMS captured & classified: sender={sender} | prediction={prediction} ({round(confidence*100, 1)}%) | risk={risk_level} | user_id={user_id} | id={prediction_id}", flush=True)
        except Exception as e:
            app.logger.error(f"Prediction DB error: {e}")
            return jsonify({"error": "Database connection error. Check MySQL is running."}), 503

        return jsonify({
            "id":          prediction_id,
            "message":     db.privacy_safe_preview(message),
            "sender":      db.mask_sender(data.get("sender")),
            "prediction":  prediction,
            "confidence":  round(confidence, 4),
            "risk_level":  risk_level,
            "created_at":  datetime.now().astimezone().isoformat(timespec="seconds"),
            "model":       _model_name,
        })

    except Exception as e:
        app.logger.error(f"Prediction error: {e}")
        return jsonify({"error": "An error occurred during classification."}), 500


@app.route("/api/history", methods=["GET"])
def history():
    """Return classification history filtered by logged-in user."""
    try:
        user_id = session.get("user_id")
        filter_type = request.args.get("filter") or request.args.get("folder") or "all"
        search = request.args.get("search", "")
        limit = int(request.args.get("limit", 500))
        records = db.get_prediction_history(user_id=user_id, limit=limit, filter_type=filter_type, search=search)
        return jsonify(records)
    except Exception as e:
        app.logger.error(f"History error: {e}")
        return jsonify({"error": "Database connection error. History is unavailable until MySQL is reachable."}), 503


@app.route("/api/stats", methods=["GET"])
def stats():
    """Return aggregate classification statistics for logged-in user."""
    try:
        user_id = session.get("user_id")
        return jsonify(db.get_statistics(user_id=user_id))
    except Exception as e:
        app.logger.error(f"Stats error: {e}")
        return jsonify({"error": "Database connection error. Statistics are unavailable until MySQL is reachable."}), 503


@app.route("/api/analytics", methods=["GET"])
def analytics():
    try:
        user_id = session.get("user_id")
        return jsonify(db.get_analytics(user_id=user_id))
    except Exception as e:
        app.logger.error(f"Analytics error: {e}")
        return jsonify({"error": "Database connection error. Analytics are unavailable until MySQL is reachable."}), 503


@app.route("/api/protection-status", methods=["GET"])
def protection_status():
    try:
        user_id = session.get("user_id")
        status = db.get_phone_status(user_id=user_id)
        status["ml_active"] = _model is not None and _vectorizer is not None
        return jsonify(status)
    except Exception as e:
        app.logger.error(f"Protection status error: {e}")
        return jsonify({"error": "Database connection error. Protection status is unavailable."}), 503


@app.route("/api/device/heartbeat", methods=["POST"])
def device_heartbeat():
    data = request.get_json(silent=True) or {}
    monitoring = data.get("monitoring_active", True)
    if not isinstance(monitoring, bool):
        return jsonify({"error": "'monitoring_active' must be a boolean."}), 400
    identifier = data.get("device_token") or data.get("mobile_number") or "9503564504"
    try:
        db.update_device_heartbeat(identifier, monitoring)
        user_id = session.get("user_id")
        status = db.get_phone_status(user_id=user_id)
        status["ml_active"] = _model is not None and _vectorizer is not None
        return jsonify(status)
    except Exception as e:
        app.logger.error(f"Heartbeat error: {e}")
        return jsonify({"error": "Database connection error. Heartbeat could not be saved."}), 503


@app.route("/api/model-performance", methods=["GET"])
def model_performance():
    try:
        perf = db.get_model_performance()
        if not perf:
            return jsonify({"error": "No model performance data. Train the model first."}), 404
        return jsonify(perf)
    except Exception as e:
        app.logger.error(f"Model performance error: {e}")
        return jsonify({"error": "Database connection error. Model performance is unavailable."}), 503


# ─────────────────────────────────────────────
# INIT
# ─────────────────────────────────────────────
try:
    db.initialize_database()
except Exception as e:
    app.logger.warning(f"Database init warning: {e}")

load_model()


# ─────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 60)
    print("  SPAMGUARD — AI-Powered SMS Security Platform")
    print("=" * 60)
    print(f"[*] ML Model: {_model_name}")
    print(f"[*] Templates: {TEMPLATE_DIR}")
    print(f"[*] Static:    {STATIC_DIR}")
    print(f"[*] http://127.0.0.1:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)