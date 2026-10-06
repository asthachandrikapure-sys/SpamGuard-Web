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

## 3. Quick Start

### 1. Run the Platform
Double-click `spam-sms-classifier/run_app.bat` or run:

```bash
cd spam-sms-classifier/backend
python app.py
```

### 2. Open in Browser
Visit [http://127.0.0.1:5000](http://127.0.0.1:5000)

### 3. Run Automated Tests
```bash
cd spam-sms-classifier
python backend/test_full_platform.py
```

For full setup documentation, see `spam-sms-classifier/README.md`.
