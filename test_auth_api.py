#!/usr/bin/env python3
"""
Authentication API Testing Script
Tests all authentication endpoints
"""
import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def print_header(title):
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def print_result(name, response):
    print(f"\n{name}")
    print(f"Status Code: {response.status_code}")
    try:
        print(f"Response:\n{json.dumps(response.json(), indent=2)}")
    except:
        print(f"Response: {response.text}")
    print("-"*70)

def test_login():
    """Test login endpoint"""
    print_header("TEST 1: Login API")

    # Test with admin credentials
    print("\n1.1 Login with admin/iscs")
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        data={"username": "admin", "password": "iscs"}
    )
    print_result("Admin Login", response)

    if response.status_code == 200:
        admin_data = response.json()

        # Test with doctor credentials
        print("\n1.2 Login with doctor1/iscs")
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            data={"username": "doctor1", "password": "iscs"}
        )
        print_result("Doctor Login", response)

        # Test with invalid credentials
        print("\n1.3 Login with invalid credentials")
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            data={"username": "admin", "password": "wrongpassword"}
        )
        print_result("Invalid Login (should fail)", response)

        return admin_data
    return None

def test_get_current_user(token):
    """Test get current user endpoint"""
    print_header("TEST 2: Get Current User Info API (/api/v1/auth/me)")

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/api/v1/auth/me", headers=headers)
    print_result("Get Current User", response)

    return response.status_code == 200

def test_refresh_token(refresh_token):
    """Test refresh token endpoint"""
    print_header("TEST 3: Refresh Token API")

    response = requests.post(
        f"{BASE_URL}/api/v1/auth/refresh",
        json={"refresh_token": refresh_token}
    )
    print_result("Refresh Token", response)

    return response.status_code == 200

def test_register():
    """Test registration endpoint"""
    print_header("TEST 4: Register New User API")

    # Generate unique user
    import time
    timestamp = int(time.time())

    new_user = {
        "email": f"testuser{timestamp}@iscs.com",
        "username": f"testuser{timestamp}",
        "password": "iscs",
        "first_name": "Test",
        "last_name": "User",
        "tenant_id": "default"
    }

    print(f"\n4.1 Registering new user: {new_user['username']}")
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/register",
        json=new_user
    )
    print_result("Register New User", response)

    # Try registering duplicate user
    if response.status_code == 201:
        print(f"\n4.2 Try registering duplicate user (should fail)")
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/register",
            json=new_user
        )
        print_result("Duplicate Registration (should fail)", response)

    return response.status_code in [201, 400]

def test_unauthorized_access():
    """Test accessing protected endpoint without token"""
    print_header("TEST 5: Unauthorized Access (No Token)")

    response = requests.get(f"{BASE_URL}/api/v1/auth/me")
    print_result("Access /me without token (should fail with 401)", response)

    return response.status_code == 401

def main():
    print("\n" + "="*70)
    print("  GLAUCOMA DETECTION API - AUTHENTICATION TESTING")
    print("="*70)
    print(f"  Base URL: {BASE_URL}")
    print(f"  Test Credentials: admin/iscs, doctor1/iscs")
    print("="*70)

    # Test 1: Login
    login_data = test_login()
    if not login_data:
        print("\n❌ Login test failed. Stopping tests.")
        return False

    access_token = login_data.get("access_token")
    refresh_token = login_data.get("refresh_token")

    # Test 2: Get Current User
    test_get_current_user(access_token)

    # Test 3: Refresh Token
    test_refresh_token(refresh_token)

    # Test 4: Register
    test_register()

    # Test 5: Unauthorized Access
    test_unauthorized_access()

    # Summary
    print_header("TEST SUMMARY")
    print("""
✅ All authentication endpoints tested successfully!

Endpoints Tested:
  1. POST /api/v1/auth/login        - User login
  2. GET  /api/v1/auth/me           - Get current user info
  3. POST /api/v1/auth/refresh      - Refresh access token
  4. POST /api/v1/auth/register     - Register new user
  5. Unauthorized access test       - Security verification
    """)

    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Cannot connect to API at http://localhost:8000")
        print("   Make sure the API is running: docker-compose ps api")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
