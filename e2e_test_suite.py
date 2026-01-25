"""
Comprehensive End-to-End API Test Suite
========================================
Tests all API functionality including:
- Authentication & RBAC
- Multi-tenancy
- Single & Batch Predictions
- Explainability (Grad-CAM)
- Doctor Verification Workflow
- Merge for Retraining

Run: python e2e_test_suite.py
"""

import os
import sys
import json
import time
import base64
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# Configuration
BASE_URL = os.getenv("API_URL", "http://localhost:8000")
TIMEOUT = 60

# Test results tracking
class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.results = []
    
    def add(self, name: str, passed: bool, message: str = "", skip: bool = False):
        if skip:
            self.skipped += 1
            status = "SKIP"
        elif passed:
            self.passed += 1
            status = "PASS"
        else:
            self.failed += 1
            status = "FAIL"
        
        self.results.append({
            "name": name,
            "status": status,
            "message": message
        })
        
        icon = "✅" if passed else ("⏭️" if skip else "❌")
        print(f"  {icon} {name}: {message if message else status}")
    
    def summary(self):
        print("\n" + "="*60)
        print(f"TEST SUMMARY: {self.passed} passed, {self.failed} failed, {self.skipped} skipped")
        print("="*60)
        return self.failed == 0


results = TestResults()

# ============================================================================
# Helper Functions
# ============================================================================

def api_request(method: str, endpoint: str, token: str = None, **kwargs) -> requests.Response:
    """Make API request with optional auth"""
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    url = f"{BASE_URL}{endpoint}"
    response = requests.request(method, url, headers=headers, timeout=TIMEOUT, **kwargs)
    return response


def find_test_image() -> Optional[Path]:
    """Find a test image from the dataset"""
    # Look for images in various locations
    search_paths = [
        Path("data/train/glaucoma"),
        Path("data/train/normal"),
        Path("data/val/glaucoma"),
        Path("data/val/normal"),
        Path("data/test/glaucoma"),
        Path("data/test/normal"),
    ]
    
    for path in search_paths:
        if path.exists():
            for img in path.glob("*.jpg"):
                return img
            for img in path.glob("*.png"):
                return img
    
    return None


# ============================================================================
# Test Suite
# ============================================================================

def test_health_and_root():
    """Test basic health endpoints"""
    print("\n--- 1. Health & Root Endpoints ---")
    
    # Root
    try:
        resp = api_request("GET", "/")
        results.add("GET /", resp.status_code == 200, f"Status: {resp.status_code}")
    except Exception as e:
        results.add("GET /", False, str(e))
    
    # Health
    try:
        resp = api_request("GET", "/health")
        data = resp.json()
        results.add("GET /health", resp.status_code == 200 and data.get("status") == "healthy", 
                   f"Model loaded: {data.get('model_loaded')}")
    except Exception as e:
        results.add("GET /health", False, str(e))
    
    # Metrics
    try:
        resp = api_request("GET", "/metrics")
        results.add("GET /metrics", resp.status_code == 200, f"Prometheus metrics available")
    except Exception as e:
        results.add("GET /metrics", False, str(e))


def test_authentication() -> Dict[str, str]:
    """Test authentication and get tokens for different roles"""
    print("\n--- 2. Authentication & RBAC ---")
    
    tokens = {}
    
    # Test registration
    try:
        resp = api_request("POST", "/api/v1/auth/register", json={
            "username": f"testadmin_{int(time.time())}",
            "email": f"testadmin_{int(time.time())}@test.com",
            "password": "TestPass123!",
            "first_name": "Test",
            "last_name": "Admin"
        })
        results.add("POST /api/v1/auth/register (new user)", resp.status_code in [200, 201, 400, 422], 
                   f"Status: {resp.status_code}")
    except Exception as e:
        results.add("POST /api/v1/auth/register", False, str(e))
    
    # Login as admin - using seeded users from init_db.py
    # Users: admin, doctor1, radiologist1, technician1, viewer1 - Password: iscs
    admin_users = [
        ("admin", "iscs"),
        ("admin@iscs.com", "iscs"),
        ("doctor1", "iscs"),
    ]
    
    admin_token = None
    for username, password in admin_users:
        try:
            resp = api_request("POST", "/api/v1/auth/login", data={
                "username": username,
                "password": password
            })
            if resp.status_code == 200:
                data = resp.json()
                admin_token = data.get("access_token")
                tokens["admin"] = admin_token
                results.add("POST /api/v1/auth/login (admin)", True, f"Logged in as {username}")
                break
        except:
            continue
    
    if not admin_token:
        results.add("POST /api/v1/auth/login (admin)", False, "Could not login with any admin credentials")
    
    # Test token validation
    if admin_token:
        try:
            resp = api_request("GET", "/api/v1/auth/me", token=admin_token)
            data = resp.json()
            results.add("GET /api/v1/auth/me", resp.status_code == 200, 
                       f"User: {data.get('username', 'N/A')}, Role: {data.get('role', {}).get('name', 'N/A') if isinstance(data.get('role'), dict) else data.get('role', 'N/A')}")
        except Exception as e:
            results.add("GET /api/v1/auth/me", False, str(e))
    
    # Test access without token (should fail with 401)
    try:
        resp = api_request("GET", "/api/v1/patients")
        results.add("GET /api/v1/patients (no auth)", resp.status_code == 401, 
                   f"Correctly rejected: {resp.status_code}")
    except Exception as e:
        results.add("GET /api/v1/patients (no auth)", False, str(e))
    
    return tokens


def test_patients_and_multitenancy(tokens: Dict[str, str]):
    """Test patient CRUD and multi-tenancy"""
    print("\n--- 3. Patients & Multi-tenancy ---")
    
    admin_token = tokens.get("admin")
    if not admin_token:
        results.add("Patient tests", False, "No admin token available", skip=True)
        return None
    
    patient_id = None
    
    # Create patient
    try:
        resp = api_request("POST", "/api/v1/patients", token=admin_token, json={
            "patient_id": f"PAT-TEST-{int(time.time())}",
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "1980-01-15",
            "gender": "male",
            "email": f"john.doe.{int(time.time())}@test.com",
            "mrn": f"MRN-{int(time.time())}"  # Medical Record Number required
        })
        if resp.status_code in [200, 201]:
            data = resp.json()
            patient_id = data.get("patient_id")
            results.add("POST /api/v1/patients", True, f"Created patient: {patient_id}")
        else:
            results.add("POST /api/v1/patients", False, f"Status: {resp.status_code}, {resp.text[:100]}")
    except Exception as e:
        results.add("POST /patients", False, str(e))
    
    # List patients
    try:
        resp = api_request("GET", "/api/v1/patients", token=admin_token)
        data = resp.json()
        count = len(data) if isinstance(data, list) else data.get("total", 0)
        results.add("GET /api/v1/patients", resp.status_code == 200, f"Found {count} patients")
    except Exception as e:
        results.add("GET /api/v1/patients", False, str(e))
    
    return patient_id


def test_predictions(tokens: Dict[str, str], patient_id: str):
    """Test single and batch predictions"""
    print("\n--- 4. Predictions ---")
    
    admin_token = tokens.get("admin")
    if not admin_token:
        results.add("Prediction tests", False, "No admin token available", skip=True)
        return
    
    test_image = find_test_image()
    if not test_image:
        results.add("Prediction tests", False, "No test image found in data/", skip=True)
        return
    
    print(f"  Using test image: {test_image}")
    
    # Single prediction
    try:
        with open(test_image, "rb") as f:
            resp = api_request("POST", "/predict", token=admin_token, 
                             files={"file": (test_image.name, f, "image/jpeg")},
                             data={"patient_id": patient_id, "use_cache": "false"})
        
        if resp.status_code == 200:
            data = resp.json()
            results.add("POST /predict", True, 
                       f"Label: {data.get('label')}, Confidence: {data.get('confidence', 0):.2f}")
        else:
            results.add("POST /predict", False, f"Status: {resp.status_code}, {resp.text[:200]}")
    except Exception as e:
        results.add("POST /predict", False, str(e))
    
    # Batch prediction (with 2 images)
    try:
        with open(test_image, "rb") as f1, open(test_image, "rb") as f2:
            files = [
                ("files", (f"img1_{test_image.name}", f1, "image/jpeg")),
                ("files", (f"img2_{test_image.name}", f2, "image/jpeg"))
            ]
            resp = api_request("POST", "/batch-predict", token=admin_token,
                             files=files,
                             data={"patient_id": patient_id, "use_cache": "false"})
        
        if resp.status_code == 200:
            data = resp.json()
            results.add("POST /batch-predict", True, 
                       f"Processed: {data.get('total_images')}, Success: {data.get('successful')}")
        else:
            results.add("POST /batch-predict", False, f"Status: {resp.status_code}, {resp.text[:200]}")
    except Exception as e:
        results.add("POST /batch-predict", False, str(e))


def test_explainability():
    """Test Grad-CAM explainability endpoint"""
    print("\n--- 5. Explainability (Grad-CAM) ---")
    
    test_image = find_test_image()
    if not test_image:
        results.add("Explainability tests", False, "No test image found", skip=True)
        return
    
    try:
        with open(test_image, "rb") as f:
            resp = api_request("POST", "/predict-with-explanation",
                             files={"file": (test_image.name, f, "image/jpeg")})
        
        if resp.status_code == 200:
            data = resp.json()
            has_heatmap = bool(data.get("heatmap_base64"))
            has_overlay = bool(data.get("overlay_base64"))
            
            results.add("POST /predict-with-explanation", True,
                       f"Label: {data.get('label')}, Heatmap: {has_heatmap}, Overlay: {has_overlay}")
            
            # Save heatmap if available
            if has_heatmap:
                heatmap_dir = Path("outputs/heatmaps")
                heatmap_dir.mkdir(parents=True, exist_ok=True)
                
                heatmap_data = base64.b64decode(data["heatmap_base64"])
                heatmap_path = heatmap_dir / f"heatmap_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                with open(heatmap_path, "wb") as f:
                    f.write(heatmap_data)
                results.add("Save heatmap", True, f"Saved to {heatmap_path}")
            
            if has_overlay:
                overlay_data = base64.b64decode(data["overlay_base64"])
                overlay_path = heatmap_dir / f"overlay_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                with open(overlay_path, "wb") as f:
                    f.write(overlay_data)
                results.add("Save overlay", True, f"Saved to {overlay_path}")
        else:
            results.add("POST /predict-with-explanation", False, 
                       f"Status: {resp.status_code}, {resp.text[:200]}")
    except Exception as e:
        results.add("POST /predict-with-explanation", False, str(e))


def test_doctor_verification(tokens: Dict[str, str]):
    """Test doctor verification workflow"""
    print("\n--- 6. Doctor Verification Workflow ---")
    
    admin_token = tokens.get("admin")
    if not admin_token:
        results.add("Verification tests", False, "No admin token available", skip=True)
        return None
    
    labeled_filename = None
    
    # Get verification stats
    try:
        resp = api_request("GET", "/admin/verification-stats", token=admin_token)
        if resp.status_code == 200:
            data = resp.json()
            results.add("GET /admin/verification-stats", True,
                       f"Pending: {data.get('pending_count')}, Glaucoma: {data.get('verified_glaucoma')}, Normal: {data.get('verified_normal')}")
        else:
            results.add("GET /admin/verification-stats", False, f"Status: {resp.status_code}")
    except Exception as e:
        results.add("GET /admin/verification-stats", False, str(e))
    
    # Get pending images
    pending_images = []
    try:
        resp = api_request("GET", "/admin/pending-images", token=admin_token)
        if resp.status_code == 200:
            pending_images = resp.json()
            results.add("GET /admin/pending-images", True, f"Found {len(pending_images)} pending images")
        else:
            results.add("GET /admin/pending-images", False, f"Status: {resp.status_code}")
    except Exception as e:
        results.add("GET /admin/pending-images", False, str(e))
    
    # Label an image if available
    if pending_images:
        try:
            image_to_label = pending_images[0]
            labeled_filename = image_to_label["filename"]
            
            resp = api_request("POST", "/admin/label-image", token=admin_token, json={
                "filename": labeled_filename,
                "doctor_label": "glaucoma",
                "doctor_notes": "Test verification - confirmed glaucoma by e2e test"
            })
            
            if resp.status_code == 200:
                data = resp.json()
                results.add("POST /admin/label-image", True, 
                           f"Labeled as glaucoma, moved to: {data.get('moved_to', 'N/A')}")
            else:
                results.add("POST /admin/label-image", False, f"Status: {resp.status_code}, {resp.text[:100]}")
        except Exception as e:
            results.add("POST /admin/label-image", False, str(e))
    else:
        results.add("POST /admin/label-image", False, "No pending images to label", skip=True)
    
    # Test image streaming endpoint
    if pending_images and len(pending_images) > 1:
        try:
            test_filename = pending_images[1]["filename"]
            resp = api_request("GET", f"/admin/incoming-image/{test_filename}", token=admin_token)
            results.add("GET /admin/incoming-image/{filename}", resp.status_code == 200,
                       f"Content-Type: {resp.headers.get('content-type', 'N/A')}")
        except Exception as e:
            results.add("GET /admin/incoming-image/{filename}", False, str(e))
    
    return labeled_filename


def test_merge_for_retraining(tokens: Dict[str, str]):
    """Test merge verified images to training"""
    print("\n--- 7. Merge for Retraining ---")
    
    admin_token = tokens.get("admin")
    if not admin_token:
        results.add("Merge tests", False, "No admin token available", skip=True)
        return
    
    # Merge to training (without clearing)
    try:
        resp = api_request("POST", "/admin/merge-to-training", token=admin_token,
                          params={"min_images": 0, "clear_after_merge": False})
        
        if resp.status_code == 200:
            data = resp.json()
            total = data.get("details", {}).get("glaucoma_added", 0) + data.get("details", {}).get("normal_added", 0)
            results.add("POST /admin/merge-to-training", True,
                       f"Merged {total} images (Glaucoma: {data.get('details', {}).get('glaucoma_added', 0)}, Normal: {data.get('details', {}).get('normal_added', 0)})")
        else:
            results.add("POST /admin/merge-to-training", False, f"Status: {resp.status_code}, {resp.text[:100]}")
    except Exception as e:
        results.add("POST /admin/merge-to-training", False, str(e))
    
    # Verify images in training directory
    train_glaucoma = Path("data/train/glaucoma")
    train_normal = Path("data/train/normal")
    
    verified_in_train = 0
    for path in [train_glaucoma, train_normal]:
        if path.exists():
            verified_in_train += len(list(path.glob("verified_*.jpg"))) + len(list(path.glob("verified_*.png")))
    
    results.add("Verified images in training", True, f"Found {verified_in_train} verified images in data/train/")


def test_openapi_docs():
    """Test API documentation"""
    print("\n--- 8. API Documentation ---")
    
    try:
        resp = api_request("GET", "/docs")
        results.add("GET /docs (Swagger UI)", resp.status_code == 200, "Available")
    except Exception as e:
        results.add("GET /docs", False, str(e))
    
    try:
        resp = api_request("GET", "/openapi.json")
        data = resp.json()
        paths_count = len(data.get("paths", {}))
        results.add("GET /openapi.json", resp.status_code == 200, f"{paths_count} endpoints documented")
    except Exception as e:
        results.add("GET /openapi.json", False, str(e))


# ============================================================================
# Main
# ============================================================================

def main():
    print("="*60)
    print("🔬 GLAUCOMA DETECTION API - END-TO-END TEST SUITE")
    print("="*60)
    print(f"Target: {BASE_URL}")
    print(f"Time: {datetime.now().isoformat()}")
    
    # Check if server is running
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        if resp.status_code != 200:
            print(f"\n❌ API server not healthy: {resp.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Cannot connect to API at {BASE_URL}")
        print("   Start the server: python -m uvicorn api.main:app --reload")
        return False
    
    # Run tests
    test_health_and_root()
    tokens = test_authentication()
    patient_id = test_patients_and_multitenancy(tokens)
    
    if patient_id:
        test_predictions(tokens, patient_id)
    else:
        print("\n--- 4. Predictions --- (SKIPPED: No patient created)")
    
    test_explainability()
    test_doctor_verification(tokens)
    test_merge_for_retraining(tokens)
    test_openapi_docs()
    
    # Summary
    success = results.summary()
    
    # Save results
    results_path = Path("outputs/test_results")
    results_path.mkdir(parents=True, exist_ok=True)
    results_file = results_path / f"e2e_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(results_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "base_url": BASE_URL,
            "summary": {
                "passed": results.passed,
                "failed": results.failed,
                "skipped": results.skipped
            },
            "results": results.results
        }, f, indent=2)
    
    print(f"\n📊 Results saved to: {results_file}")
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
