import os
import sys
import subprocess

def _check_and_reexec():
    try:
        import joblib
        import flask
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

import json
from app import app

client = app.test_client()

print("--- Test 1: GET / (Frontend) ---")
res = client.get("/")
print(f"Status: {res.status_code}, Length: {len(res.data)}, Content-Type: {res.content_type}")
assert res.status_code == 200
assert b"SpamGuard" in res.data
assert res.get_data(as_text=True).count(">Home</a>") == 1
assert b'id="sms-input"' not in res.data
assert b"Check SMS" not in res.data
checker = client.get("/classifier")
assert checker.status_code == 302
assert checker.headers["Location"] == "/"
assert client.get("/dashboard").status_code == 200
assert client.get("/history").status_code == 200
assert client.get("/protection").status_code == 200
assert client.get("/settings").status_code == 200
assert client.get("/analytics").status_code == 200
print("PASSED")

print("\n--- Test 2: GET /style.css ---")
res = client.get("/style.css")
print(f"Status: {res.status_code}, Length: {len(res.data)}")
assert res.status_code == 200
print("PASSED")

print("\n--- Test 3: GET /script.js (legacy manual checker removed) ---")
res = client.get("/script.js")
print(f"Status: {res.status_code}, Length: {len(res.data)}")
assert res.status_code == 404
print("PASSED")

print("\n--- Test 4: GET /api/model-performance ---")
res = client.get("/api/model-performance")
print(f"Status: {res.status_code}")
data = res.get_json()
print(f"Loaded {len(data)} models:")
for m in data:
    print(f"  {m['model_name']}: Acc={m['accuracy']}, Prec={m['precision']}, Rec={m['recall']}, F1={m['f1_score']}, Best={m['is_best']}")
assert res.status_code == 200
assert len(data) == 3
print("PASSED")

print("\n--- Test 5: POST /api/predict (SPAM) ---")
spam_msg = "URGENT! You have won a 1 week FREE membership in our 100,000 Prize Jackpot! Text OK to 87021 to claim"
res = client.post("/api/predict", json={"message": spam_msg, "sender": "+1 (202) 555-0123"})
print(f"Status: {res.status_code}")
data = res.get_json()
print(f"Prediction: {data}")
assert res.status_code == 200
assert data["prediction"] == "spam"
assert data["confidence"] > 0.5
assert data["risk_level"] == "HIGH"
assert data["id"] > 0
assert data["created_at"]
assert "87021" not in data["message"]
assert "100,000" not in data["message"]
assert data["sender"] == "***23"
spam_prediction_id = data["id"]
print("PASSED")

print("\n--- Test 6: POST /api/predict (HAM) ---")
ham_msg = "Hey what time are we having lunch today? I can meet you at the library cafe."
res = client.post("/api/predict", json={"message": ham_msg})
print(f"Status: {res.status_code}")
data = res.get_json()
print(f"Prediction: {data}")
assert res.status_code == 200
assert data["prediction"] == "ham"
assert data["confidence"] > 0.5
assert data["risk_level"] == "LOW"
assert data["id"] > 0
print("PASSED")

print("\n--- Test 7: GET /api/history ---")
res = client.get("/api/history")
print(f"Status: {res.status_code}")
history = res.get_json()
print(f"History records: {len(history)}")
assert len(history) >= 2
assert any(item["id"] == spam_prediction_id and item["sender"] == "***23" for item in history)
print("PASSED")

print("\n--- Test 8: GET /api/stats ---")
res = client.get("/api/stats")
print(f"Status: {res.status_code}")
stats = res.get_json()
print(f"Stats: {stats}")
assert stats["total"] >= 2
assert stats["spam"] >= 1
assert stats["ham"] >= 1
assert stats["high_risk_messages"] >= 1
print("PASSED")

print("\n--- Test 9: GET /api/analytics ---")
res = client.get("/api/analytics")
analytics = res.get_json()
print(f"Status: {res.status_code}, Analytics: {analytics}")
assert res.status_code == 200
assert "daily" in analytics and "risk_levels" in analytics
print("PASSED")

print("\n--- Test 10: POST /api/device/heartbeat ---")
res = client.post("/api/device/heartbeat", json={"monitoring_active": True})
heartbeat = res.get_json()
assert res.status_code == 200
assert heartbeat["phone_connected"] and heartbeat["protection_active"]
status = client.get("/api/protection-status")
assert status.status_code == 200
assert status.get_json()["ml_active"]
client.post("/api/device/heartbeat", json={"monitoring_active": False})
print("PASSED")

print("\n--- Test 11: POST /api/predict (empty message) ---")
res = client.post("/api/predict", json={"message": "   "})
data = res.get_json()
print(f"Status: {res.status_code}, Error: {data}")
assert res.status_code == 400
assert data["error"] == "Please enter an SMS message."
print("PASSED")

print("\n==========================================")
print("  ALL 11 TESTS PASSED SUCCESSFULLY!")
print("==========================================")
