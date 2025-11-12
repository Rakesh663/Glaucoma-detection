#!/usr/bin/env python3
"""
Test script for Patient APIs
Tests all 7 patient endpoints
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def print_test(name, status):
    symbol = "[PASS]" if status else "[FAIL]"
    print(f"{symbol} {name}")

# Step 1: Login
print("\n" + "="*60)
print("TESTING PATIENT APIs")
print("="*60)

print("\n1. Logging in as doctor1...")
login_response = requests.post(
    f"{BASE_URL}/api/v1/auth/login",
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    data={"username": "doctor1", "password": "iscs"}
)

if login_response.status_code == 200:
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print_test("Login successful", True)
else:
    print_test(f"Login failed: {login_response.text}", False)
    exit(1)

# Step 2: Create Patient
print("\n2. Testing POST /api/v1/patients (Create Patient)...")
patient_data = {
    "first_name": "John",
    "last_name": "Doe",
    "mrn": f"MRN{datetime.now().timestamp()}",  # Unique MRN
    "date_of_birth": "1980-05-15T00:00:00",
    "gender": "Male",
    "email": "john.doe@example.com",
    "phone": "+1-555-0123",
    "address": "123 Main St, New York, NY",
    "medical_history": {"diabetes": False, "hypertension": True},
    "risk_factors": {"family_history": True, "age": 43}
}

create_response = requests.post(
    f"{BASE_URL}/api/v1/patients",
    headers={**headers, "Content-Type": "application/json"},
    json=patient_data
)

if create_response.status_code == 201:
    patient = create_response.json()
    patient_id = patient["patient_id"]
    print_test(f"Patient created: {patient['first_name']} {patient['last_name']} (ID: {patient_id})", True)
    print(f"   MRN: {patient['mrn']}")
    print(f"   Email: {patient['email']}")
else:
    print_test(f"Failed to create patient: {create_response.text}", False)
    patient_id = None

# Step 3: List Patients
print("\n3. Testing GET /api/v1/patients (List Patients)...")
list_response = requests.get(
    f"{BASE_URL}/api/v1/patients?page=1&page_size=10",
    headers=headers
)

if list_response.status_code == 200:
    patients_data = list_response.json()
    print_test(f"Found {patients_data['total']} patients (showing {len(patients_data['patients'])})", True)
    for p in patients_data['patients'][:3]:
        print(f"   - {p['first_name']} {p['last_name']} (MRN: {p['mrn']})")
else:
    print_test(f"Failed to list patients: {list_response.text}", False)

# Step 4: Get Patient Details
if patient_id:
    print(f"\n4. Testing GET /api/v1/patients/{{id}} (Get Patient Details)...")
    get_response = requests.get(
        f"{BASE_URL}/api/v1/patients/{patient_id}",
        headers=headers
    )

    if get_response.status_code == 200:
        patient_details = get_response.json()
        print_test(f"Retrieved patient details for {patient_details['first_name']} {patient_details['last_name']}", True)
        print(f"   Total Predictions: {patient_details['total_predictions']}")
        print(f"   Medical History: {patient_details['medical_history']}")
    else:
        print_test(f"Failed to get patient: {get_response.text}", False)

# Step 5: Update Patient
if patient_id:
    print(f"\n5. Testing PUT /api/v1/patients/{{id}} (Update Patient)...")
    update_data = {
        "phone": "+1-555-9999",
        "address": "456 Oak Ave, Boston, MA",
        "medical_history": {"diabetes": True, "hypertension": True, "asthma": False}
    }

    update_response = requests.put(
        f"{BASE_URL}/api/v1/patients/{patient_id}",
        headers={**headers, "Content-Type": "application/json"},
        json=update_data
    )

    if update_response.status_code == 200:
        updated_patient = update_response.json()
        print_test(f"Patient updated successfully", True)
        print(f"   New Phone: {updated_patient['phone']}")
        print(f"   New Address: {updated_patient['address']}")
    else:
        print_test(f"Failed to update patient: {update_response.text}", False)

# Step 6: Get Patient Predictions
if patient_id:
    print(f"\n6. Testing GET /api/v1/patients/{{id}}/predictions (Get Predictions)...")
    pred_response = requests.get(
        f"{BASE_URL}/api/v1/patients/{patient_id}/predictions",
        headers=headers
    )

    if pred_response.status_code == 200:
        predictions = pred_response.json()
        print_test(f"Retrieved {predictions['total']} predictions for patient", True)
        if predictions['total'] > 0:
            for pred in predictions['predictions'][:2]:
                print(f"   - {pred['label']} (confidence: {pred['confidence']:.2%})")
        else:
            print("   (No predictions yet)")
    else:
        print_test(f"Failed to get predictions: {pred_response.text}", False)

# Step 7: Get Patient Stats
if patient_id:
    print(f"\n7. Testing GET /api/v1/patients/{{id}}/stats (Get Statistics)...")
    stats_response = requests.get(
        f"{BASE_URL}/api/v1/patients/{patient_id}/stats",
        headers=headers
    )

    if stats_response.status_code == 200:
        stats = stats_response.json()
        print_test(f"Retrieved patient statistics", True)
        print(f"   Total Predictions: {stats['total_predictions']}")
        print(f"   Glaucoma Detections: {stats['glaucoma_detections']}")
        print(f"   Normal Results: {stats['normal_results']}")
        print(f"   Risk Distribution: {stats['risk_distribution']}")
    else:
        print_test(f"Failed to get stats: {stats_response.text}", False)

# Step 8: Delete Patient (Soft Delete)
if patient_id:
    print(f"\n8. Testing DELETE /api/v1/patients/{{id}} (Delete Patient - Soft Delete)...")
    delete_response = requests.delete(
        f"{BASE_URL}/api/v1/patients/{patient_id}",
        headers=headers
    )

    if delete_response.status_code == 204:
        print_test(f"Patient soft-deleted successfully", True)

        # Verify patient is inactive
        get_after_delete = requests.get(
            f"{BASE_URL}/api/v1/patients/{patient_id}",
            headers=headers
        )
        if get_after_delete.status_code == 200:
            inactive_patient = get_after_delete.json()
            print(f"   Patient still accessible but marked inactive: {not inactive_patient.get('is_active', True)}")
    else:
        print_test(f"Failed to delete patient: {delete_response.text}", False)

print("\n" + "="*60)
print("ALL TESTS COMPLETED!")
print("="*60 + "\n")
