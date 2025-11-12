import requests

# Login as admin
login = requests.post(
    "http://localhost:8000/api/v1/auth/login",
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    data={"username": "admin", "password": "iscs"}
)

token = login.json()["access_token"]

# Delete patient as admin
delete_response = requests.delete(
    "http://localhost:8000/api/v1/patients/7e22c767-e798-45b3-af08-206f88e1f247",
    headers={"Authorization": f"Bearer {token}"}
)

print(f"DELETE Status: {delete_response.status_code}")
if delete_response.status_code == 204:
    print("[PASS] Patient deleted successfully by admin!")
else:
    print(f"[FAIL] {delete_response.text}")
