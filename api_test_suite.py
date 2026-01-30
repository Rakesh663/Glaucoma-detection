"""
Glaucoma Detection API - Complete End-to-End Test Suite
=======================================================
Tests all API endpoints for frontend integration verification.
Run with: python api_test_suite.py
"""

import requests
import json
import os
import sys
from datetime import datetime
from typing import Optional
import time

# Configuration
BASE_URL = "http://localhost:8002"
TEST_IMAGE_PATH = None  # Will search for test images

# Test results tracking
test_results = []

def log_result(test_name: str, passed: bool, details: str = "", response: dict = None):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    result = {
        "test": test_name,
        "passed": passed,
        "status": status,
        "details": details,
        "response": response
    }
    test_results.append(result)
    print(f"{status} | {test_name}")
    if details:
        print(f"       └─ {details}")

def find_test_image():
    """Find a test image in the project"""
    search_paths = [
        "data/train/glaucoma",
        "data/train/normal",
        "data/test/glaucoma",
        "data/test/normal",
        "data/incoming",
        "data"
    ]
    
    for path in search_paths:
        if os.path.exists(path):
            for f in os.listdir(path):
                if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                    return os.path.join(path, f)
    return None

def create_test_image():
    """Create a simple test image if none exists"""
    try:
        from PIL import Image
        import numpy as np
        
        # Create a simple 512x512 image
        img = Image.fromarray(np.random.randint(0, 255, (512, 512, 3), dtype=np.uint8))
        test_path = "test_image_temp.jpg"
        img.save(test_path)
        return test_path
    except Exception as e:
        print(f"Could not create test image: {e}")
        return None

# ============================================================================
# HEALTH & SYSTEM TESTS
# ============================================================================

def test_root_endpoint():
    """Test GET / endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "service" in data and "Glaucoma" in data.get("service", ""):
                log_result("GET /", True, f"Service: {data['service']}", data)
                return True
        log_result("GET /", False, f"Status: {response.status_code}")
        return False
    except Exception as e:
        log_result("GET /", False, str(e))
        return False

def test_health_endpoint():
    """Test GET /health endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            model_loaded = data.get("model_loaded", False)
            log_result("GET /health", True, f"Model loaded: {model_loaded}", data)
            return True
        log_result("GET /health", False, f"Status: {response.status_code}")
        return False
    except Exception as e:
        log_result("GET /health", False, str(e))
        return False

def test_docs_endpoint():
    """Test GET /docs endpoint (Swagger UI)"""
    try:
        response = requests.get(f"{BASE_URL}/docs", timeout=10)
        if response.status_code == 200:
            log_result("GET /docs", True, "Swagger UI accessible")
            return True
        log_result("GET /docs", False, f"Status: {response.status_code}")
        return False
    except Exception as e:
        log_result("GET /docs", False, str(e))
        return False

def test_metrics_endpoint():
    """Test GET /metrics endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/metrics", timeout=10)
        if response.status_code == 200:
            log_result("GET /metrics", True, "Prometheus metrics available")
            return True
        log_result("GET /metrics", False, f"Status: {response.status_code}")
        return False
    except Exception as e:
        log_result("GET /metrics", False, str(e))
        return False

# ============================================================================
# AUTHENTICATION TESTS
# ============================================================================

def test_login_success():
    """Test POST /api/v1/auth/login with valid credentials"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            data={"username": "admin", "password": "iscs"},
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            if "access_token" in data:
                log_result("POST /api/v1/auth/login (admin)", True, f"Role: {data.get('role')}", 
                          {"user_id": data.get("user_id"), "role": data.get("role")})
                return data["access_token"]
        log_result("POST /api/v1/auth/login (admin)", False, f"Status: {response.status_code}, Response: {response.text[:200]}")
        return None
    except Exception as e:
        log_result("POST /api/v1/auth/login (admin)", False, str(e))
        return None

def test_login_failure():
    """Test POST /api/v1/auth/login with invalid credentials"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            data={"username": "admin", "password": "wrongpassword"},
            timeout=10
        )
        if response.status_code == 401:
            log_result("POST /api/v1/auth/login (invalid)", True, "Correctly rejected invalid credentials")
            return True
        log_result("POST /api/v1/auth/login (invalid)", False, f"Expected 401, got {response.status_code}")
        return False
    except Exception as e:
        log_result("POST /api/v1/auth/login (invalid)", False, str(e))
        return False

def test_get_current_user(token: str):
    """Test GET /api/v1/auth/me"""
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            log_result("GET /api/v1/auth/me", True, f"User: {data.get('username')}", data)
            return True
        log_result("GET /api/v1/auth/me", False, f"Status: {response.status_code}")
        return False
    except Exception as e:
        log_result("GET /api/v1/auth/me", False, str(e))
        return False

def test_unauthorized_access():
    """Test accessing protected endpoint without token"""
    try:
        response = requests.get(f"{BASE_URL}/api/v1/auth/me", timeout=10)
        if response.status_code == 401:
            log_result("Unauthorized access test", True, "Correctly requires authentication")
            return True
        log_result("Unauthorized access test", False, f"Expected 401, got {response.status_code}")
        return False
    except Exception as e:
        log_result("Unauthorized access test", False, str(e))
        return False

# ============================================================================
# PATIENT MANAGEMENT TESTS
# ============================================================================

def test_create_patient(token: str):
    """Test POST /api/v1/patients/"""
    try:
        patient_data = {
            "first_name": "Test",
            "last_name": f"Patient_{datetime.now().strftime('%H%M%S')}",
            "mrn": f"MRN-TEST-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "date_of_birth": "1990-01-15",
            "gender": "male",
            "email": f"test_{datetime.now().strftime('%H%M%S')}@example.com",
            "phone": "+91-9876543210"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/v1/patients/",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json=patient_data,
            timeout=15
        )
        
        if response.status_code == 201:
            data = response.json()
            patient_id = data.get("patient_id")
            log_result("POST /api/v1/patients/", True, f"Created patient: {patient_id}", 
                      {"patient_id": patient_id, "mrn": data.get("mrn")})
            return patient_id
        log_result("POST /api/v1/patients/", False, f"Status: {response.status_code}, Response: {response.text[:300]}")
        return None
    except Exception as e:
        log_result("POST /api/v1/patients/", False, str(e))
        return None

def test_list_patients(token: str):
    """Test GET /api/v1/patients/"""
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/patients/?page=1&page_size=10",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            total = data.get("total", 0)
            log_result("GET /api/v1/patients/", True, f"Total patients: {total}", 
                      {"total": total, "page": data.get("page")})
            return True
        log_result("GET /api/v1/patients/", False, f"Status: {response.status_code}")
        return False
    except Exception as e:
        log_result("GET /api/v1/patients/", False, str(e))
        return False

def test_get_patient(token: str, patient_id: str):
    """Test GET /api/v1/patients/{patient_id}"""
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/patients/{patient_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            log_result("GET /api/v1/patients/{id}", True, f"Patient: {data.get('first_name')} {data.get('last_name')}")
            return True
        log_result("GET /api/v1/patients/{id}", False, f"Status: {response.status_code}")
        return False
    except Exception as e:
        log_result("GET /api/v1/patients/{id}", False, str(e))
        return False

def test_update_patient(token: str, patient_id: str):
    """Test PUT /api/v1/patients/{patient_id}"""
    try:
        update_data = {"phone": "+91-1111111111"}
        
        response = requests.put(
            f"{BASE_URL}/api/v1/patients/{patient_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json=update_data,
            timeout=10
        )
        if response.status_code == 200:
            log_result("PUT /api/v1/patients/{id}", True, "Patient updated successfully")
            return True
        log_result("PUT /api/v1/patients/{id}", False, f"Status: {response.status_code}")
        return False
    except Exception as e:
        log_result("PUT /api/v1/patients/{id}", False, str(e))
        return False

def test_patient_stats(token: str, patient_id: str):
    """Test GET /api/v1/patients/{patient_id}/stats"""
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/patients/{patient_id}/stats",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            log_result("GET /api/v1/patients/{id}/stats", True, f"Total predictions: {data.get('total_predictions', 0)}")
            return True
        log_result("GET /api/v1/patients/{id}/stats", False, f"Status: {response.status_code}")
        return False
    except Exception as e:
        log_result("GET /api/v1/patients/{id}/stats", False, str(e))
        return False

# ============================================================================
# PREDICTION TESTS
# ============================================================================

def test_predict_with_explanation(image_path: str):
    """Test POST /predict-with-explanation (no auth required)"""
    try:
        if not image_path or not os.path.exists(image_path):
            log_result("POST /predict-with-explanation", False, "No test image available")
            return None
        
        with open(image_path, "rb") as f:
            files = {"file": (os.path.basename(image_path), f, "image/jpeg")}
            response = requests.post(
                f"{BASE_URL}/predict-with-explanation",
                files=files,
                timeout=60
            )
        
        if response.status_code == 200:
            data = response.json()
            label = data.get("label")
            confidence = data.get("confidence", 0)
            has_heatmap = data.get("heatmap_base64") is not None
            log_result("POST /predict-with-explanation", True, 
                      f"Label: {label}, Confidence: {confidence:.2%}, Heatmap: {has_heatmap}",
                      {"label": label, "confidence": confidence, "has_heatmap": has_heatmap})
            return data
        log_result("POST /predict-with-explanation", False, f"Status: {response.status_code}, Response: {response.text[:300]}")
        return None
    except Exception as e:
        log_result("POST /predict-with-explanation", False, str(e))
        return None

def test_predict(token: str, patient_id: str, image_path: str):
    """Test POST /predict (requires auth and patient_id)"""
    try:
        if not image_path or not os.path.exists(image_path):
            log_result("POST /predict", False, "No test image available")
            return None
        
        with open(image_path, "rb") as f:
            files = {"file": (os.path.basename(image_path), f, "image/jpeg")}
            data = {"patient_id": patient_id, "use_cache": "false"}
            response = requests.post(
                f"{BASE_URL}/predict",
                headers={"Authorization": f"Bearer {token}"},
                files=files,
                data=data,
                timeout=60
            )
        
        if response.status_code == 200:
            result = response.json()
            label = result.get("label")
            confidence = result.get("confidence", 0)
            log_result("POST /predict", True, 
                      f"Label: {label}, Confidence: {confidence:.2%}, Risk: {result.get('risk_level')}",
                      {"label": label, "confidence": confidence, "risk_level": result.get("risk_level")})
            return result
        log_result("POST /predict", False, f"Status: {response.status_code}, Response: {response.text[:300]}")
        return None
    except Exception as e:
        log_result("POST /predict", False, str(e))
        return None

def test_patient_predictions(token: str, patient_id: str):
    """Test GET /api/v1/patients/{patient_id}/predictions"""
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/patients/{patient_id}/predictions",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            total = data.get("total", 0)
            log_result("GET /api/v1/patients/{id}/predictions", True, f"Total predictions: {total}")
            return True
        log_result("GET /api/v1/patients/{id}/predictions", False, f"Status: {response.status_code}")
        return False
    except Exception as e:
        log_result("GET /api/v1/patients/{id}/predictions", False, str(e))
        return False

# ============================================================================
# ADMIN VERIFICATION TESTS
# ============================================================================

def test_pending_images(token: str):
    """Test GET /admin/pending-images"""
    try:
        response = requests.get(
            f"{BASE_URL}/admin/pending-images?limit=10",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            count = len(data) if isinstance(data, list) else 0
            log_result("GET /admin/pending-images", True, f"Pending images: {count}")
            return data
        log_result("GET /admin/pending-images", False, f"Status: {response.status_code}")
        return None
    except Exception as e:
        log_result("GET /admin/pending-images", False, str(e))
        return None

def test_verification_stats(token: str):
    """Test GET /admin/verification-stats"""
    try:
        response = requests.get(
            f"{BASE_URL}/admin/verification-stats",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            log_result("GET /admin/verification-stats", True, 
                      f"Pending: {data.get('pending_count', 0)}, Verified Glaucoma: {data.get('verified_glaucoma', 0)}")
            return True
        log_result("GET /admin/verification-stats", False, f"Status: {response.status_code}")
        return False
    except Exception as e:
        log_result("GET /admin/verification-stats", False, str(e))
        return False

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def run_all_tests():
    """Run all API tests"""
    print("=" * 70)
    print("🔬 GLAUCOMA DETECTION API - END-TO-END TEST SUITE")
    print(f"📍 Testing: {BASE_URL}")
    print(f"🕐 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()
    
    # Find or create test image
    global TEST_IMAGE_PATH
    TEST_IMAGE_PATH = find_test_image()
    if TEST_IMAGE_PATH:
        print(f"📸 Using test image: {TEST_IMAGE_PATH}")
    else:
        print("📸 No test image found, creating temporary one...")
        TEST_IMAGE_PATH = create_test_image()
    print()
    
    # ================== HEALTH & SYSTEM ==================
    print("─" * 50)
    print("📡 HEALTH & SYSTEM ENDPOINTS")
    print("─" * 50)
    test_root_endpoint()
    test_health_endpoint()
    test_docs_endpoint()
    test_metrics_endpoint()
    print()
    
    # ================== AUTHENTICATION ==================
    print("─" * 50)
    print("🔐 AUTHENTICATION ENDPOINTS")
    print("─" * 50)
    
    access_token = test_login_success()
    test_login_failure()
    test_unauthorized_access()
    
    if access_token:
        test_get_current_user(access_token)
    else:
        print("⚠️  Skipping auth-dependent tests (login failed)")
    print()
    
    # ================== PATIENT MANAGEMENT ==================
    print("─" * 50)
    print("🏥 PATIENT MANAGEMENT ENDPOINTS")
    print("─" * 50)
    
    patient_id = None
    if access_token:
        patient_id = test_create_patient(access_token)
        test_list_patients(access_token)
        
        if patient_id:
            test_get_patient(access_token, patient_id)
            test_update_patient(access_token, patient_id)
            test_patient_stats(access_token, patient_id)
    else:
        print("⚠️  Skipping patient tests (no auth token)")
    print()
    
    # ================== PREDICTIONS ==================
    print("─" * 50)
    print("🔬 PREDICTION ENDPOINTS")
    print("─" * 50)
    
    # Test predict-with-explanation (no auth needed)
    test_predict_with_explanation(TEST_IMAGE_PATH)
    
    # Test authenticated prediction
    if access_token and patient_id and TEST_IMAGE_PATH:
        test_predict(access_token, patient_id, TEST_IMAGE_PATH)
        test_patient_predictions(access_token, patient_id)
    else:
        print("⚠️  Skipping auth prediction (missing token/patient/image)")
    print()
    
    # ================== ADMIN VERIFICATION ==================
    print("─" * 50)
    print("👨‍⚕️ ADMIN VERIFICATION ENDPOINTS")
    print("─" * 50)
    
    if access_token:
        test_pending_images(access_token)
        test_verification_stats(access_token)
    else:
        print("⚠️  Skipping admin tests (no auth token)")
    print()
    
    # ================== SUMMARY ==================
    print("=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for r in test_results if r["passed"])
    failed = sum(1 for r in test_results if not r["passed"])
    total = len(test_results)
    
    print(f"   ✅ Passed: {passed}")
    print(f"   ❌ Failed: {failed}")
    print(f"   📋 Total:  {total}")
    print(f"   📈 Success Rate: {(passed/total*100):.1f}%" if total > 0 else "N/A")
    print()
    
    if failed > 0:
        print("❌ FAILED TESTS:")
        for r in test_results:
            if not r["passed"]:
                print(f"   - {r['test']}: {r['details']}")
        print()
    
    print("=" * 70)
    print(f"🏁 Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Cleanup temp image
    if TEST_IMAGE_PATH and TEST_IMAGE_PATH.startswith("test_image_temp"):
        try:
            os.remove(TEST_IMAGE_PATH)
        except:
            pass
    
    # Save results to JSON
    results_file = f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "base_url": BASE_URL,
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "success_rate": f"{(passed/total*100):.1f}%" if total > 0 else "N/A",
            "results": test_results
        }, f, indent=2)
    print(f"📄 Results saved to: {results_file}")
    
    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
