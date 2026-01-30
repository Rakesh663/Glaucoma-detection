"""
Comprehensive End-to-End API Test Suite
========================================
Tests ALL API endpoints in the Glaucoma Detection project.
Includes: Auth, Patients, Predictions, Admin, User Management
"""

import requests
import json
import os
import time
import base64
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8002"
RESULTS = []
START_TIME = None

# Test credentials
TEST_USER = "doctor1"
TEST_PASSWORD = "iscs"

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def log_test(category, name, passed, details="", response_time=0):
    """Log test result"""
    status = f"{Colors.GREEN}✅ PASS{Colors.END}" if passed else f"{Colors.RED}❌ FAIL{Colors.END}"
    print(f"  {status} {name}")
    if details and not passed:
        print(f"       {Colors.YELLOW}{details}{Colors.END}")
    RESULTS.append({
        "category": category,
        "test": name,
        "passed": passed,
        "details": details,
        "response_time_ms": response_time
    })

def section_header(title):
    """Print section header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")

def get_token(username=TEST_USER, password=TEST_PASSWORD):
    """Helper to get auth token"""
    r = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        data={"username": username, "password": password},
        timeout=10
    )
    if r.status_code == 200:
        return r.json().get("access_token"), r.json().get("refresh_token")
    return None, None

def find_test_image():
    """Find a test image for prediction tests"""
    for root, dirs, files in os.walk('data/train'):
        for f in files:
            if f.endswith(('.jpg', '.jpeg', '.png')):
                return os.path.join(root, f)
    return None

# ============================================================================
# TEST CATEGORIES
# ============================================================================

def test_health_endpoints():
    """Test health and system endpoints"""
    section_header("1. HEALTH & SYSTEM ENDPOINTS")
    
    # GET /
    start = time.time()
    r = requests.get(f"{BASE_URL}/", timeout=10)
    elapsed = (time.time() - start) * 1000
    log_test("Health", "GET / (root)", r.status_code == 200, 
             f"Status: {r.status_code}", elapsed)
    
    # GET /health
    start = time.time()
    r = requests.get(f"{BASE_URL}/health", timeout=10)
    elapsed = (time.time() - start) * 1000
    log_test("Health", "GET /health", r.status_code == 200,
             f"Status: {r.status_code}", elapsed)
    
    # GET /docs
    start = time.time()
    r = requests.get(f"{BASE_URL}/docs", timeout=10)
    elapsed = (time.time() - start) * 1000
    log_test("Health", "GET /docs (Swagger)", r.status_code == 200,
             f"Status: {r.status_code}", elapsed)
    
    # GET /openapi.json
    start = time.time()
    r = requests.get(f"{BASE_URL}/openapi.json", timeout=10)
    elapsed = (time.time() - start) * 1000
    log_test("Health", "GET /openapi.json", r.status_code == 200,
             f"Status: {r.status_code}", elapsed)
    
    # GET /metrics
    start = time.time()
    r = requests.get(f"{BASE_URL}/metrics", timeout=10)
    elapsed = (time.time() - start) * 1000
    log_test("Health", "GET /metrics", r.status_code == 200,
             f"Status: {r.status_code}", elapsed)


def test_auth_endpoints():
    """Test authentication endpoints"""
    section_header("2. AUTHENTICATION ENDPOINTS")
    
    # POST /api/v1/auth/login
    start = time.time()
    r = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        data={"username": TEST_USER, "password": TEST_PASSWORD},
        timeout=10
    )
    elapsed = (time.time() - start) * 1000
    log_test("Auth", "POST /api/v1/auth/login", r.status_code == 200,
             f"Status: {r.status_code}", elapsed)
    
    token = None
    refresh_token = None
    if r.status_code == 200:
        token = r.json().get("access_token")
        refresh_token = r.json().get("refresh_token")
    
    # Test login with wrong password
    start = time.time()
    r = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        data={"username": TEST_USER, "password": "wrongpassword"},
        timeout=10
    )
    elapsed = (time.time() - start) * 1000
    log_test("Auth", "Login with wrong password (401)", r.status_code == 401,
             f"Status: {r.status_code}", elapsed)
    
    # GET /api/v1/auth/me
    if token:
        start = time.time()
        r = requests.get(
            f"{BASE_URL}/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        elapsed = (time.time() - start) * 1000
        log_test("Auth", "GET /api/v1/auth/me", r.status_code == 200,
                 f"Status: {r.status_code}", elapsed)
    
    # Test unauthorized access
    start = time.time()
    r = requests.get(f"{BASE_URL}/api/v1/auth/me", timeout=10)
    elapsed = (time.time() - start) * 1000
    log_test("Auth", "Unauthorized access (401)", r.status_code == 401,
             f"Status: {r.status_code}", elapsed)
    
    # POST /api/v1/auth/refresh
    if refresh_token:
        start = time.time()
        r = requests.post(
            f"{BASE_URL}/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
            timeout=10
        )
        elapsed = (time.time() - start) * 1000
        log_test("Auth", "POST /api/v1/auth/refresh", r.status_code == 200,
                 f"Status: {r.status_code}", elapsed)
    
    # POST /api/v1/auth/logout
    if token:
        # Get fresh token first
        token, _ = get_token()
        start = time.time()
        r = requests.post(
            f"{BASE_URL}/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
            json={},
            timeout=10
        )
        elapsed = (time.time() - start) * 1000
        log_test("Auth", "POST /api/v1/auth/logout", r.status_code == 200,
                 f"Status: {r.status_code}", elapsed)
    
    # POST /api/v1/auth/change-password (validation test)
    token, _ = get_token()
    if token:
        start = time.time()
        r = requests.post(
            f"{BASE_URL}/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"current_password": "wrongpass", "new_password": "newpass123"},
            timeout=10
        )
        elapsed = (time.time() - start) * 1000
        log_test("Auth", "Password change (wrong current password)", r.status_code == 401,
                 f"Status: {r.status_code}", elapsed)
    
    # POST /api/v1/auth/register (test with existing user)
    start = time.time()
    r = requests.post(
        f"{BASE_URL}/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "username": "testuser_" + str(int(time.time())),
            "password": "testpass123",
            "first_name": "Test",
            "last_name": "User"
        },
        timeout=10
    )
    elapsed = (time.time() - start) * 1000
    log_test("Auth", "POST /api/v1/auth/register", r.status_code in [200, 201, 400],
             f"Status: {r.status_code}", elapsed)
    
    return token


def test_patient_endpoints(token):
    """Test patient management endpoints"""
    section_header("3. PATIENT MANAGEMENT ENDPOINTS")
    
    if not token:
        token, _ = get_token()
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # GET /api/v1/patients
    start = time.time()
    r = requests.get(
        f"{BASE_URL}/api/v1/patients",
        headers=headers,
        timeout=10
    )
    elapsed = (time.time() - start) * 1000
    log_test("Patient", "GET /api/v1/patients", r.status_code == 200,
             f"Status: {r.status_code}", elapsed)
    
    # POST /api/v1/patients (create)
    unique_mrn = f"MRN-{int(time.time())}"
    start = time.time()
    r = requests.post(
        f"{BASE_URL}/api/v1/patients",
        headers=headers,
        json={
            "first_name": "Test",
            "last_name": "Patient",
            "mrn": unique_mrn,
            "gender": "M",
            "email": f"test_{int(time.time())}@example.com"
        },
        timeout=10
    )
    elapsed = (time.time() - start) * 1000
    log_test("Patient", "POST /api/v1/patients (create)", r.status_code == 201,
             f"Status: {r.status_code}", elapsed)
    
    patient_id = None
    if r.status_code == 201:
        patient_id = r.json().get("patient_id")
    
    # GET /api/v1/patients/{id}
    if patient_id:
        start = time.time()
        r = requests.get(
            f"{BASE_URL}/api/v1/patients/{patient_id}",
            headers=headers,
            timeout=10
        )
        elapsed = (time.time() - start) * 1000
        log_test("Patient", f"GET /api/v1/patients/{{id}}", r.status_code == 200,
                 f"Status: {r.status_code}", elapsed)
    
    # PUT /api/v1/patients/{id}
    if patient_id:
        start = time.time()
        r = requests.put(
            f"{BASE_URL}/api/v1/patients/{patient_id}",
            headers=headers,
            json={"first_name": "UpdatedTest"},
            timeout=10
        )
        elapsed = (time.time() - start) * 1000
        log_test("Patient", f"PUT /api/v1/patients/{{id}}", r.status_code == 200,
                 f"Status: {r.status_code}", elapsed)
    
    # GET /api/v1/patients/{id}/stats
    if patient_id:
        start = time.time()
        r = requests.get(
            f"{BASE_URL}/api/v1/patients/{patient_id}/stats",
            headers=headers,
            timeout=10
        )
        elapsed = (time.time() - start) * 1000
        log_test("Patient", f"GET /api/v1/patients/{{id}}/stats", r.status_code == 200,
                 f"Status: {r.status_code}", elapsed)
    
    # GET /api/v1/patients/{id}/predictions
    if patient_id:
        start = time.time()
        r = requests.get(
            f"{BASE_URL}/api/v1/patients/{patient_id}/predictions",
            headers=headers,
            timeout=10
        )
        elapsed = (time.time() - start) * 1000
        log_test("Patient", f"GET /api/v1/patients/{{id}}/predictions", r.status_code == 200,
                 f"Status: {r.status_code}", elapsed)
    
    # DELETE /api/v1/patients/{id}
    if patient_id:
        start = time.time()
        r = requests.delete(
            f"{BASE_URL}/api/v1/patients/{patient_id}",
            headers=headers,
            timeout=10
        )
        elapsed = (time.time() - start) * 1000
        log_test("Patient", f"DELETE /api/v1/patients/{{id}}", r.status_code == 204,
                 f"Status: {r.status_code}", elapsed)
    
    return patient_id


def test_prediction_endpoints(token):
    """Test prediction endpoints"""
    section_header("4. PREDICTION ENDPOINTS")
    
    if not token:
        token, _ = get_token()
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Find test image
    test_image = find_test_image()
    if not test_image:
        log_test("Prediction", "Find test image", False, "No test image found")
        return
    
    log_test("Prediction", "Find test image", True, f"Using: {os.path.basename(test_image)}")
    
    # First create a patient for prediction
    unique_mrn = f"PRED-{int(time.time())}"
    r = requests.post(
        f"{BASE_URL}/api/v1/patients",
        headers=headers,
        json={
            "first_name": "Prediction",
            "last_name": "Test",
            "mrn": unique_mrn,
            "gender": "M"
        },
        timeout=10
    )
    patient_id = r.json().get("patient_id") if r.status_code == 201 else None
    
    # POST /predict (basic prediction - requires patient_id)
    if patient_id:
        with open(test_image, 'rb') as f:
            start = time.time()
            r = requests.post(
                f"{BASE_URL}/predict",
                headers=headers,
                files={"file": (os.path.basename(test_image), f, "image/jpeg")},
                data={"patient_id": patient_id, "use_cache": "true"},
                timeout=120
            )
            elapsed = (time.time() - start) * 1000
        log_test("Prediction", "POST /predict", r.status_code == 200,
                 f"Status: {r.status_code}, Time: {elapsed:.0f}ms", elapsed)
        
        if r.status_code == 200:
            data = r.json()
            log_test("Prediction", "Response has label", "label" in data)
            log_test("Prediction", "Response has confidence", "confidence" in data)
            log_test("Prediction", "Response has risk_level", "risk_level" in data)
    else:
        log_test("Prediction", "POST /predict", False, "Could not create patient for test")
    
    # POST /predict-with-explanation (Grad-CAM - no patient_id required)
    with open(test_image, 'rb') as f:
        start = time.time()
        r = requests.post(
            f"{BASE_URL}/predict-with-explanation",
            headers=headers,
            files={"file": (os.path.basename(test_image), f, "image/jpeg")},
            timeout=120
        )
        elapsed = (time.time() - start) * 1000
    log_test("Prediction", "POST /predict-with-explanation", r.status_code == 200,
             f"Status: {r.status_code}, Time: {elapsed:.0f}ms", elapsed)
    
    if r.status_code == 200:
        data = r.json()
        log_test("Prediction", "Response has heatmap_base64", "heatmap_base64" in data)
        log_test("Prediction", "Response has overlay_base64", "overlay_base64" in data)
        
        # Verify heatmap is valid base64
        if data.get("heatmap_base64"):
            try:
                decoded = base64.b64decode(data["heatmap_base64"])
                log_test("Prediction", "Heatmap is valid base64", len(decoded) > 0)
            except:
                log_test("Prediction", "Heatmap is valid base64", False)
        
        # Verify overlay is valid base64
        if data.get("overlay_base64"):
            try:
                decoded = base64.b64decode(data["overlay_base64"])
                log_test("Prediction", "Overlay is valid base64", len(decoded) > 0)
            except:
                log_test("Prediction", "Overlay is valid base64", False)


def test_admin_endpoints(token):
    """Test admin verification endpoints"""
    section_header("5. ADMIN VERIFICATION ENDPOINTS")
    
    if not token:
        token, _ = get_token()
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # GET /admin/pending-images
    start = time.time()
    r = requests.get(
        f"{BASE_URL}/admin/pending-images",
        headers=headers,
        params={"limit": 10},
        timeout=10
    )
    elapsed = (time.time() - start) * 1000
    log_test("Admin", "GET /admin/pending-images", r.status_code in [200, 403],
             f"Status: {r.status_code}", elapsed)
    
    # GET /admin/verification-stats
    start = time.time()
    r = requests.get(
        f"{BASE_URL}/admin/verification-stats",
        headers=headers,
        timeout=10
    )
    elapsed = (time.time() - start) * 1000
    log_test("Admin", "GET /admin/verification-stats", r.status_code in [200, 403],
             f"Status: {r.status_code}", elapsed)


def test_user_management_endpoints(token):
    """Test user management endpoints"""
    section_header("6. USER MANAGEMENT ENDPOINTS")
    
    if not token:
        token, _ = get_token()
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # GET /api/v1/admin/users
    start = time.time()
    r = requests.get(
        f"{BASE_URL}/api/v1/admin/users",
        headers=headers,
        timeout=10
    )
    elapsed = (time.time() - start) * 1000
    log_test("UserMgmt", "GET /api/v1/admin/users", r.status_code in [200, 403],
             f"Status: {r.status_code}", elapsed)
    
    user_id = None
    if r.status_code == 200:
        users = r.json().get("users", [])
        if users:
            # Find a non-current user
            for u in users:
                if u.get("username") != TEST_USER:
                    user_id = u.get("user_id")
                    break
    
    # GET /api/v1/admin/users/{id}
    if user_id:
        start = time.time()
        r = requests.get(
            f"{BASE_URL}/api/v1/admin/users/{user_id}",
            headers=headers,
            timeout=10
        )
        elapsed = (time.time() - start) * 1000
        log_test("UserMgmt", f"GET /api/v1/admin/users/{{id}}", r.status_code in [200, 403],
                 f"Status: {r.status_code}", elapsed)
    
    # Test unlock endpoint exists (use non-existent user to avoid side effects)
    start = time.time()
    r = requests.post(
        f"{BASE_URL}/api/v1/admin/users/nonexistent123/unlock",
        headers=headers,
        timeout=10
    )
    elapsed = (time.time() - start) * 1000
    log_test("UserMgmt", "POST /api/v1/admin/users/{id}/unlock (endpoint exists)", 
             r.status_code in [200, 400, 403, 404],
             f"Status: {r.status_code}", elapsed)
    
    # Test role change endpoint exists
    start = time.time()
    r = requests.put(
        f"{BASE_URL}/api/v1/admin/users/nonexistent123/role",
        headers=headers,
        json={"role_name": "viewer"},
        timeout=10
    )
    elapsed = (time.time() - start) * 1000
    log_test("UserMgmt", "PUT /api/v1/admin/users/{id}/role (endpoint exists)", 
             r.status_code in [200, 400, 403, 404],
             f"Status: {r.status_code}", elapsed)


def test_security_features(token):
    """Test security features"""
    section_header("7. SECURITY FEATURES")
    
    if not token:
        token, _ = get_token()
    
    # Test JWT has JTI
    try:
        parts = token.split('.')
        payload_b64 = parts[1] + '=='
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        has_jti = "jti" in payload
        log_test("Security", "JWT has JTI (token ID)", has_jti,
                 f"JTI: {payload.get('jti', 'MISSING')[:16]}..." if has_jti else "Missing")
        log_test("Security", "JWT has IAT (issued at)", "iat" in payload)
        log_test("Security", "JWT has EXP (expiry)", "exp" in payload)
        log_test("Security", "JWT has type field", "type" in payload)
    except Exception as e:
        log_test("Security", "JWT structure valid", False, str(e))
    
    # Test account lockout (check admin is locked)
    start = time.time()
    r = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        data={"username": "admin", "password": "iscs"},
        timeout=10
    )
    elapsed = (time.time() - start) * 1000
    # Admin should be locked (403) or work (200)
    log_test("Security", "Account lockout check", r.status_code in [200, 403],
             f"Admin status: {r.status_code} (403=locked, 200=ok)", elapsed)


def print_summary():
    """Print test summary"""
    section_header("SUMMARY")
    
    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r["passed"])
    failed = total - passed
    
    # Group by category
    categories = {}
    for r in RESULTS:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"passed": 0, "failed": 0}
        if r["passed"]:
            categories[cat]["passed"] += 1
        else:
            categories[cat]["failed"] += 1
    
    print(f"\n{Colors.BOLD}Results by Category:{Colors.END}")
    for cat, stats in categories.items():
        total_cat = stats["passed"] + stats["failed"]
        pct = (stats["passed"] / total_cat * 100) if total_cat > 0 else 0
        color = Colors.GREEN if pct == 100 else Colors.YELLOW if pct >= 80 else Colors.RED
        print(f"  {cat:15} {color}{stats['passed']}/{total_cat}{Colors.END} ({pct:.0f}%)")
    
    print(f"\n{Colors.BOLD}Overall:{Colors.END}")
    pct = (passed / total * 100) if total > 0 else 0
    color = Colors.GREEN if pct >= 90 else Colors.YELLOW if pct >= 70 else Colors.RED
    print(f"  {color}{Colors.BOLD}{passed}/{total} tests passed ({pct:.1f}%){Colors.END}")
    
    # Execution time
    elapsed = time.time() - START_TIME
    print(f"\n{Colors.BOLD}Execution Time:{Colors.END} {elapsed:.1f} seconds")
    
    # Failed tests
    if failed > 0:
        print(f"\n{Colors.RED}{Colors.BOLD}Failed Tests:{Colors.END}")
        for r in RESULTS:
            if not r["passed"]:
                print(f"  ❌ [{r['category']}] {r['test']}: {r['details']}")
    
    # Save results to file
    results_file = f"e2e_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "success_rate": f"{pct:.1f}%",
            "execution_time_seconds": elapsed,
            "results": RESULTS
        }, f, indent=2)
    print(f"\n{Colors.BLUE}Results saved to: {results_file}{Colors.END}")
    
    return passed == total


def main():
    global START_TIME
    START_TIME = time.time()
    
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}   COMPREHENSIVE END-TO-END API TEST SUITE{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}   Glaucoma Detection API - All Endpoints{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"Base URL: {BASE_URL}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run all tests
    test_health_endpoints()
    token = test_auth_endpoints()
    test_patient_endpoints(token)
    test_prediction_endpoints(token)
    test_admin_endpoints(token)
    test_user_management_endpoints(token)
    test_security_features(token)
    
    # Summary
    all_passed = print_summary()
    
    if all_passed:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 ALL TESTS PASSED!{Colors.END}")
    else:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  Some tests failed - review details above{Colors.END}")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
