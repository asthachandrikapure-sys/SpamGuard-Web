# SPAMGUARD

### Real-Time SMS Security

AI-powered security system that automatically protects incoming SMS messages with real-time machine learning detection.

---

## 1. Product Concept & Architecture

SPAMGUARD provides end-to-end automated protection for mobile SMS:

```
Android Phone
    ↓  (Incoming SMS detected)
SpamGuard Android Companion (Kotlin + Jetpack Compose)
    ↓  (Encrypted HTTPS POST /api/predict)
Flask Backend (Python 3.10+)
    ↓  (TF-IDF Vectorizer + Support Vector Machine)
Spam / Safe Classification + Confidence + Risk Level
    ↓  (Stored securely)
MySQL Database (spamguard_db)
    ↓  (Real-time live synchronization)
SpamGuard Web Security Platform
    ↓
SMS Inbox (🚨 Spam Panel · 🛡️ Safe SMS · Analytics · Live Protection)
```

The core user experience is **completely automatic**: no copy-pasting or manual checking is required. Incoming SMS messages are intercepted on the phone, evaluated by the AI model, cataloged in MySQL, and immediately reflected across the live dashboard and security inbox.

---

## 2. Key Features

- **Automated Mobile Protection**: Android companion app requests `RECEIVE_SMS` permission, detects incoming messages in real-time, and sends them to the Flask backend via WorkManager.
- **AI Classification**: TF-IDF Vectorizer + Support Vector Machine (SVM) model pre-trained on SMS datasets with 99%+ accuracy and confidence probability scoring.
- **Gmail-like Security Inbox**:
  - `📥 All SMS` folder with unread badges and live counts.
  - `🚨 Spam SMS` dedicated panel showing summary breakdown (Total, High Risk, Medium, Low).
  - `🛡️ Safe SMS` folder for verified legitimate communications.
  - `⚠️ High Risk` threat filter.
  - Real-time search across senders and message content.
  - Detailed inspection view showing full AI confidence metrics, classification, risk level, and timestamp.
- **Live Protection Dashboard**:
  - Real-time protection status indicator (`PROTECTION ACTIVE` / `WAITING FOR DEVICE`).
  - Metric cards: SMS Scanned, Spam Detected, Safe Messages, High Risk.
  - Spam vs Safe distribution doughnut chart.
  - Live activity feed showing newly intercepted messages.
- **Analytics & Trends**:
  - Interactive Chart.js visualizations for 14-day daily detections, risk levels, and average confidence gauge.
- **Security & Privacy Settings**:
  - Toggle controls for SMS Monitoring, AI Detection, and High Risk Alerts.
  - Data confidentiality options: Mask Phone Numbers (`+91 ******45`), Hide SMS Content.
  - Connected device status monitoring.
  - Account profile management and secure password change.
- **Enterprise-Grade Authentication**:
  - Secure signup and login with salted SHA-256 password hashing.
  - Session-based authorization protecting all dashboard routes.
- **Multi-Database Support**:
  - First-class MySQL integration (`mysql-connector-python`).
  - Seamless zero-config fallback to SQLite if MySQL is unavailable.

---

## 3. Technology Stack

- **Frontend**: HTML5, Vanilla CSS3 (Dark Glassmorphism SaaS Theme, Inter & Outfit Typography), JavaScript (ES6+), Chart.js
- **Backend**: Python 3.10+, Flask, Flask-CORS, Gunicorn
- **Machine Learning**: Scikit-Learn, Pandas, NumPy, TF-IDF, Joblib
- **Database**: MySQL Server 8.0+ (`spamguard_db`), SQLite fallback
- **Android**: Kotlin, Jetpack Compose, Retrofit 2, OkHttp 3, AndroidX WorkManager, Coroutines

---

## 4. Local Development Setup

### Prerequisites

1. **Python 3.10+ (64-bit)**
2. **MySQL Server 8.0+** running locally (or SQLite fallback)
3. **Android Studio** (optional, for companion app deployment)

### 1. Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Default local `.env` configuration:

```ini
SPAM_DB_DRIVER=mysql
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=root
MYSQL_DATABASE=spamguard_db
FLASK_SECRET_KEY=spamguard-secret-key-2026
PORT=5000
```

> **Note:** If MySQL is not installed locally, set `SPAM_DB_DRIVER=sqlite` in `.env` for instant local development without configuring a database server.

### 2. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Run the Platform

**On Windows (Double-click or run):**

```bat
run_app.bat
```

Or from terminal:

```bash
python backend/app.py
```

### 4. Open in Browser

Open your browser to:

```
http://127.0.0.1:5000
```

---

## 5. Running Tests

Execute the comprehensive platform test suite:

```bash
python backend/test_full_platform.py
```

This verifies:
1. MySQL database connection & automatic table schema creation.
2. Machine learning model loading (SVM + TF-IDF).
3. Public pages rendering (`/`, `/login`, `/signup`).
4. Static CSS & JS asset availability.
5. User authentication flow (signup, duplicate rejection, session tracking, logout, login).
6. Protected pages (`/dashboard`, `/inbox`, `/protection`, `/analytics`, `/devices`, `/settings`).
7. AI SMS prediction & risk scoring with privacy masking.
8. History filtering, message read status, and message detail retrieval.
9. Aggregate statistics, analytics metrics, and model performance.
10. User preferences & password update APIs.
11. Device heartbeat registration and live status polling.

---

## 6. Android Companion App Setup

The native Android app source code is located in `android/`:

1. Open Android Studio and select **Open** → Choose `spam-sms-classifier/android`.
2. In `android/app/build.gradle.kts`, set `API_BASE_URL` to your backend host (e.g. `http://10.0.2.2:5000/` for Android Emulator, or your public Render URL).
3. Connect your Android phone or start an Android Emulator.
4. Click **Run 'app'**.
5. When prompted on the device, grant the **SMS Permission** (`RECEIVE_SMS`).
6. Turn on **Automatic Protection** in the app.
7. Send a test SMS to the phone; SpamGuard will analyze the message, show a notification if high-risk spam is detected, and update the web dashboard in real time.

---

## 7. API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/signup` | Register a new user |
| `POST` | `/api/auth/login` | Authenticate user & start session |
| `POST` | `/api/auth/logout` | Terminate session |
| `GET`  | `/api/auth/me` | Current user profile |
| `POST` | `/api/predict` | Classify incoming SMS (`{ "message": "...", "sender": "..." }`) |
| `GET`  | `/api/history` | List classified messages (query param `filter=all\|spam\|safe\|high_risk`) |
| `GET`  | `/api/sms/<id>` | Retrieve message details |
| `POST` | `/api/sms/<id>/read` | Mark message as read |
| `GET`  | `/api/stats` | Aggregated statistics (totals, spam count, detection rate) |
| `GET`  | `/api/analytics` | 14-day daily detection trends & risk distribution |
| `GET`  | `/api/protection-status` | Android device connection & monitoring state |
| `POST` | `/api/device/heartbeat` | Phone heartbeat (`{ "monitoring_active": true }`) |
| `GET`  | `/api/settings` | Retrieve user preferences |
| `POST` | `/api/settings` | Save user preferences |
| `POST` | `/api/account/update` | Update display name or password |
| `GET`  | `/api/model-performance` | Model evaluation benchmarks (SVM, Naive Bayes, etc.) |

---

## 8. Deployment (Render)

SpamGuard is pre-configured for deployment on Render with `render.yaml`:

1. Push your repository to GitHub.
2. In Render, create a new **Web Service** from your repository.
3. Configure the environment variables in the Render Dashboard:
   - `SPAM_DB_DRIVER`: `mysql` (or `sqlite` with disk)
   - `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`
   - `FLASK_SECRET_KEY`: A secure random secret
4. Render automatically runs `pip install -r backend/requirements.txt` and starts the app with Gunicorn on `0.0.0.0:$PORT`.
