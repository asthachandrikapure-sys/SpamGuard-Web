"""Persistence layer for SpamGuard — SMS messages, users, devices, settings, model metrics.
Fully connected architecture with MySQL / SQLite support, user isolation, and Android companion linkage.
"""

import json
import os
import re
import sqlite3
import secrets
from datetime import datetime

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DATABASE_DIR = os.path.join(PROJECT_ROOT, "database")
DB_PATH      = os.path.join(DATABASE_DIR, "spam_sms.db")

# Load .env file from project root or backend directory
for env_path in [os.path.join(PROJECT_ROOT, ".env"), os.path.join(BASE_DIR, ".env")]:
    if os.path.exists(env_path):
        try:
            with open(env_path, encoding="utf-8") as _f:
                for _line in _f:
                    _line = _line.strip()
                    if _line and not _line.startswith("#") and "=" in _line:
                        _k, _, _v = _line.partition("=")
                        os.environ.setdefault(_k.strip(), _v.strip())
        except Exception:
            pass

DB_DRIVER    = os.getenv("SPAM_DB_DRIVER", "mysql").lower()
DB_NAME      = os.getenv("SPAM_DB_NAME") or os.getenv("MYSQL_DATABASE") or "spamguard_db"


# ─────────────────────────────────────────────
# CONNECTION HELPERS
# ─────────────────────────────────────────────
def _mysql_connection(include_database=True):
    try:
        import mysql.connector
    except ImportError as exc:
        raise RuntimeError(
            "MySQL driver unavailable. Install mysql-connector-python and configure MySQL."
        ) from exc

    options = {
        "host":     os.getenv("SPAM_DB_HOST") or os.getenv("MYSQL_HOST") or "127.0.0.1",
        "port":     int(os.getenv("SPAM_DB_PORT") or os.getenv("MYSQL_PORT") or "3306"),
        "user":     os.getenv("SPAM_DB_USER") or os.getenv("MYSQL_USER") or "root",
        "password": os.getenv("SPAM_DB_PASSWORD") or os.getenv("MYSQL_PASSWORD") or "root",
    }
    if include_database:
        options["database"] = DB_NAME
    try:
        return mysql.connector.connect(**options)
    except mysql.connector.Error as exc:
        raise RuntimeError(f"MySQL connection failed: {exc}") from exc


def get_connection():
    if DB_DRIVER == "sqlite":
        os.makedirs(DATABASE_DIR, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    if DB_DRIVER != "mysql":
        raise RuntimeError("SPAM_DB_DRIVER must be 'mysql' or 'sqlite'.")
    return _mysql_connection()


def _cursor(conn):
    if DB_DRIVER == "mysql":
        return conn.cursor(dictionary=True)
    return conn.cursor()


def _ph(sql):
    """Replace ? placeholders with %s for MySQL."""
    return sql.replace("?", "%s") if DB_DRIVER == "mysql" else sql


# ─────────────────────────────────────────────
# DATABASE INITIALIZATION & MIGRATIONS
# ─────────────────────────────────────────────
def initialize_database():
    """Create all application tables, run migrations, and seed test data."""
    if DB_DRIVER == "mysql":
        conn0 = _mysql_connection(include_database=False)
        cur0  = conn0.cursor()
        cur0.execute(
            f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        conn0.commit()
        cur0.close()
        conn0.close()

    conn = get_connection()
    cur  = _cursor(conn)

    if DB_DRIVER == "mysql":
        # 1. users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            BIGINT AUTO_INCREMENT PRIMARY KEY,
                name          VARCHAR(100) NOT NULL,
                email         VARCHAR(255) NOT NULL UNIQUE,
                mobile_number VARCHAR(20) NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_users_email (email),
                INDEX idx_users_mobile (mobile_number)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # Migration: ensure mobile_number exists
        cur.execute("SHOW COLUMNS FROM users LIKE 'mobile_number'")
        if not cur.fetchone():
            cur.execute("ALTER TABLE users ADD COLUMN mobile_number VARCHAR(20) NULL UNIQUE")

        # 2. devices table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id           BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id      BIGINT NOT NULL,
                device_name  VARCHAR(100) NOT NULL DEFAULT 'Android Phone',
                mobile_number VARCHAR(20) NULL,
                device_token VARCHAR(255) NOT NULL UNIQUE,
                status       VARCHAR(30) NOT NULL DEFAULT 'CONNECTED',
                last_seen    TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
                created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_devices_user (user_id),
                INDEX idx_devices_token (device_token)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        cur.execute("SHOW COLUMNS FROM devices LIKE 'mobile_number'")
        if not cur.fetchone():
            cur.execute("ALTER TABLE devices ADD COLUMN mobile_number VARCHAR(20) NULL")

        # 3. sms_messages table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sms_messages (
                id           BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id      BIGINT NOT NULL,
                device_id    BIGINT NULL,
                sender_number VARCHAR(64) NOT NULL DEFAULT 'Unknown sender',
                message      TEXT NOT NULL,
                prediction   VARCHAR(10) NOT NULL,
                confidence   DOUBLE NOT NULL,
                risk_level   VARCHAR(10) NOT NULL,
                is_read      TINYINT DEFAULT 0,
                is_important TINYINT DEFAULT 0,
                is_trashed   TINYINT DEFAULT 0,
                model        VARCHAR(255),
                created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_sms_msg_user (user_id),
                INDEX idx_sms_msg_device (device_id),
                INDEX idx_sms_msg_pred (prediction),
                INDEX idx_sms_msg_risk (risk_level),
                INDEX idx_sms_msg_read (is_read),
                INDEX idx_sms_msg_important (is_important),
                INDEX idx_sms_msg_trashed (is_trashed),
                INDEX idx_sms_msg_created (created_at)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # 4. sms_predictions (maintained for backward compatibility)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sms_predictions (
                id          BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id     BIGINT NULL,
                device_id   BIGINT NULL,
                sender      VARCHAR(64) NOT NULL DEFAULT 'Unknown sender',
                sender_number VARCHAR(64) NULL,
                message     TEXT NOT NULL,
                prediction  VARCHAR(10) NOT NULL,
                confidence  DOUBLE NOT NULL,
                risk_level  VARCHAR(10) NOT NULL,
                model       VARCHAR(255),
                is_read     TINYINT DEFAULT 0,
                is_important TINYINT DEFAULT 0,
                is_trashed  TINYINT DEFAULT 0,
                created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_sms_created_at (created_at),
                INDEX idx_sms_prediction (prediction),
                INDEX idx_sms_risk_level (risk_level)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        for col, col_def in [
            ("user_id", "BIGINT NULL"),
            ("device_id", "BIGINT NULL"),
            ("sender", "VARCHAR(64) NOT NULL DEFAULT 'Unknown sender'"),
            ("sender_number", "VARCHAR(64) NULL"),
            ("is_read", "TINYINT DEFAULT 0"),
            ("is_important", "TINYINT DEFAULT 0"),
            ("is_trashed", "TINYINT DEFAULT 0"),
        ]:
            cur.execute(f"SHOW COLUMNS FROM sms_predictions LIKE '{col}'")
            if not cur.fetchone():
                cur.execute(f"ALTER TABLE sms_predictions ADD COLUMN {col} {col_def}")

        # 5. settings table (and user_settings)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id                 BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id            BIGINT NOT NULL UNIQUE,
                sms_monitoring     TINYINT NOT NULL DEFAULT 1,
                ai_detection       TINYINT NOT NULL DEFAULT 1,
                high_risk_alerts   TINYINT NOT NULL DEFAULT 1,
                mask_phone_numbers TINYINT NOT NULL DEFAULT 1,
                hide_sms_content   TINYINT NOT NULL DEFAULT 0,
                created_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_settings_user (user_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id            BIGINT PRIMARY KEY,
                sms_monitoring     TINYINT NOT NULL DEFAULT 1,
                ai_detection       TINYINT NOT NULL DEFAULT 1,
                high_risk_alerts   TINYINT NOT NULL DEFAULT 1,
                mask_phone_numbers TINYINT NOT NULL DEFAULT 1,
                hide_sms_content   TINYINT NOT NULL DEFAULT 0,
                updated_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

        # 6. model_performance
        cur.execute("""
            CREATE TABLE IF NOT EXISTS model_performance (
                id             BIGINT AUTO_INCREMENT PRIMARY KEY,
                model_name     VARCHAR(255) NOT NULL UNIQUE,
                accuracy       DOUBLE,
                precision_score DOUBLE,
                recall         DOUBLE,
                f1_score       DOUBLE,
                is_best        TINYINT DEFAULT 0
            )
        """)

        # 7. phone_status (legacy compatibility)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS phone_status (
                id               TINYINT PRIMARY KEY,
                monitoring_active BOOLEAN NOT NULL DEFAULT 1,
                last_seen        TIMESTAMP NULL
            )
        """)

    else:  # SQLite fallback
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                email         TEXT NOT NULL UNIQUE,
                mobile_number TEXT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL,
                device_name  TEXT NOT NULL DEFAULT 'Android Phone',
                mobile_number TEXT NULL,
                device_token TEXT NOT NULL UNIQUE,
                status       TEXT NOT NULL DEFAULT 'CONNECTED',
                last_seen    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sms_messages (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL,
                device_id     INTEGER NULL,
                sender_number TEXT NOT NULL DEFAULT 'Unknown sender',
                message       TEXT NOT NULL,
                prediction    TEXT NOT NULL,
                confidence    REAL NOT NULL,
                risk_level    TEXT NOT NULL,
                is_read       INTEGER DEFAULT 0,
                is_important  INTEGER DEFAULT 0,
                is_trashed    INTEGER DEFAULT 0,
                model         TEXT,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sms_predictions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NULL,
                device_id    INTEGER NULL,
                sender       TEXT NOT NULL DEFAULT 'Unknown sender',
                sender_number TEXT NULL,
                message      TEXT NOT NULL,
                prediction   TEXT NOT NULL,
                confidence   REAL NOT NULL,
                risk_level   TEXT NOT NULL,
                model        TEXT,
                is_read      INTEGER DEFAULT 0,
                is_important INTEGER DEFAULT 0,
                is_trashed   INTEGER DEFAULT 0,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id            INTEGER NOT NULL UNIQUE,
                sms_monitoring     INTEGER NOT NULL DEFAULT 1,
                ai_detection       INTEGER NOT NULL DEFAULT 1,
                high_risk_alerts   INTEGER NOT NULL DEFAULT 1,
                mask_phone_numbers INTEGER NOT NULL DEFAULT 1,
                hide_sms_content   INTEGER NOT NULL DEFAULT 0,
                created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id            INTEGER PRIMARY KEY,
                sms_monitoring     INTEGER NOT NULL DEFAULT 1,
                ai_detection       INTEGER NOT NULL DEFAULT 1,
                high_risk_alerts   INTEGER NOT NULL DEFAULT 1,
                mask_phone_numbers INTEGER NOT NULL DEFAULT 1,
                hide_sms_content   INTEGER NOT NULL DEFAULT 0,
                updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS model_performance (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL UNIQUE,
                accuracy   REAL,
                precision  REAL,
                recall     REAL,
                f1_score   REAL,
                is_best    INTEGER DEFAULT 0
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS phone_status (
                id                INTEGER PRIMARY KEY CHECK (id = 1),
                monitoring_active INTEGER NOT NULL DEFAULT 1,
                last_seen         TIMESTAMP
            )
        """)

    conn.commit()
    cur.close()
    conn.close()

    _seed_model_performance()
    _seed_test_account()
    return DB_NAME if DB_DRIVER == "mysql" else DB_PATH


def init_db():
    return initialize_database()


# ─────────────────────────────────────────────
# SEEDING: TEST ACCOUNT & DEVICE
# ─────────────────────────────────────────────
def _seed_test_account():
    """Ensure test account (Astha / 9503564504) and paired Android device exist."""
    conn = get_connection()
    cur  = _cursor(conn)
    test_mobile = "9503564504"

    # Check by mobile number or email
    cur.execute(_ph("SELECT id, name, email, mobile_number FROM users WHERE mobile_number = ? OR email = ? LIMIT 1"),
                (test_mobile, "astha@spamguard.security"))
    user = cur.fetchone()

    # Valid pre-hashed Password123!
    default_hash = "64451896acef4eedd32e13a6aeaef338:9fad14c66a96e4f73e97f415532ec5831238ca4cb4b5ac41da634d34d6ece837"

    user_id = None
    if user:
        user_id = user["id"]
        # Ensure mobile_number and default password hash are set
        cur.execute(_ph("UPDATE users SET mobile_number = ?, password_hash = ? WHERE id = ?"), (test_mobile, default_hash, user_id))
        conn.commit()
    else:
        # Check if user with id 3 (Astha Chandrikapure) exists from previous run
        cur.execute(_ph("SELECT id FROM users WHERE email = ? LIMIT 1"), ("asthachandrikapure@gmail.com",))
        existing_astha = cur.fetchone()
        if existing_astha:
            user_id = existing_astha["id"]
            cur.execute(_ph("UPDATE users SET mobile_number = ?, password_hash = ? WHERE id = ?"), (test_mobile, default_hash, user_id))
            conn.commit()
        else:
            cur.execute(
                _ph("INSERT INTO users (name, email, mobile_number, password_hash) VALUES (?, ?, ?, ?)"),
                ("Astha Chandrikapure", "astha@spamguard.security", test_mobile, default_hash)
            )
            conn.commit()
            user_id = cur.lastrowid

    if user_id:
        # Ensure device exists for Astha
        cur.execute(_ph("SELECT id FROM devices WHERE user_id = ? LIMIT 1"), (user_id,))
        dev = cur.fetchone()
        if not dev:
            cur.execute(
                _ph("INSERT INTO devices (user_id, device_name, mobile_number, device_token, status, last_seen) "
                    "VALUES (?, ?, ?, ?, 'CONNECTED', CURRENT_TIMESTAMP)"),
                (user_id, "Astha's Android Phone", test_mobile, f"SPAMGUARD-DEV-{test_mobile}")
            )
            conn.commit()

        # Ensure settings exist
        cur.execute(_ph("SELECT id FROM settings WHERE user_id = ? LIMIT 1"), (user_id,))
        if not cur.fetchone():
            cur.execute(
                _ph("INSERT INTO settings (user_id, sms_monitoring, ai_detection, high_risk_alerts, mask_phone_numbers, hide_sms_content) "
                    "VALUES (?, 1, 1, 1, 1, 0)"),
                (user_id,)
            )
            conn.commit()

        # Ensure user_settings exists
        cur.execute(_ph("SELECT user_id FROM user_settings WHERE user_id = ? LIMIT 1"), (user_id,))
        if not cur.fetchone():
            cur.execute(
                _ph("INSERT INTO user_settings (user_id, sms_monitoring, ai_detection, high_risk_alerts, mask_phone_numbers, hide_sms_content) "
                    "VALUES (?, 1, 1, 1, 1, 0)"),
                (user_id,)
            )
            conn.commit()

    cur.close()
    conn.close()


def _seed_model_performance():
    results_path = os.path.join(BASE_DIR, "model", "model_results.json")
    if not os.path.exists(results_path):
        return []
    try:
        with open(results_path, encoding="utf-8") as f:
            results = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(results, list):
        return []
    for r in results:
        if isinstance(r, dict) and r.get("model_name"):
            save_model_performance(
                r["model_name"], r.get("accuracy"), r.get("precision"),
                r.get("recall"), r.get("f1_score"), int(bool(r.get("is_best")))
            )
    return results


# ─────────────────────────────────────────────
# PRIVACY HELPERS
# ─────────────────────────────────────────────
def privacy_safe_preview(message, max_length=160, mask_numbers=True, hide_content=False):
    """Redact phone numbers and OTPs according to privacy settings."""
    if hide_content:
        return "[SMS Content Hidden by Privacy Setting]"
    text = str(message or "")
    if mask_numbers:
        text = re.sub(r"(?<!\w)\+?\d[\d\s,().-]{5,}\d(?!\w)", "[masked number]", text)
        text = re.sub(r"(?<!\d)\d{4,}(?!\d)", "[masked number]", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_length:
        return text[: max_length - 1].rstrip() + "…"
    return text


def mask_sender(sender, mask=True):
    value = str(sender or "").strip()
    if not mask:
        return value or "Unknown sender"
    if re.fullmatch(r"\*{3}\d{2}", value):
        return value
    digits = re.sub(r"\D", "", value)
    if len(digits) < 5:
        return value if value and not digits else "Unknown sender"
    return f"***{digits[-2:]}"


# ─────────────────────────────────────────────
# USER MANAGEMENT (MULTI-USER & ISOLATION)
# ─────────────────────────────────────────────
def get_user_by_email(email: str):
    conn = get_connection()
    cur  = _cursor(conn)
    cur.execute(_ph("SELECT id, name, email, mobile_number, password_hash FROM users WHERE email = ? LIMIT 1"), (email,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def get_user_by_mobile(mobile_number: str):
    conn = get_connection()
    cur  = _cursor(conn)
    cur.execute(_ph("SELECT id, name, email, mobile_number, password_hash FROM users WHERE mobile_number = ? LIMIT 1"), (mobile_number,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def get_user_by_login(identifier: str):
    """Find user by either email or mobile number."""
    identifier = str(identifier or "").strip().lower()
    conn = get_connection()
    cur  = _cursor(conn)
    cur.execute(
        _ph("SELECT id, name, email, mobile_number, password_hash FROM users WHERE email = ? OR mobile_number = ? LIMIT 1"),
        (identifier, identifier)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: int):
    conn = get_connection()
    cur  = _cursor(conn)
    cur.execute(_ph("SELECT id, name, email, mobile_number FROM users WHERE id = ? LIMIT 1"), (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def create_user(name: str, email: str, password_hash: str = None, mobile_number: str = None, **kwargs) -> int:
    """Create user in MySQL/database.
    Supports:
      create_user(name, email, password_hash, mobile_number=None)
      create_user(name, email, mobile_number, password_hash)
    """
    if "arg3" in kwargs:
        password_hash = kwargs["arg3"]
    if "arg4" in kwargs:
        mobile_number = kwargs["arg4"]

    # If called positionally where 3rd arg was mobile_number and 4th was password_hash:
    if mobile_number and (":" in mobile_number or len(mobile_number) > 35) and (not password_hash or len(password_hash) < 30):
        password_hash, mobile_number = mobile_number, password_hash

    conn = get_connection()
    cur  = _cursor(conn)
    cur.execute(
        _ph("INSERT INTO users (name, email, mobile_number, password_hash) VALUES (?, ?, ?, ?)"),
        (name, email, mobile_number, password_hash)
    )
    conn.commit()
    user_id = cur.lastrowid

    # Auto-create paired Android device record
    phone_token_tag = mobile_number if mobile_number else secrets.token_hex(4)
    device_token = f"SPAMGUARD-DEV-{phone_token_tag}-{secrets.token_hex(4)}"
    first_name = name.split()[0] if name else "User"
    cur.execute(
        _ph("INSERT INTO devices (user_id, device_name, mobile_number, device_token, status, last_seen) "
            "VALUES (?, ?, ?, ?, 'CONNECTED', CURRENT_TIMESTAMP)"),
        (user_id, f"{first_name}'s Android Phone", mobile_number, device_token)
    )

    # Auto-create default settings
    cur.execute(
        _ph("INSERT INTO settings (user_id, sms_monitoring, ai_detection, high_risk_alerts, mask_phone_numbers, hide_sms_content) "
            "VALUES (?, 1, 1, 1, 1, 0)"),
        (user_id,)
    )
    cur.execute(
        _ph("INSERT INTO user_settings (user_id, sms_monitoring, ai_detection, high_risk_alerts, mask_phone_numbers, hide_sms_content) "
            "VALUES (?, 1, 1, 1, 1, 0)"),
        (user_id,)
    )

    conn.commit()
    cur.close()
    conn.close()
    return user_id


def reset_user_password(identifier: str, new_password_hash: str) -> bool:
    """Reset user password by email or mobile number."""
    identifier = str(identifier or "").strip().lower()
    conn = get_connection()
    cur  = _cursor(conn)
    cur.execute(
        _ph("SELECT id FROM users WHERE email = ? OR mobile_number = ? LIMIT 1"),
        (identifier, identifier)
    )
    user = cur.fetchone()
    if not user:
        cur.close()
        conn.close()
        return False

    cur.execute(_ph("UPDATE users SET password_hash = ? WHERE id = ?"), (new_password_hash, user["id"]))
    conn.commit()
    cur.close()
    conn.close()
    return True


# ─────────────────────────────────────────────
# SMS MESSAGES (PERSISTENCE & FLOW)
# ─────────────────────────────────────────────
def save_prediction(message, prediction, confidence, model="", risk_level=None, sender=None, user_id=None, device_id=None):
    """Save an SMS classification record linked to user and device."""
    risk_level    = risk_level or ("HIGH" if prediction == "spam" else "LOW")
    raw_message   = str(message or "")
    sender_number = str(sender or "Unknown sender")

    conn = get_connection()
    cur  = _cursor(conn)

    # Resolve user_id if not provided
    if user_id is None:
        cur.execute("SELECT id FROM users ORDER BY id ASC LIMIT 1")
        first_user = cur.fetchone()
        user_id = first_user["id"] if first_user else 1

    # Resolve device_id if not provided
    if device_id is None and user_id:
        cur.execute(_ph("SELECT id FROM devices WHERE user_id = ? ORDER BY id ASC LIMIT 1"), (user_id,))
        dev = cur.fetchone()
        device_id = dev["id"] if dev else None

    # Fetch privacy settings for display previews
    settings = get_user_settings(user_id)
    mask_nums = bool(settings.get("mask_phone_numbers", 1))
    hide_sms  = bool(settings.get("hide_sms_content", 0))

    safe_message = privacy_safe_preview(raw_message, mask_numbers=mask_nums, hide_content=hide_sms)
    safe_sender  = mask_sender(sender_number, mask=mask_nums)

    # 1. Insert into primary `sms_messages` table
    cur.execute(
        _ph("INSERT INTO sms_messages (user_id, device_id, sender_number, message, prediction, confidence, risk_level, model) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"),
        (user_id, device_id, safe_sender, safe_message, prediction, round(float(confidence), 4), risk_level, model)
    )
    conn.commit()
    msg_id = cur.lastrowid

    # 2. Keep `sms_predictions` table synchronized for legacy compatibility
    try:
        cur.execute(
            _ph("INSERT INTO sms_predictions (id, user_id, device_id, sender, sender_number, message, prediction, confidence, risk_level, model) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"),
            (msg_id, user_id, device_id, safe_sender, safe_sender, safe_message, prediction, round(float(confidence), 4), risk_level, model)
        )
        conn.commit()
    except Exception:
        pass

    # 3. Update device last_seen and phone status
    if device_id:
        cur.execute(_ph("UPDATE devices SET last_seen = CURRENT_TIMESTAMP, status = 'CONNECTED' WHERE id = ?"), (device_id,))
        conn.commit()

    cur.close()
    conn.close()
    return msg_id


def insert_prediction(message, prediction, confidence, model="", risk_level=None, sender=None, user_id=None, device_id=None):
    return save_prediction(message, prediction, confidence, model, risk_level, sender, user_id, device_id)


def get_prediction_history(user_id=None, limit=500, filter_type="all", search=""):
    """Query SMS history filtered by user_id and folder/category."""
    conn = get_connection()
    cur  = _cursor(conn)

    conditions = []
    params = []

    if user_id is not None:
        conditions.append("user_id = ?")
        params.append(user_id)

    filter_type = str(filter_type or "all").lower()

    if filter_type == "trash":
        conditions.append("is_trashed = 1")
    else:
        conditions.append("is_trashed = 0")
        if filter_type == "spam":
            conditions.append("prediction = 'spam'")
        elif filter_type in ("ham", "safe"):
            conditions.append("prediction = 'ham'")
        elif filter_type == "high_risk":
            conditions.append("risk_level = 'HIGH'")
        elif filter_type == "important":
            conditions.append("is_important = 1")

    if search:
        search_like = f"%{search}%"
        conditions.append("(message LIKE ? OR sender_number LIKE ?)")
        params.extend([search_like, search_like])

    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"SELECT * FROM sms_messages{where_clause} ORDER BY id DESC LIMIT ?"
    params.append(limit)

    cur.execute(_ph(query), tuple(params))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()

    for row in rows:
        row["sender"] = row.get("sender_number") or row.get("sender", "Unknown sender")
        if row.get("created_at") and hasattr(row["created_at"], "isoformat"):
            row["created_at"] = row["created_at"].isoformat()
    return rows


def get_all_predictions(user_id=None, limit=500, filter_type="all"):
    return get_prediction_history(user_id=user_id, limit=limit, filter_type=filter_type)


def get_statistics(user_id=None):
    """Aggregate statistics strictly filtered by user_id."""
    conn = get_connection()
    cur  = _cursor(conn)

    user_filter = " WHERE user_id = ? AND is_trashed = 0" if user_id is not None else " WHERE is_trashed = 0"
    params = (user_id,) if user_id is not None else ()

    cur.execute(_ph(f"SELECT COUNT(*) AS total FROM sms_messages{user_filter}"), params)
    total = int(cur.fetchone()["total"] or 0)

    cur.execute(_ph(f"SELECT COUNT(*) AS cnt FROM sms_messages{user_filter} AND prediction = 'spam'"), params)
    spam_count = int(cur.fetchone()["cnt"] or 0)

    cur.execute(_ph(f"SELECT COUNT(*) AS cnt FROM sms_messages{user_filter} AND risk_level = 'HIGH'"), params)
    high_risk = int(cur.fetchone()["cnt"] or 0)

    cur.execute(_ph(f"SELECT COUNT(*) AS cnt FROM sms_messages{user_filter} AND is_read = 0"), params)
    unread = int(cur.fetchone()["cnt"] or 0)

    cur.execute(_ph(f"SELECT COUNT(*) AS cnt FROM sms_messages{user_filter} AND is_important = 1"), params)
    important = int(cur.fetchone()["cnt"] or 0)

    trash_filter = " WHERE user_id = ? AND is_trashed = 1" if user_id is not None else " WHERE is_trashed = 1"
    cur.execute(_ph(f"SELECT COUNT(*) AS cnt FROM sms_messages{trash_filter}"), params)
    trashed = int(cur.fetchone()["cnt"] or 0)

    cur.close()
    conn.close()

    ham_count = total - spam_count
    spam_pct  = round((spam_count / total) * 100, 2) if total > 0 else 0.0

    return {
        "total_messages":     total,
        "spam_messages":      spam_count,
        "ham_messages":       ham_count,
        "high_risk_messages": high_risk,
        "unread_messages":    unread,
        "important_messages": important,
        "trashed_messages":   trashed,
        "spam_percentage":    spam_pct,
        "ham_percentage":     round(100.0 - spam_pct, 2) if total > 0 else 0.0,
        "total": total,
        "spam":  spam_count,
        "ham":   ham_count,
        "spam_percent": spam_pct,
    }


def get_stats(user_id=None):
    return get_statistics(user_id)


def get_sms_by_id(sms_id: int, user_id=None):
    conn = get_connection()
    cur  = _cursor(conn)
    if user_id is not None:
        cur.execute(_ph("SELECT * FROM sms_messages WHERE id = ? AND user_id = ? LIMIT 1"), (sms_id, user_id))
    else:
        cur.execute(_ph("SELECT * FROM sms_messages WHERE id = ? LIMIT 1"), (sms_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    res = dict(row)
    res["sender"] = res.get("sender_number") or res.get("sender", "Unknown sender")
    if res.get("created_at") and hasattr(res["created_at"], "isoformat"):
        res["created_at"] = res["created_at"].isoformat()
    return res


def mark_sms_read(sms_id: int, user_id=None, is_read=1):
    conn = get_connection()
    cur  = _cursor(conn)
    if user_id is not None:
        cur.execute(_ph("UPDATE sms_messages SET is_read = ? WHERE id = ? AND user_id = ?"), (is_read, sms_id, user_id))
        cur.execute(_ph("UPDATE sms_predictions SET is_read = ? WHERE id = ? AND user_id = ?"), (is_read, sms_id, user_id))
    else:
        cur.execute(_ph("UPDATE sms_messages SET is_read = ? WHERE id = ?"), (is_read, sms_id))
        cur.execute(_ph("UPDATE sms_predictions SET is_read = ? WHERE id = ?"), (is_read, sms_id))
    conn.commit()
    cur.close()
    conn.close()
    return True


def mark_sms_important(sms_id: int, user_id=None, is_important=None):
    conn = get_connection()
    cur  = _cursor(conn)
    if is_important is None:
        # Toggle
        if user_id is not None:
            cur.execute(_ph("SELECT is_important FROM sms_messages WHERE id = ? AND user_id = ?"), (sms_id, user_id))
        else:
            cur.execute(_ph("SELECT is_important FROM sms_messages WHERE id = ?"), (sms_id,))
        row = cur.fetchone()
        cur_val = int(row["is_important"] or 0) if row else 0
        new_val = 0 if cur_val == 1 else 1
    else:
        new_val = int(bool(is_important))

    if user_id is not None:
        cur.execute(_ph("UPDATE sms_messages SET is_important = ? WHERE id = ? AND user_id = ?"), (new_val, sms_id, user_id))
        cur.execute(_ph("UPDATE sms_predictions SET is_important = ? WHERE id = ? AND user_id = ?"), (new_val, sms_id, user_id))
    else:
        cur.execute(_ph("UPDATE sms_messages SET is_important = ? WHERE id = ?"), (new_val, sms_id))
        cur.execute(_ph("UPDATE sms_predictions SET is_important = ? WHERE id = ?"), (new_val, sms_id))
    conn.commit()
    cur.close()
    conn.close()
    return new_val


def trash_sms(sms_id: int, user_id=None, is_trashed=1):
    conn = get_connection()
    cur  = _cursor(conn)
    if user_id is not None:
        cur.execute(_ph("UPDATE sms_messages SET is_trashed = ? WHERE id = ? AND user_id = ?"), (is_trashed, sms_id, user_id))
        cur.execute(_ph("UPDATE sms_predictions SET is_trashed = ? WHERE id = ? AND user_id = ?"), (is_trashed, sms_id, user_id))
    else:
        cur.execute(_ph("UPDATE sms_messages SET is_trashed = ? WHERE id = ?"), (is_trashed, sms_id))
        cur.execute(_ph("UPDATE sms_predictions SET is_trashed = ? WHERE id = ?"), (is_trashed, sms_id))
    conn.commit()
    cur.close()
    conn.close()
    return True


# ─────────────────────────────────────────────
# DEVICES (ANDROID COMPANION & HEARTBEAT)
# ─────────────────────────────────────────────
def get_user_devices(user_id: int):
    """Retrieve all devices for a user with calculated connection status."""
    conn = get_connection()
    cur  = _cursor(conn)

    if DB_DRIVER == "mysql":
        cur.execute(_ph("""
            SELECT id, user_id, device_name, mobile_number, device_token, status, last_seen, created_at,
                   CASE WHEN last_seen >= CURRENT_TIMESTAMP - INTERVAL 20 MINUTE THEN 1 ELSE 0 END AS is_connected
            FROM devices WHERE user_id = ? ORDER BY id ASC
        """), (user_id,))
    else:
        cur.execute(_ph("""
            SELECT id, user_id, device_name, mobile_number, device_token, status, last_seen, created_at,
                   CASE WHEN last_seen >= datetime('now', '-20 minutes') THEN 1 ELSE 0 END AS is_connected
            FROM devices WHERE user_id = ? ORDER BY id ASC
        """), (user_id,))

    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()

    for r in rows:
        r["connected"] = bool(r.get("is_connected"))
        if r.get("last_seen") and hasattr(r["last_seen"], "isoformat"):
            r["last_seen"] = r["last_seen"].isoformat()
        if r.get("created_at") and hasattr(r["created_at"], "isoformat"):
            r["created_at"] = r["created_at"].isoformat()
    return rows


def register_device(user_id: int, device_name: str, mobile_number: str = None, device_token: str = None):
    """Register a new device for a user."""
    conn = get_connection()
    cur  = _cursor(conn)

    if not device_token:
        device_token = f"SPAMGUARD-DEV-{(mobile_number or 'AND').replace('+', '')}-{secrets.token_hex(4)}"

    cur.execute(
        _ph("INSERT INTO devices (user_id, device_name, mobile_number, device_token, status, last_seen) "
            "VALUES (?, ?, ?, ?, 'CONNECTED', CURRENT_TIMESTAMP)"),
        (user_id, device_name, mobile_number, device_token)
    )
    conn.commit()
    dev_id = cur.lastrowid
    cur.close()
    conn.close()
    return {
        "id": dev_id,
        "user_id": user_id,
        "device_name": device_name,
        "mobile_number": mobile_number,
        "device_token": device_token,
        "status": "CONNECTED",
        "connected": True,
    }


def find_device_by_token(token: str):
    conn = get_connection()
    cur  = _cursor(conn)
    cur.execute(_ph("SELECT * FROM devices WHERE device_token = ? LIMIT 1"), (token,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def find_device_by_mobile(mobile: str):
    conn = get_connection()
    cur  = _cursor(conn)
    cur.execute(_ph("SELECT * FROM devices WHERE mobile_number = ? ORDER BY id DESC LIMIT 1"), (mobile,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def update_device_heartbeat(identifier: str, monitoring_active: bool = True):
    """Update last_seen timestamp by device_token or mobile_number."""
    conn = get_connection()
    cur  = _cursor(conn)
    cur.execute(
        _ph("UPDATE devices SET last_seen = CURRENT_TIMESTAMP, status = 'CONNECTED' "
            "WHERE device_token = ? OR mobile_number = ?"),
        (identifier, identifier)
    )
    conn.commit()
    cur.close()
    conn.close()

    # Legacy phone_status sync
    update_phone_status(monitoring_active)
    return True


def delete_device(device_id: int, user_id: int):
    conn = get_connection()
    cur  = _cursor(conn)
    cur.execute(_ph("DELETE FROM devices WHERE id = ? AND user_id = ?"), (device_id, user_id))
    conn.commit()
    cur.close()
    conn.close()
    return True


def update_phone_status(monitoring_active: bool):
    """Legacy phone_status sync."""
    conn   = get_connection()
    cur    = _cursor(conn)
    active = int(bool(monitoring_active))

    if DB_DRIVER == "mysql":
        cur.execute(
            "INSERT INTO phone_status (id, monitoring_active, last_seen) "
            "VALUES (1, %s, CURRENT_TIMESTAMP) "
            "ON DUPLICATE KEY UPDATE monitoring_active=VALUES(monitoring_active), last_seen=CURRENT_TIMESTAMP",
            (active,),
        )
    else:
        cur.execute(
            "INSERT INTO phone_status (id, monitoring_active, last_seen) "
            "VALUES (1, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(id) DO UPDATE SET "
            "monitoring_active=excluded.monitoring_active, last_seen=CURRENT_TIMESTAMP",
            (active,),
        )
    conn.commit()
    cur.close()
    conn.close()


def get_phone_status(user_id=None):
    """Return device connection status (for user if provided, otherwise latest active device)."""
    conn = get_connection()
    cur  = _cursor(conn)

    if user_id:
        if DB_DRIVER == "mysql":
            cur.execute(_ph("""
                SELECT status, last_seen,
                    CASE WHEN last_seen >= CURRENT_TIMESTAMP - INTERVAL 20 MINUTE THEN 1 ELSE 0 END AS phone_connected
                FROM devices WHERE user_id = ? ORDER BY last_seen DESC LIMIT 1
            """), (user_id,))
        else:
            cur.execute(_ph("""
                SELECT status, last_seen,
                    CASE WHEN last_seen >= datetime('now', '-20 minutes') THEN 1 ELSE 0 END AS phone_connected
                FROM devices WHERE user_id = ? ORDER BY last_seen DESC LIMIT 1
            """), (user_id,))
    else:
        if DB_DRIVER == "mysql":
            cur.execute("""
                SELECT status, last_seen,
                    CASE WHEN last_seen >= CURRENT_TIMESTAMP - INTERVAL 20 MINUTE THEN 1 ELSE 0 END AS phone_connected
                FROM devices ORDER BY last_seen DESC LIMIT 1
            """)
        else:
            cur.execute("""
                SELECT status, last_seen,
                    CASE WHEN last_seen >= datetime('now', '-20 minutes') THEN 1 ELSE 0 END AS phone_connected
                FROM devices ORDER BY last_seen DESC LIMIT 1
            """)

    dev_row = cur.fetchone()
    cur.close()
    conn.close()

    # Get user settings
    settings = get_user_settings(user_id or 1)
    monitoring = bool(settings.get("sms_monitoring", 1))

    if not dev_row:
        return {"phone_connected": False, "monitoring_active": False, "protection_active": False, "last_seen": None}

    connected = bool(dev_row["phone_connected"])
    last_seen = dev_row["last_seen"]
    if last_seen is not None and hasattr(last_seen, "isoformat"):
        last_seen = last_seen.isoformat()

    return {
        "phone_connected":   connected,
        "monitoring_active": monitoring,
        "protection_active": connected and monitoring,
        "last_seen":         last_seen,
    }


# ─────────────────────────────────────────────
# ANALYTICS (REAL DATABASE RECORDS ONLY)
# ─────────────────────────────────────────────
def get_analytics(user_id=None, days=14):
    conn = get_connection()
    cur  = _cursor(conn)

    user_clause = " AND user_id = ?" if user_id is not None else ""
    params = [days, user_id] if user_id is not None else [days]

    if DB_DRIVER == "mysql":
        daily_sql = _ph(f"""
            SELECT DATE(created_at) AS day,
                COUNT(*) AS total,
                SUM(CASE WHEN prediction = 'spam' THEN 1 ELSE 0 END) AS spam,
                SUM(CASE WHEN prediction = 'ham'  THEN 1 ELSE 0 END) AS ham
            FROM sms_messages
            WHERE is_trashed = 0 AND created_at >= DATE_SUB(CURRENT_TIMESTAMP, INTERVAL ? DAY){user_clause}
            GROUP BY DATE(created_at)
            ORDER BY day ASC
            LIMIT 14
        """)
    else:
        daily_sql = _ph(f"""
            SELECT DATE(created_at) AS day,
                COUNT(*) AS total,
                SUM(CASE WHEN prediction = 'spam' THEN 1 ELSE 0 END) AS spam,
                SUM(CASE WHEN prediction = 'ham'  THEN 1 ELSE 0 END) AS ham
            FROM sms_messages
            WHERE is_trashed = 0 AND created_at >= datetime('now', '-' || ? || ' days'){user_clause}
            GROUP BY DATE(created_at)
            ORDER BY day ASC
            LIMIT 14
        """)

    cur.execute(daily_sql, tuple(params))
    daily = []
    for row in cur.fetchall():
        day = row["day"]
        daily.append({
            "day":   day.isoformat() if hasattr(day, "isoformat") else str(day),
            "total": int(row["total"] or 0),
            "spam":  int(row["spam"] or 0),
            "ham":   int(row["ham"] or 0),
        })

    # Risk levels
    risk_sql = "SELECT risk_level, COUNT(*) AS total FROM sms_messages WHERE is_trashed = 0"
    risk_params = ()
    if user_id is not None:
        risk_sql += " AND user_id = ?"
        risk_params = (user_id,)
    risk_sql += " GROUP BY risk_level"

    cur.execute(_ph(risk_sql), risk_params)
    risk_levels = {r["risk_level"]: int(r["total"] or 0) for r in cur.fetchall()}

    # Average confidence
    conf_sql = "SELECT AVG(confidence) AS avg_conf FROM sms_messages WHERE is_trashed = 0"
    if user_id is not None:
        conf_sql += " AND user_id = ?"
    cur.execute(_ph(conf_sql), risk_params)
    avg_conf = cur.fetchone()["avg_conf"] or 0.0

    cur.close()
    conn.close()

    return {
        "daily":              daily,
        "risk_levels":        risk_levels,
        "average_confidence": round(float(avg_conf), 4),
    }


# ─────────────────────────────────────────────
# MODEL PERFORMANCE
# ─────────────────────────────────────────────
def save_model_performance(model_name, accuracy, precision, recall, f1_score, is_best=0):
    conn = get_connection()
    cur  = _cursor(conn)

    if DB_DRIVER == "mysql":
        query = """
            INSERT INTO model_performance
                (model_name, accuracy, precision_score, recall, f1_score, is_best)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                accuracy=VALUES(accuracy),
                precision_score=VALUES(precision_score),
                recall=VALUES(recall),
                f1_score=VALUES(f1_score),
                is_best=VALUES(is_best)
        """
    else:
        query = """
            INSERT INTO model_performance
                (model_name, accuracy, precision, recall, f1_score, is_best)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(model_name) DO UPDATE SET
                accuracy=excluded.accuracy,
                precision=excluded.precision,
                recall=excluded.recall,
                f1_score=excluded.f1_score,
                is_best=excluded.is_best
        """

    cur.execute(query, (model_name, accuracy, precision, recall, f1_score, is_best))
    conn.commit()
    cur.close()
    conn.close()
    return True


def get_model_performance():
    conn = get_connection()
    cur  = _cursor(conn)

    if DB_DRIVER == "mysql":
        cur.execute(
            "SELECT model_name, accuracy, precision_score AS `precision`, "
            "recall, f1_score, is_best FROM model_performance ORDER BY f1_score DESC"
        )
    else:
        cur.execute("SELECT * FROM model_performance ORDER BY f1_score DESC")

    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


# ─────────────────────────────────────────────
# USER SETTINGS (PERSISTENCE IN MySQL)
# ─────────────────────────────────────────────
DEFAULT_SETTINGS = {
    "sms_monitoring":     1,
    "ai_detection":       1,
    "high_risk_alerts":   1,
    "mask_phone_numbers": 1,
    "hide_sms_content":   0,
}


def get_user_settings(user_id: int):
    conn = get_connection()
    cur  = _cursor(conn)
    cur.execute(_ph("SELECT sms_monitoring, ai_detection, high_risk_alerts, mask_phone_numbers, hide_sms_content FROM settings WHERE user_id = ? LIMIT 1"), (user_id,))
    row = cur.fetchone()
    if not row:
        cur.execute(_ph("SELECT sms_monitoring, ai_detection, high_risk_alerts, mask_phone_numbers, hide_sms_content FROM user_settings WHERE user_id = ? LIMIT 1"), (user_id,))
        row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return dict(DEFAULT_SETTINGS)
    return {
        "sms_monitoring":     int(row.get("sms_monitoring", 1)),
        "ai_detection":       int(row.get("ai_detection", 1)),
        "high_risk_alerts":   int(row.get("high_risk_alerts", 1)),
        "mask_phone_numbers": int(row.get("mask_phone_numbers", 1)),
        "hide_sms_content":   int(row.get("hide_sms_content", 0)),
    }


def save_user_settings(user_id: int, s: dict):
    sms_mon   = int(bool(s.get("sms_monitoring", 1)))
    ai_det    = int(bool(s.get("ai_detection", 1)))
    hr_alert  = int(bool(s.get("high_risk_alerts", 1)))
    mask_num  = int(bool(s.get("mask_phone_numbers", 1)))
    hide_sms  = int(bool(s.get("hide_sms_content", 0)))

    conn = get_connection()
    cur  = _cursor(conn)

    if DB_DRIVER == "mysql":
        query1 = """
            INSERT INTO settings
                (user_id, sms_monitoring, ai_detection, high_risk_alerts, mask_phone_numbers, hide_sms_content)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                sms_monitoring=VALUES(sms_monitoring),
                ai_detection=VALUES(ai_detection),
                high_risk_alerts=VALUES(high_risk_alerts),
                mask_phone_numbers=VALUES(mask_phone_numbers),
                hide_sms_content=VALUES(hide_sms_content)
        """
        query2 = """
            INSERT INTO user_settings
                (user_id, sms_monitoring, ai_detection, high_risk_alerts, mask_phone_numbers, hide_sms_content)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                sms_monitoring=VALUES(sms_monitoring),
                ai_detection=VALUES(ai_detection),
                high_risk_alerts=VALUES(high_risk_alerts),
                mask_phone_numbers=VALUES(mask_phone_numbers),
                hide_sms_content=VALUES(hide_sms_content)
        """
    else:
        query1 = """
            INSERT INTO settings
                (user_id, sms_monitoring, ai_detection, high_risk_alerts, mask_phone_numbers, hide_sms_content)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                sms_monitoring=excluded.sms_monitoring,
                ai_detection=excluded.ai_detection,
                high_risk_alerts=excluded.high_risk_alerts,
                mask_phone_numbers=excluded.mask_phone_numbers,
                hide_sms_content=excluded.hide_sms_content
        """
        query2 = """
            INSERT INTO user_settings
                (user_id, sms_monitoring, ai_detection, high_risk_alerts, mask_phone_numbers, hide_sms_content)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                sms_monitoring=excluded.sms_monitoring,
                ai_detection=excluded.ai_detection,
                high_risk_alerts=excluded.high_risk_alerts,
                mask_phone_numbers=excluded.mask_phone_numbers,
                hide_sms_content=excluded.hide_sms_content
        """

    cur.execute(query1, (user_id, sms_mon, ai_det, hr_alert, mask_num, hide_sms))
    cur.execute(query2, (user_id, sms_mon, ai_det, hr_alert, mask_num, hide_sms))
    conn.commit()
    cur.close()
    conn.close()
    return get_user_settings(user_id)


def update_user_name(user_id: int, name: str):
    conn = get_connection()
    cur  = _cursor(conn)
    cur.execute(_ph("UPDATE users SET name = ? WHERE id = ?"), (name, user_id))
    conn.commit()
    cur.close()
    conn.close()
    return True


def update_user_password(user_id: int, password_hash: str):
    conn = get_connection()
    cur  = _cursor(conn)
    cur.execute(_ph("UPDATE users SET password_hash = ? WHERE id = ?"), (password_hash, user_id))
    conn.commit()
    cur.close()
    conn.close()
    return True