"""
Rigorous End-to-End API Test Suite for Glaucoma Detection System
Tests all APIs with edge cases, error handling, and RBAC validation
"""
import requests
import json
import time
import os
from datetime import datetime

BASE_URL = "http://localhost:8000"
RESULTS = {"passed": 0, "failed": 0, "total": 0}

def test(name, condition, message=""):
    """Record test result"""
    RESULTS["total"] += 1
    if condition:
        RESULTS["passed"] += 1
        print(f"  ✅ {name}: {message}")
    else:
        RESULTS["failed"] += 1
        print(f"  ❌ {name}: {message}")
    return condition

def api_get(endpoint, token=None, expected_status=200):
    """GET request helper"""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        resp = requests.get(f"{BASE_URL}{endpoint}", headers=headers, timeout=30)
        return resp
    except Exception as e:
        return None

def api_post(endpoint, data=None, files=None, token=None, json_data=None):
    """POST request helper"""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        if files:
            resp = requests.post(f"{BASE_URL}{endpoint}", files=files, headers=headers, timeout=60)
        elif json_data:
            headers["Content-Type"] = "application/json"
            resp = requests.post(f"{BASE_URL}{endpoint}", json=json_data, headers=headers, timeout=30)
        else:
            resp = requests.post(f"{BASE_URL}{endpoint}", data=data, headers=headers, timeout=30)
        return resp
    except Exception as e:
        return None

def login(username, password):
    """Login and return token"""
    resp = api_post("/api/v1/auth/login", data={"username": username, "password": password})
    if resp and resp.status_code == 200:
        return resp.json().get("access_token")
    return None

print("="*70)
print("🔬 RIGOROUS API TEST SUITE - Glaucoma Detection System")
print("="*70)
print(f"Target: {BASE_URL}")
print(f"Time: {datetime.now().isoformat()}")
print()

# ==============================================================================
# 1. HEALTH & INFRASTRUCTURE TESTS
# ==============================================================================
print("--- 1. HEALTH & INFRASTRUCTURE ---")
resp = api_get("/")
test("Root endpoint", resp and resp.status_code == 200, f"Status: {resp.status_code if resp else 'FAIL'}")

resp = api_get("/health")
test("Health endpoint", resp and resp.status_code == 200, f"Model loaded: {resp.json().get('model_loaded') if resp else 'N/A'}")

resp = api_get("/metrics")
test("Prometheus metrics", resp and resp.status_code == 200 and "glaucoma" in resp.text, "Metrics available")

resp = api_get("/docs")
test("Swagger UI", resp and resp.status_code == 200, "Documentation available")

resp = api_get("/openapi.json")
test("OpenAPI spec", resp and resp.status_code == 200, f"{len(resp.json().get('paths', {}))} endpoints")

# ==============================================================================
# 2. AUTHENTICATION TESTS
# ==============================================================================
print("\n--- 2. AUTHENTICATION ---")

# Test login with valid admin credentials
admin_token = login("admin", "iscs")
test("Admin login", admin_token is not None, "Token received")

# Test login with invalid password
resp = api_post("/api/v1/auth/login", data={"username": "admin", "password": "wrongpassword"})
test("Invalid password rejected", resp and resp.status_code in [401, 400], f"Status: {resp.status_code}")

# Test login with non-existent user
resp = api_post("/api/v1/auth/login", data={"username": "nonexistent", "password": "test"})
test("Non-existent user rejected", resp and resp.status_code in [401, 400, 404], f"Status: {resp.status_code}")

# Test /me endpoint
resp = api_get("/api/v1/auth/me", token=admin_token)
test("Get current user", resp and resp.status_code == 200 and resp.json().get("username") == "admin", "User: admin")

# Test /me without token
resp = api_get("/api/v1/auth/me")
test("Unauthorized /me rejected", resp and resp.status_code == 401, "401 Unauthorized")

# Test different roles
doctor_token = login("doctor1", "iscs")
test("Doctor login", doctor_token is not None, "Token received")

radiologist_token = login("radiologist1", "iscs")
test("Radiologist login", radiologist_token is not None, "Token received")

# ==============================================================================
# 3. RBAC & AUTHORIZATION TESTS
# ==============================================================================
print("\n--- 3. RBAC & AUTHORIZATION ---")

# Test protected endpoints without token
resp = api_get("/api/v1/patients")
test("Patients without auth rejected", resp and resp.status_code == 401, "401 Unauthorized")

resp = api_get("/admin/verification-stats")
test("Admin endpoint without auth rejected", resp and resp.status_code == 401, "401 Unauthorized")

# Test with valid tokens
resp = api_get("/api/v1/patients", token=admin_token)
test("Admin can access patients", resp and resp.status_code == 200, f"Found {len(resp.json()) if resp else 0} patients")

resp = api_get("/admin/verification-stats", token=admin_token)
test("Admin can access verification stats", resp and resp.status_code == 200, "Stats retrieved")

resp = api_get("/admin/verification-stats", token=doctor_token)
test("Doctor can access verification stats", resp and resp.status_code == 200, "Stats retrieved")

# ==============================================================================
# 4. PATIENT MANAGEMENT TESTS
# ==============================================================================
print("\n--- 4. PATIENT MANAGEMENT ---")

# Create patient
patient_data = {
    "first_name": f"Test_{int(time.time())}",
    "last_name": "Patient",
    "mrn": f"MRN-{int(time.time())}",
    "gender": "male",
    "email": f"test_{int(time.time())}@example.com"
}
resp = api_post("/api/v1/patients", json_data=patient_data, token=admin_token)
test("Create patient", resp and resp.status_code in [200, 201], f"Status: {resp.status_code}")
patient_id = resp.json().get("patient_id") if resp and resp.status_code in [200, 201] else None

# Get patient list
resp = api_get("/api/v1/patients", token=admin_token)
test("List patients", resp and resp.status_code == 200, f"Found {len(resp.json()) if resp else 0} patients")

# Test duplicate MRN rejection
resp = api_post("/api/v1/patients", json_data=patient_data, token=admin_token)
test("Duplicate MRN rejected", resp and resp.status_code in [400, 409, 422], f"Status: {resp.status_code}")

# ==============================================================================
# 5. PREDICTION API TESTS
# ==============================================================================
print("\n--- 5. PREDICTION APIs ---")

# Find test images
test_images = []
for subdir in ["glaucoma", "normal"]:
    path = f"data/train/{subdir}"
    if os.path.exists(path):
        files = [f for f in os.listdir(path) if f.endswith(('.jpg', '.png', '.jpeg'))]
        if files:
            test_images.append(os.path.join(path, files[0]))

if test_images:
    test_image = test_images[0]
    print(f"  Using test image: {test_image}")
    
    # Single prediction
    with open(test_image, 'rb') as f:
        resp = api_post("/predict", files={"file": f})
    test("Single prediction", resp and resp.status_code == 200, 
         f"Label: {resp.json().get('label')}, Confidence: {resp.json().get('confidence'):.2f}" if resp and resp.status_code == 200 else "FAIL")
    
    # Prediction with explanation
    with open(test_image, 'rb') as f:
        resp = api_post("/predict-with-explanation", files={"file": f})
    has_heatmap = resp and resp.status_code == 200 and resp.json().get("heatmap_base64")
    test("Prediction with Grad-CAM", has_heatmap, 
         f"Heatmap: {'Yes' if has_heatmap else 'No'}, Label: {resp.json().get('label') if resp else 'N/A'}")
    
    # Batch prediction with 2 images
    if len(test_images) >= 1:
        with open(test_image, 'rb') as f1, open(test_image, 'rb') as f2:
            files = [("files", f1), ("files", f2)]
            resp = api_post("/batch-predict", files=files)
        if resp and resp.status_code in [200, 201]:
            data = resp.json()
            processed = data.get('processed_count', data.get('total', 0))
            success = data.get('success_count', data.get('successful', 0))
            test("Batch prediction", True, f"Processed: {processed}, Success: {success}")
        else:
            test("Batch prediction", False, f"Status: {resp.status_code if resp else 'FAIL'}")
else:
    print("  ⚠️ No test images found - skipping prediction tests")

# Test prediction without file
resp = api_post("/predict")
test("Prediction without file rejected", resp and resp.status_code == 422, f"Status: {resp.status_code}")

# ==============================================================================
# 6. ADMIN VERIFICATION WORKFLOW TESTS
# ==============================================================================
print("\n--- 6. ADMIN VERIFICATION WORKFLOW ---")

resp = api_get("/admin/verification-stats", token=admin_token)
test("Get verification stats", resp and resp.status_code == 200, 
     f"Pending: {resp.json().get('pending', 0)}" if resp else "FAIL")

resp = api_get("/admin/pending-images", token=admin_token)
pending_count = len(resp.json()) if resp and resp.status_code == 200 and isinstance(resp.json(), list) else 0
test("Get pending images", resp and resp.status_code == 200, f"Found {pending_count} pending")

resp = api_post("/admin/merge-to-training", token=admin_token)
test("Merge to training", resp and resp.status_code == 200,
     f"Merged: {resp.json().get('merged_count', 0)}" if resp else "FAIL")

# ==============================================================================
# 7. ERROR HANDLING TESTS
# ==============================================================================
print("\n--- 7. ERROR HANDLING ---")

resp = api_get("/nonexistent-endpoint")
test("404 for unknown endpoint", resp and resp.status_code == 404, f"Status: {resp.status_code}")

resp = api_post("/api/v1/patients", json_data={"invalid": "data"}, token=admin_token)
test("Invalid patient data rejected", resp and resp.status_code == 422, f"Status: {resp.status_code}")

# ==============================================================================
# 8. PERFORMANCE TESTS
# ==============================================================================
print("\n--- 8. PERFORMANCE ---")

# Health check latency
start = time.time()
resp = api_get("/health")
latency = (time.time() - start) * 1000
test("Health check latency", latency < 500, f"{latency:.0f}ms")

# Auth latency
start = time.time()
token = login("admin", "iscs")
latency = (time.time() - start) * 1000
test("Login latency", latency < 2000, f"{latency:.0f}ms")

# ==============================================================================
# SUMMARY
# ==============================================================================
print("\n" + "="*70)
print(f"📊 TEST SUMMARY: {RESULTS['passed']} passed, {RESULTS['failed']} failed, {RESULTS['total']} total")
print(f"   Pass Rate: {RESULTS['passed']/RESULTS['total']*100:.1f}%")
print("="*70)

# Save results
os.makedirs("outputs/test_results", exist_ok=True)
result_file = f"outputs/test_results/rigorous_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(result_file, 'w') as f:
    json.dump({
        "timestamp": datetime.now().isoformat(),
        "base_url": BASE_URL,
        "summary": RESULTS
    }, f, indent=2)
print(f"\n💾 Results saved to: {result_file}")

exit(0 if RESULTS['failed'] == 0 else 1)
