import requests

BASE = "http://localhost:8001"

# Login
r = requests.post(f"{BASE}/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
print(f"Login: {r.status_code}")
data = r.json()
token = data.get("access_token", "")
print(f"Role: {data.get('user', {}).get('role')}")

h = {"Authorization": f"Bearer {token}"}

endpoints = [
    ("/api/v1/admin/stats", "stats"),
    ("/api/v1/admin/trend?days=7", "trend"),
    ("/api/v1/admin/model-analysis", "model-analysis"),
    ("/api/v1/admin/detection-contents?page=1&page_size=3", "contents"),
    ("/api/v1/admin/users?page=1&page_size=3", "users"),
    ("/api/v1/admin/detections?page=1&page_size=3", "detections"),
]

for ep, name in endpoints:
    try:
        r = requests.get(f"{BASE}{ep}", headers=h, timeout=15)
        print(f"\n[{name}] {ep}: {r.status_code}")
        if r.status_code == 200:
            j = r.json()
            if isinstance(j, dict):
                for k, v in list(j.items())[:5]:
                    val = str(v)[:120]
                    print(f"  OK {k}: {val}")
            elif isinstance(j, list):
                print(f"  OK array: {len(j)} items")
        else:
            print(f"  FAIL: {r.text[:300]}")
    except Exception as e:
        print(f"{name}: EXCEPTION - {e}")

# Test export
try:
    r = requests.post(f"{BASE}/api/v1/admin/export-dataset", headers=h, params={"sample_limit": 5}, timeout=15)
    print(f"\n[export] {r.status_code}")
    if r.status_code == 200:
        j = r.json()
        print(f"  total: {j.get('total')}, dataset items: {len(j.get('dataset', []))}")
except Exception as e:
    print(f"export: {e}")

# Test detail endpoint
try:
    r = requests.get(f"{BASE}{endpoints[4][0]}", headers=h, timeout=10)
    if r.status_code == 200:
        dets = r.json().get("detections", [])
        if dets:
            det_id = dets[0].get("id")
            r2 = requests.get(f"{BASE}/api/v1/admin/detections/{det_id}", headers=h, timeout=10)
            print(f"\n[detail] /detections/{det_id[:8]}...: {r2.status_code}")
            if r2.status_code == 200:
                j2 = r2.json()
                for k in ["id","modality","is_ai_generated","confidence","risk_level"]:
                    print(f"  OK {k}: {j2.get(k)}")
except Exception as e:
    print(f"detail: {e}")

print("\n=== DONE ===")
