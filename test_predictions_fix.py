"""
Test script to verify the patient predictions endpoint fix
"""
import requests

BASE_URL = "http://localhost:8000"

# Login as admin
print("Logging in as admin...")
login = requests.post(
    f"{BASE_URL}/api/v1/auth/login",
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    data={"username": "admin", "password": "iscs"}
)

if login.status_code != 200:
    print(f"[FAIL] Login failed: {login.status_code}")
    print(login.text)
    exit(1)

token = login.json()["access_token"]
print("[PASS] Login successful")

# Create a test patient first
print("\nCreating test patient...")
patient_data = {
    "first_name": "Test",
    "last_name": "Patient",
    "mrn": f"MRN-TEST-{requests.get('https://httpbin.org/uuid').json()['uuid'][:8]}",
    "date_of_birth": "1990-01-01T00:00:00",
    "gender": "M"
}

create_response = requests.post(
    f"{BASE_URL}/api/v1/patients",
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    json=patient_data
)

if create_response.status_code != 201:
    print(f"[FAIL] Patient creation failed: {create_response.status_code}")
    print(create_response.text)
    exit(1)

patient = create_response.json()
patient_id = patient["patient_id"]
print(f"[PASS] Patient created: {patient_id}")

# Test GET /api/v1/patients/{patient_id} endpoint
print(f"\nTesting GET /api/v1/patients/{patient_id}...")
get_response = requests.get(
    f"{BASE_URL}/api/v1/patients/{patient_id}",
    headers={"Authorization": f"Bearer {token}"}
)

print(f"Status Code: {get_response.status_code}")
if get_response.status_code == 200:
    print("[PASS] GET patient endpoint works!")
    data = get_response.json()
    print(f"Predictions: {data.get('predictions', [])}")
    print(f"Total Predictions: {data.get('total_predictions', 0)}")
else:
    print(f"[FAIL] GET patient failed: {get_response.status_code}")
    print(get_response.text)

# Test GET /api/v1/patients/{patient_id}/predictions endpoint
print(f"\nTesting GET /api/v1/patients/{patient_id}/predictions...")
predictions_response = requests.get(
    f"{BASE_URL}/api/v1/patients/{patient_id}/predictions",
    headers={"Authorization": f"Bearer {token}"}
)

print(f"Status Code: {predictions_response.status_code}")
if predictions_response.status_code == 200:
    print("[PASS] GET patient predictions endpoint works!")
    data = predictions_response.json()
    print(f"Total: {data.get('total', 0)}")
    print(f"Predictions: {data.get('predictions', [])}")
else:
    print(f"[FAIL] GET patient predictions failed: {predictions_response.status_code}")
    print(predictions_response.text)

print("\n" + "="*60)
print("Test completed!")
