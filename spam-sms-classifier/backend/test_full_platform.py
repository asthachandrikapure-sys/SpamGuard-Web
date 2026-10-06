"""
test_full_platform.py — SpamGuard End-to-End Validation Test Suite
Tests backend, MySQL database, ML model, authentication, APIs, and template rendering.
"""

import os
import sys

# Ensure backend directory is in path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import json
from app import app, load_model
import database as db

client = app.test_client()

def run_tests():
    print("=" * 65)
    print("       SPAMGUARD — FULL PLATFORM VERIFICATION SUITE")
    print("=" * 65)

    # 1. Database & Model Init
    print("\n[1] Initializing Database & Loading ML Model...")
    db_res = db.initialize_database()
    print(f"    MySQL/DB connected: {db_res} (Driver: {db.DB_DRIVER})")

    loaded, msg = load_model()
    print(f"    ML Model status: {msg}")
    assert loaded, f"Model failed to load: {msg}"
    print("    [PASS] Database & Model loaded.")

    # 2. Public Pages
    print("\n[2] Testing Public Routes...")
    res = client.get("/")
    assert res.status_code == 200
    assert b"SPAMGUARD" in res.data
    assert b"Real-Time SMS Security" in res.data
    print("    [PASS] GET / (Landing Page)")

    res = client.get("/login")
    assert res.status_code == 200
    assert b"Sign In" in res.data
    print("    [PASS] GET /login")

    res = client.get("/signup")
    assert res.status_code == 200
    assert b"Create your account" in res.data
    print("    [PASS] GET /signup")

    # 3. Static Files
    print("\n[3] Testing Static CSS & JavaScript Assets...")
    for asset in [
        "/static/css/style.css",
        "/static/js/dashboard.js",
        "/static/js/inbox.js",
        "/static/js/settings.js",
        "/static/js/analytics.js",
        "/static/js/protection-status.js"
    ]:
        res = client.get(asset)
        assert res.status_code == 200, f"Asset missing: {asset} ({res.status_code})"
        print(f"    [PASS] {asset} ({len(res.data)} bytes)")

    # 4. Authentication Flow (Signup, Login, Me, Logout)
    print("\n[4] Testing Authentication APIs...")
    test_email = f"agent_test_{os.urandom(4).hex()}@spamguard.security"
    test_password = "SecurePassword123!"

    # Signup
    res = client.post("/api/auth/signup", json={
        "name": "Security Analyst",
        "email": test_email,
        "password": test_password
    })
    assert res.status_code == 200
    signup_data = res.get_json()
    assert signup_data.get("success") is True
    print(f"    [PASS] POST /api/auth/signup -> Created user {test_email}")

    # Duplicate Signup rejection
    res = client.post("/api/auth/signup", json={
        "name": "Duplicate User",
        "email": test_email,
        "password": test_password
    })
    assert res.status_code == 409
    print("    [PASS] POST /api/auth/signup -> Duplicate email rejected with 409")

    # Check session auth with /api/auth/me
    res = client.get("/api/auth/me")
    assert res.status_code == 200
    me_data = res.get_json()
    assert me_data["email"] == test_email
    print(f"    [PASS] GET /api/auth/me -> Authenticated as {me_data['name']}")

    # Logout
    res = client.post("/api/auth/logout")
    assert res.status_code == 200

    # Unauthenticated /api/auth/me
    res = client.get("/api/auth/me")
    assert res.status_code == 401
    print("    [PASS] POST /api/auth/logout -> Session cleared")

    # Login
    res = client.post("/api/auth/login", json={
        "email": test_email,
        "password": test_password
    })
    assert res.status_code == 200
    assert res.get_json().get("success") is True
    print("    [PASS] POST /api/auth/login -> Logged in successfully")

    # 5. Protected Frontend Pages
    print("\n[5] Testing Authenticated Application Pages...")
    for route, title_text in [
        ("/dashboard", b"Dashboard"),
        ("/inbox", b"SMS Inbox"),
        ("/protection", b"Live Protection"),
        ("/analytics", b"Protection Analytics"),
        ("/devices", b"Connected Devices"),
        ("/settings", b"Settings")
    ]:
        res = client.get(route)
        assert res.status_code == 200, f"Route {route} failed with {res.status_code}"
        assert title_text in res.data, f"Title text missing in {route}"
        print(f"    [PASS] GET {route}")

    # 6. ML SMS Classification (/api/predict)
    print("\n[6] Testing ML SMS Prediction Flow...")
    # Spam message
    spam_text = "CONGRATULATIONS! You have won a 50,000 cash prize! Claim immediately at http://claim-prize.fake or call 9876543210"
    res = client.post("/api/predict", json={
        "message": spam_text,
        "sender": "+91 98765 43210"
    })
    assert res.status_code == 200
    spam_result = res.get_json()
    assert spam_result["prediction"] == "spam"
    assert spam_result["risk_level"] == "HIGH"
    assert spam_result["confidence"] > 0.5
    assert spam_result["id"] > 0
    assert "9876543210" not in spam_result["message"]  # Privacy masking verified
    assert spam_result["sender"] == "***10"  # Sender masked
    spam_id = spam_result["id"]
    print(f"    [PASS] SPAM detection: ID={spam_id}, Pred={spam_result['prediction']}, Conf={spam_result['confidence']*100:.1f}%, Risk={spam_result['risk_level']}")

    # Ham / Safe message
    ham_text = "Hi Astha, your security verification code is 492104. Valid for 10 minutes."
    res = client.post("/api/predict", json={
        "message": ham_text,
        "sender": "BANK-ALERT"
    })
    assert res.status_code == 200
    ham_result = res.get_json()
    assert ham_result["prediction"] == "ham"
    assert ham_result["risk_level"] == "LOW"
    assert ham_result["id"] > 0
    ham_id = ham_result["id"]
    print(f"    [PASS] SAFE detection: ID={ham_id}, Pred={ham_result['prediction']}, Conf={ham_result['confidence']*100:.1f}%, Risk={ham_result['risk_level']}")

    # 7. SMS History & Inbox API
    print("\n[7] Testing SMS History & Filters...")
    res = client.get("/api/history?filter=all")
    assert res.status_code == 200
    all_history = res.get_json()
    assert len(all_history) >= 2
    print(f"    [PASS] GET /api/history?filter=all ({len(all_history)} items returned)")

    res = client.get("/api/history?filter=spam")
    assert res.status_code == 200
    spam_history = res.get_json()
    assert all(item["prediction"] == "spam" for item in spam_history)
    print(f"    [PASS] GET /api/history?filter=spam ({len(spam_history)} spam items)")

    res = client.get("/api/history?filter=safe")
    assert res.status_code == 200
    safe_history = res.get_json()
    assert all(item["prediction"] == "ham" for item in safe_history)
    print(f"    [PASS] GET /api/history?filter=safe ({len(safe_history)} safe items)")

    # Read status update
    res = client.post(f"/api/sms/{spam_id}/read")
    assert res.status_code == 200
    res = client.get(f"/api/sms/{spam_id}")
    assert res.status_code == 200
    assert res.get_json()["is_read"] == 1
    print(f"    [PASS] POST /api/sms/{spam_id}/read & GET /api/sms/{spam_id}")

    # 8. Statistics & Analytics
    print("\n[8] Testing Statistics & Analytics APIs...")
    res = client.get("/api/stats")
    assert res.status_code == 200
    stats = res.get_json()
    assert stats["total_messages"] >= 2
    assert stats["spam_messages"] >= 1
    assert stats["ham_messages"] >= 1
    print(f"    [PASS] GET /api/stats -> Total={stats['total_messages']}, Spam={stats['spam_messages']}, Ham={stats['ham_messages']}, Rate={stats['spam_percentage']}%")

    res = client.get("/api/analytics")
    assert res.status_code == 200
    analytics = res.get_json()
    assert "risk_levels" in analytics
    assert "average_confidence" in analytics
    print(f"    [PASS] GET /api/analytics -> Avg Conf={analytics['average_confidence']*100:.1f}%, Risk Levels={analytics['risk_levels']}")

    res = client.get("/api/model-performance")
    assert res.status_code == 200
    perf = res.get_json()
    assert len(perf) >= 1
    print(f"    [PASS] GET /api/model-performance -> Loaded {len(perf)} evaluated models")

    # 9. Settings API
    print("\n[9] Testing Settings & Account Update APIs...")
    res = client.get("/api/settings")
    assert res.status_code == 200
    cur_settings = res.get_json()
    assert "sms_monitoring" in cur_settings
    print(f"    [PASS] GET /api/settings -> Current: {cur_settings}")

    # Save settings
    res = client.post("/api/settings", json={
        "sms_monitoring": 1,
        "ai_detection": 1,
        "high_risk_alerts": 1,
        "mask_phone_numbers": 1,
        "hide_sms_content": 0
    })
    assert res.status_code == 200
    assert res.get_json().get("success") is True
    print("    [PASS] POST /api/settings -> Saved preferences successfully")

    # Account Profile Name Update
    res = client.post("/api/account/update", json={
        "action": "profile",
        "name": "Lead Security Officer"
    })
    assert res.status_code == 200
    assert client.get("/api/auth/me").get_json()["name"] == "Lead Security Officer"
    print("    [PASS] POST /api/account/update (profile) -> Name updated")

    # Account Password Update
    new_password = "NewSuperSecurePassword2026!"
    res = client.post("/api/account/update", json={
        "action": "password",
        "current_password": test_password,
        "new_password": new_password,
        "confirm_password": new_password
    })
    assert res.status_code == 200
    print("    [PASS] POST /api/account/update (password) -> Password updated")

    # Verify login with new password
    client.post("/api/auth/logout")
    res = client.post("/api/auth/login", json={
        "email": test_email,
        "password": new_password
    })
    assert res.status_code == 200
    print("    [PASS] POST /api/auth/login with new password succeeded")

    # 10. Device Heartbeat & Protection Status
    print("\n[10] Testing Device Heartbeat & Protection Status...")
    res = client.post("/api/device/heartbeat", json={"monitoring_active": True})
    assert res.status_code == 200
    heartbeat_res = res.get_json()
    assert heartbeat_res["phone_connected"] is True
    assert heartbeat_res["monitoring_active"] is True
    assert heartbeat_res["protection_active"] is True
    print(f"    [PASS] POST /api/device/heartbeat -> Connected={heartbeat_res['phone_connected']}, Protected={heartbeat_res['protection_active']}")

    res = client.get("/api/protection-status")
    assert res.status_code == 200
    prot_status = res.get_json()
    assert prot_status["phone_connected"] is True
    print("    [PASS] GET /api/protection-status -> Active device verified")

    # 11. SMS Inbox Actions (Important, Unread, Trash)
    print("\n[11] Testing SMS Star, Unread, and Trash Actions...")
    res = client.post(f"/api/sms/{spam_id}/important", json={"is_important": 1})
    assert res.status_code == 200
    assert res.get_json()["is_important"] == 1
    print(f"    [PASS] POST /api/sms/{spam_id}/important -> Marked Important")

    res = client.post(f"/api/sms/{spam_id}/unread")
    assert res.status_code == 200
    assert res.get_json()["is_read"] == 0
    print(f"    [PASS] POST /api/sms/{spam_id}/unread -> Marked Unread")

    res = client.get("/api/history?filter=important")
    assert res.status_code == 200
    assert any(m["id"] == spam_id for m in res.get_json())
    print("    [PASS] GET /api/history?filter=important -> Starred message returned")

    res = client.post(f"/api/sms/{spam_id}/trash", json={"is_trashed": 1})
    assert res.status_code == 200
    assert res.get_json()["is_trashed"] == 1
    print(f"    [PASS] POST /api/sms/{spam_id}/trash -> Moved to Trash")

    res = client.get("/api/history?filter=trash")
    assert res.status_code == 200
    assert any(m["id"] == spam_id for m in res.get_json())
    print("    [PASS] GET /api/history?filter=trash -> Trashed message isolated in Trash")

    # Restore from trash
    res = client.post(f"/api/sms/{spam_id}/trash", json={"is_trashed": 0})
    assert res.status_code == 200

    # 12. Devices API (GET, Register, List)
    print("\n[12] Testing Devices Management APIs...")
    res = client.get("/api/devices")
    assert res.status_code == 200
    devices = res.get_json()
    assert isinstance(devices, list)
    print(f"    [PASS] GET /api/devices -> Found {len(devices)} user devices")

    res = client.post("/api/devices/register", json={
        "device_name": "Testing Pixel 9 Pro",
        "mobile_number": "9503564504"
    })
    assert res.status_code == 200
    new_dev = res.get_json()["device"]
    assert new_dev["device_name"] == "Testing Pixel 9 Pro"
    print(f"    [PASS] POST /api/devices/register -> Registered device ID={new_dev['id']}")

    # 13. Mobile Number Authentication & Forgot Password Reset
    print("\n[13] Testing Mobile Number Authentication & Forgot Password...")
    client.post("/api/auth/logout")

    # Test login with test mobile number: 9503564504
    res = client.post("/api/auth/login", json={
        "identifier": "9503564504",
        "password": "Password123!"
    })
    assert res.status_code == 200
    assert res.get_json().get("success") is True
    print("    [PASS] POST /api/auth/login with mobile number 9503564504 succeeded")

    # Test reset password via mobile number
    reset_pw = "ResetPassWord9503564504!"
    res = client.post("/api/auth/reset-password", json={
        "identifier": "9503564504",
        "password": reset_pw,
        "confirm_password": reset_pw
    })
    assert res.status_code == 200
    print("    [PASS] POST /api/auth/reset-password for mobile 9503564504 succeeded")

    # Verify login with reset password
    client.post("/api/auth/logout")
    res = client.post("/api/auth/login", json={
        "identifier": "9503564504",
        "password": reset_pw
    })
    assert res.status_code == 200
    print("    [PASS] Login with newly reset password succeeded")

    # Restore default test password
    db.reset_user_password("9503564504", "689bc99332297a9f2e8ed250d92a82d0:8b272a710d6acb6745ab6d8b757067a9afd7492284cefedc314a4f14c3f39bcd")

    # 14. Complete User Isolation Flow (User A vs User B)
    print("\n[14] Testing Strict Multi-User Isolation (User A vs User B)...")
    client.post("/api/auth/logout")

    mobile_a = f"91{os.urandom(4).hex()[:8]}"
    email_a = f"user_a_{os.urandom(3).hex()}@spamguard.security"
    res_a = client.post("/api/auth/signup", json={
        "name": "User Alpha",
        "email": email_a,
        "mobile_number": mobile_a,
        "password": "PasswordAlpha123!"
    })
    assert res_a.status_code == 200

    # User A classifies an SMS
    res = client.post("/api/predict", json={
        "message": "User A secret alert message",
        "sender": "BANK-ALPHA"
    })
    assert res.status_code == 200
    sms_a_id = res.get_json()["id"]

    # Verify User A sees SMS A
    res_a_history = client.get("/api/history?filter=all").get_json()
    assert any(m["id"] == sms_a_id for m in res_a_history)
    print("    [PASS] User A created, classified SMS A, and sees it in history")

    # User B signs up and logs in
    client.post("/api/auth/logout")
    mobile_b = f"92{os.urandom(4).hex()[:8]}"
    email_b = f"user_b_{os.urandom(3).hex()}@spamguard.security"
    res_b = client.post("/api/auth/signup", json={
        "name": "User Beta",
        "email": email_b,
        "mobile_number": mobile_b,
        "password": "PasswordBeta123!"
    })
    assert res_b.status_code == 200

    # User B classifies an SMS
    res = client.post("/api/predict", json={
        "message": "User B distinct message",
        "sender": "BANK-BETA"
    })
    assert res.status_code == 200
    sms_b_id = res.get_json()["id"]

    # User B MUST NOT see User A's SMS!
    res_b_history = client.get("/api/history?filter=all").get_json()
    assert all(m["id"] != sms_a_id for m in res_b_history), "CRITICAL: User B saw User A's SMS!"
    assert any(m["id"] == sms_b_id for m in res_b_history)
    print("    [PASS] User B history is completely isolated (cannot see User A's SMS)")

    # User B attempts to access User A's SMS directly by ID -> MUST return 404
    res_forbidden = client.get(f"/api/sms/{sms_a_id}")
    assert res_forbidden.status_code == 404, "CRITICAL: User B directly retrieved User A's SMS!"
    print(f"    [PASS] GET /api/sms/{sms_a_id} by User B rejected with 404 (Access Denied)")

    print("\n" + "=" * 65)
    print("       ALL SPAMGUARD PLATFORM TESTS PASSED SUCCESSFULLY! ")
    print("=" * 65)

if __name__ == "__main__":
    run_tests()

