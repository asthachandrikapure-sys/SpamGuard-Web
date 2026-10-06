"""Persistence layer for SMS predictions and trained-model metrics."""

import json
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DATABASE_DIR = os.path.join(PROJECT_ROOT, "database")
DB_PATH = os.path.join(DATABASE_DIR, "spam_sms.db")
DB_DRIVER = os.getenv("SPAM_DB_DRIVER", "mysql").lower()
DB_NAME = os.getenv("MYSQL_DATABASE", "spam_sms_classifier")


def _mysql_connection(include_database=True):
    try:
        import mysql.connector
    except ImportError as exc:
        raise RuntimeError(
            "MySQL driver is unavailable. Install backend/requirements.txt and configure MySQL."
        ) from exc

    options = {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
    }
    if include_database:
        options["database"] = DB_NAME
    try:
        return mysql.connector.connect(**options)
    except mysql.connector.Error as exc:
        raise RuntimeError(f"MySQL database connection failed: {exc}") from exc


def get_connection():
    """Return a connection for the configured database backend."""
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


def _placeholders(sql):
    return sql.replace("?", "%s") if DB_DRIVER == "mysql" else sql


def initialize_database():
    """Create the application tables and seed trained model metrics."""
    if DB_DRIVER == "mysql":
        connection = _mysql_connection(include_database=False)
        cursor = connection.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        connection.commit()
        cursor.close()
        connection.close()

    conn = get_connection()
    cur = _cursor(conn)
    if DB_DRIVER == "mysql":
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sms_predictions (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                message TEXT NOT NULL,
                prediction VARCHAR(10) NOT NULL,
                confidence DOUBLE NOT NULL,
                risk_level VARCHAR(10) NOT NULL,
                model VARCHAR(255),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_sms_predictions_created_at (created_at),
                INDEX idx_sms_predictions_prediction (prediction)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS model_performance (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                model_name VARCHAR(255) NOT NULL UNIQUE,
                accuracy DOUBLE,
                precision_score DOUBLE,
                recall DOUBLE,
                f1_score DOUBLE,
                is_best TINYINT DEFAULT 0
            )
        """)
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sms_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                prediction TEXT NOT NULL,
                confidence REAL NOT NULL,
                risk_level TEXT NOT NULL,
                model TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS model_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL UNIQUE,
                accuracy REAL,
                precision REAL,
                recall REAL,
                f1_score REAL,
                is_best INTEGER DEFAULT 0
            )
        """)
    conn.commit()
    cur.close()
    conn.close()
    _seed_model_performance()
    return DB_NAME if DB_DRIVER == "mysql" else DB_PATH


def init_db():
    return initialize_database()


def _seed_model_performance():
    results_path = os.path.join(BASE_DIR, "model", "model_results.json")
    if not os.path.exists(results_path):
        return []
    try:
        with open(results_path, "r", encoding="utf-8") as file:
            results = json.load(file)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(results, list):
        return []
    for result in results:
        if isinstance(result, dict) and result.get("model_name"):
            save_model_performance(
                result["model_name"], result.get("accuracy"), result.get("precision"),
                result.get("recall"), result.get("f1_score"), int(bool(result.get("is_best")))
            )
    return results


def save_prediction(message, prediction, confidence, model="", risk_level=None):
    risk_level = risk_level or ("HIGH" if prediction == "spam" else "LOW")
    conn = get_connection()
    cur = _cursor(conn)
    cur.execute(_placeholders(
        "INSERT INTO sms_predictions (message, prediction, confidence, risk_level, model) VALUES (?, ?, ?, ?, ?)"
    ), (message, prediction, round(float(confidence), 4), risk_level, model))
    conn.commit()
    row_id = cur.lastrowid
    cur.close()
    conn.close()
    return row_id


def insert_prediction(message, prediction, confidence, model="", risk_level=None):
    return save_prediction(message, prediction, confidence, model, risk_level)


def get_prediction_history(limit=500):
    conn = get_connection()
    cur = _cursor(conn)
    cur.execute(_placeholders("SELECT * FROM sms_predictions ORDER BY id DESC LIMIT ?"), (limit,))
    rows = [dict(row) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


def get_all_predictions(limit=500):
    return get_prediction_history(limit)


def get_statistics():
    conn = get_connection()
    cur = _cursor(conn)
    cur.execute("SELECT COUNT(*) AS total FROM sms_predictions")
    total = int(cur.fetchone()["total"] or 0)
    cur.execute("SELECT COUNT(*) AS cnt FROM sms_predictions WHERE prediction = 'spam'")
    spam_count = int(cur.fetchone()["cnt"] or 0)
    cur.close()
    conn.close()
    ham_count = total - spam_count
    spam_pct = round(spam_count / total * 100, 2) if total else 0
    ham_pct = round(ham_count / total * 100, 2) if total else 0
    return {
        "total_messages": total, "spam_messages": spam_count, "ham_messages": ham_count,
        "spam_percentage": spam_pct, "ham_percentage": ham_pct,
        "total": total, "spam": spam_count, "ham": ham_count,
        "spam_percent": spam_pct, "ham_percent": ham_pct,
    }


def get_stats():
    return get_statistics()


def save_model_performance(model_name, accuracy, precision, recall, f1_score, is_best=0):
    conn = get_connection()
    cur = _cursor(conn)
    if DB_DRIVER == "mysql":
        query = """
            INSERT INTO model_performance (model_name, accuracy, precision_score, recall, f1_score, is_best)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE accuracy=VALUES(accuracy), precision_score=VALUES(precision_score),
                recall=VALUES(recall), f1_score=VALUES(f1_score), is_best=VALUES(is_best)
        """
        values = (model_name, accuracy, precision, recall, f1_score, is_best)
    else:
        query = """
            INSERT INTO model_performance (model_name, accuracy, precision, recall, f1_score, is_best)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(model_name) DO UPDATE SET accuracy=excluded.accuracy,
                precision=excluded.precision, recall=excluded.recall,
                f1_score=excluded.f1_score, is_best=excluded.is_best
        """
        values = (model_name, accuracy, precision, recall, f1_score, is_best)
    cur.execute(query, values)
    conn.commit()
    cur.close()
    conn.close()
    return True


def get_model_performance():
    conn = get_connection()
    cur = _cursor(conn)
    if DB_DRIVER == "mysql":
        cur.execute("SELECT model_name, accuracy, precision_score AS precision, recall, f1_score, is_best FROM model_performance ORDER BY f1_score DESC")
    else:
        cur.execute("SELECT * FROM model_performance ORDER BY f1_score DESC")
    rows = [dict(row) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return rows