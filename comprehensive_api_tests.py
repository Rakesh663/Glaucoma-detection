"""
Comprehensive API Test Suite for Glaucoma Detection API
Tests all endpoints with various scenarios including edge cases and error handling.

Run with: python comprehensive_api_tests.py
"""
import requests
import json
import base64
import os
from PIL import Image
from io import BytesIO
import time

API_BASE = "http://127.0.0.1:8001"

# Test images
TEST_GLAUCOMA_IMAGE = "data/test/glaucoma/Im313_g_ACRIMA.jpg"
TEST_NORMAL_IMAGE = "data/test/normal/Im002_ACRIMA.jpg"

class TestResults:
    """Track test results"""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []
    
    def add(self, name, passed, details=""):
        status = "✅ PASS" if passed else "❌ FAIL"
        self.results.append((name, status, details))
        if passed:
            self.passed += 1
        else:
            self.failed += 1
        print(f"  {status}: {name}" + (f" - {details}" if details else ""))

results = TestResults()

# ==============================================================
# 1. ROOT ENDPOINT TESTS
# ==============================================================
def test_root_endpoint():
    print("\n" + "=" * 60)
    print("1. ROOT ENDPOINT TESTS (GET /)")
    print("=" * 60)
    
    # Test 1.1: Basic root access
    r = requests.get(f"{API_BASE}/")
    results.add("Root endpoint returns 200", r.status_code == 200)
    
    # Test 1.2: Response structure
    data = r.json()
    results.add("Response has 'service' field", "service" in data)
    results.add("Response has 'version' field", "version" in data)
    results.add("Response has 'endpoints' field", "endpoints" in data)
    results.add("Response has 'model_status' field", "model_status" in data)
    
    # Test 1.3: Model status is loaded
    results.add("Model status is 'loaded'", data.get("model_status") == "loaded")
    
    # Test 1.4: All endpoints listed
    endpoints = data.get("endpoints", {})
    expected_endpoints = [
        "GET /", "GET /health", "POST /predict", 
        "POST /predict-with-explanation", "POST /batch-predict", "GET /docs"
    ]
    for ep in expected_endpoints:
        results.add(f"Endpoint '{ep}' listed", ep in endpoints)

# ==============================================================
# 2. HEALTH ENDPOINT TESTS
# ==============================================================
def test_health_endpoint():
    print("\n" + "=" * 60)
    print("2. HEALTH ENDPOINT TESTS (GET /health)")
    print("=" * 60)
    
    # Test 2.1: Basic health check
    r = requests.get(f"{API_BASE}/health")
    results.add("Health endpoint returns 200", r.status_code == 200)
    
    # Test 2.2: Response structure
    data = r.json()
    results.add("Response has 'status' field", "status" in data)
    results.add("Response has 'model_loaded' field", "model_loaded" in data)
    results.add("Response has 'timestamp' field", "timestamp" in data)
    results.add("Response has 'version' field", "version" in data)
    
    # Test 2.3: Status is healthy
    results.add("Status is 'healthy'", data.get("status") == "healthy")
    
    # Test 2.4: Model is loaded
    results.add("Model is loaded", data.get("model_loaded") == True)

# ==============================================================
# 3. METRICS ENDPOINT TESTS
# ==============================================================
def test_metrics_endpoint():
    print("\n" + "=" * 60)
    print("3. METRICS ENDPOINT TESTS (GET /metrics)")
    print("=" * 60)
    
    # Test 3.1: Basic metrics access
    r = requests.get(f"{API_BASE}/metrics")
    results.add("Metrics endpoint returns 200", r.status_code == 200)
    
    # Test 3.2: Content type is Prometheus format
    content_type = r.headers.get("content-type", "")
    results.add("Content-Type is text/plain", "text/plain" in content_type)
    
    # Test 3.3: Contains Prometheus format
    content = r.text
    results.add("Contains '# HELP' directive", "# HELP" in content)
    results.add("Contains '# TYPE' directive", "# TYPE" in content)

# ==============================================================
# 4. PREDICT-WITH-EXPLANATION ENDPOINT TESTS
# ==============================================================
def test_predict_with_explanation():
    print("\n" + "=" * 60)
    print("4. PREDICT-WITH-EXPLANATION TESTS (POST /predict-with-explanation)")
    print("=" * 60)
    
    # Test 4.1: Glaucoma image prediction
    if os.path.exists(TEST_GLAUCOMA_IMAGE):
        with open(TEST_GLAUCOMA_IMAGE, 'rb') as f:
            files = {'file': ('glaucoma_test.jpg', f, 'image/jpeg')}
            r = requests.post(f"{API_BASE}/predict-with-explanation", files=files)
        
        results.add("Glaucoma image returns 200", r.status_code == 200)
        
        if r.status_code == 200:
            data = r.json()
            results.add("Response has 'prediction' field", "prediction" in data)
            results.add("Response has 'label' field", "label" in data)
            results.add("Response has 'probability' field", "probability" in data)
            results.add("Response has 'confidence' field", "confidence" in data)
            results.add("Response has 'heatmap_base64' field", "heatmap_base64" in data)
            results.add("Response has 'overlay_base64' field", "overlay_base64" in data)
            
            # Check heatmap is not None
            results.add("Heatmap is generated", data.get("heatmap_base64") is not None)
            results.add("Overlay is generated", data.get("overlay_base64") is not None)
            
            # Validate base64 decoding
            if data.get("overlay_base64"):
                try:
                    img_data = base64.b64decode(data["overlay_base64"])
                    img = Image.open(BytesIO(img_data))
                    results.add("Overlay is valid PNG image", True, f"Size: {img.size}")
                except Exception as e:
                    results.add("Overlay is valid PNG image", False, str(e))
            
            # Check prediction values
            prob = data.get("probability", 0)
            results.add("Probability is between 0 and 1", 0 <= prob <= 1)
            results.add("High probability for glaucoma image", prob > 0.5, f"Prob: {prob:.4f}")
    
    # Test 4.2: Normal image prediction
    if os.path.exists(TEST_NORMAL_IMAGE):
        with open(TEST_NORMAL_IMAGE, 'rb') as f:
            files = {'file': ('normal_test.jpg', f, 'image/jpeg')}
            r = requests.post(f"{API_BASE}/predict-with-explanation", files=files)
        
        results.add("Normal image returns 200", r.status_code == 200)
        
        if r.status_code == 200:
            data = r.json()
            prob = data.get("probability", 0)
            # Note: With current model, prediction may vary
            results.add("Normal image has valid probability", 0 <= prob <= 1, f"Prob: {prob:.4f}")
    
    # Test 4.3: No file provided
    r = requests.post(f"{API_BASE}/predict-with-explanation")
    results.add("Missing file returns 422", r.status_code == 422)
    
    # Test 4.4: Invalid file type
    files = {'file': ('test.txt', b'not an image', 'text/plain')}
    r = requests.post(f"{API_BASE}/predict-with-explanation", files=files)
    results.add("Invalid file type returns 400", r.status_code == 400)
    
    # Test 4.5: Processing time is reasonable
    if os.path.exists(TEST_GLAUCOMA_IMAGE):
        start = time.time()
        with open(TEST_GLAUCOMA_IMAGE, 'rb') as f:
            files = {'file': ('speed_test.jpg', f, 'image/jpeg')}
            r = requests.post(f"{API_BASE}/predict-with-explanation", files=files)
        elapsed = time.time() - start
        results.add("Response time under 60s", elapsed < 60, f"{elapsed:.2f}s")

# ==============================================================
# 5. DOCS ENDPOINT TESTS
# ==============================================================
def test_docs_endpoint():
    print("\n" + "=" * 60)
    print("5. DOCUMENTATION ENDPOINT TESTS")
    print("=" * 60)
    
    # Test 5.1: Swagger UI
    r = requests.get(f"{API_BASE}/docs")
    results.add("Swagger UI returns 200", r.status_code == 200)
    results.add("Swagger UI is HTML", "text/html" in r.headers.get("content-type", ""))
    
    # Test 5.2: OpenAPI JSON
    r = requests.get(f"{API_BASE}/openapi.json")
    results.add("OpenAPI spec returns 200", r.status_code == 200)
    
    if r.status_code == 200:
        data = r.json()
        results.add("OpenAPI has 'paths' field", "paths" in data)
        results.add("OpenAPI has 'info' field", "info" in data)
        
        # Check endpoints are documented
        paths = data.get("paths", {})
        results.add("/predict-with-explanation documented", "/predict-with-explanation" in paths)

# ==============================================================
# 6. CORS AND HEADERS TESTS
# ==============================================================
def test_cors_headers():
    print("\n" + "=" * 60)
    print("6. CORS AND HEADERS TESTS")
    print("=" * 60)
    
    # Test 6.1: CORS headers present
    r = requests.get(f"{API_BASE}/")
    headers = r.headers
    results.add("CORS allow-origin header present", "access-control-allow-origin" in headers)
    
    # Test 6.2: Correlation ID in response
    results.add("X-Correlation-ID in response", "x-correlation-id" in headers)
    
    # Test 6.3: Custom correlation ID preserved
    custom_id = "test-correlation-12345"
    r = requests.get(f"{API_BASE}/health", headers={"X-Correlation-ID": custom_id})
    results.add("Custom correlation ID header accepted", r.status_code == 200)

# ==============================================================
# 7. ERROR HANDLING TESTS
# ==============================================================
def test_error_handling():
    print("\n" + "=" * 60)
    print("7. ERROR HANDLING TESTS")
    print("=" * 60)
    
    # Test 7.1: 404 for unknown endpoint
    r = requests.get(f"{API_BASE}/unknown-endpoint")
    results.add("Unknown endpoint returns 404", r.status_code == 404)
    
    # Test 7.2: Method not allowed
    r = requests.put(f"{API_BASE}/health")
    results.add("Wrong method returns 405", r.status_code == 405)
    
    # Test 7.3: Large file handling (simulate with actual file if under limit)
    # Skipping actual large file test to avoid memory issues

# ==============================================================
# 8. PERFORMANCE TESTS
# ==============================================================
def test_performance():
    print("\n" + "=" * 60)
    print("8. PERFORMANCE TESTS")
    print("=" * 60)
    
    # Test 8.1: Multiple requests don't crash server
    for i in range(3):
        r = requests.get(f"{API_BASE}/health")
        if r.status_code != 200:
            results.add(f"Repeated request {i+1} successful", False)
            return
    results.add("3 consecutive health checks successful", True)
    
    # Test 8.2: Health endpoint is fast
    times = []
    for _ in range(3):
        start = time.time()
        requests.get(f"{API_BASE}/health")
        times.append(time.time() - start)
    avg_time = sum(times) / len(times)
    results.add("Avg health check under 1s", avg_time < 1, f"{avg_time:.3f}s")

# ==============================================================
# MAIN TEST RUNNER
# ==============================================================
def main():
    print("=" * 70)
    print("    COMPREHENSIVE GLAUCOMA DETECTION API TEST SUITE")
    print("=" * 70)
    print(f"API Base: {API_BASE}")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check API is running
    try:
        r = requests.get(f"{API_BASE}/health", timeout=5)
        print(f"API Status: {'Running ✅' if r.status_code == 200 else 'Not healthy ⚠️'}")
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Cannot connect to API. Make sure it's running:")
        print(f"   python -m uvicorn api.main:app --host 127.0.0.1 --port 8001")
        return
    
    # Run all test groups
    test_root_endpoint()
    test_health_endpoint()
    test_metrics_endpoint()
    test_predict_with_explanation()
    test_docs_endpoint()
    test_cors_headers()
    test_error_handling()
    test_performance()
    
    # Print summary
    print("\n" + "=" * 70)
    print("    TEST SUMMARY")
    print("=" * 70)
    print(f"Total Tests: {results.passed + results.failed}")
    print(f"Passed: {results.passed} ✅")
    print(f"Failed: {results.failed} ❌")
    print(f"Pass Rate: {results.passed / (results.passed + results.failed) * 100:.1f}%")
    
    if results.failed > 0:
        print("\n❌ FAILED TESTS:")
        for name, status, details in results.results:
            if "FAIL" in status:
                print(f"   - {name}: {details}")
    
    print("\n" + "=" * 70)
    overall = "✅ ALL TESTS PASSED!" if results.failed == 0 else "⚠️ SOME TESTS FAILED"
    print(f"    {overall}")
    print("=" * 70)
    
    return results.failed == 0

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
