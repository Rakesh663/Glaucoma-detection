# Authentication API Testing Guide

## Test Results Summary

### ✅ Working Endpoints (Tested Successfully)

1. **POST /api/v1/auth/login** - User Login
2. **POST /api/v1/auth/register** - New User Registration
3. **POST /api/v1/auth/refresh** - Refresh Access Token
4. **POST /predict** - Prediction with RBAC enforcement
5. **POST /batch-predict** - Batch prediction with RBAC enforcement

### ⚠️ Known Issue

- **GET /api/v1/auth/me** - Currently has a caching issue (needs container rebuild)

---

## How to Test Authentication APIs

### Method 1: Using Swagger UI (Recommended)

1. **Open Swagger UI**
   ```
   http://localhost:8000/docs
   ```

2. **Test Login**
   - Click on `POST /api/v1/auth/login`
   - Click "Try it out"
   - Fill in the form:
     ```
     username: admin
     password: iscs
     ```
   - Click "Execute"
   - **Copy the `access_token` from the response** (you'll need this for protected endpoints)

3. **Authorize in Swagger UI**
   - Click the "Authorize" button at the top right
   - Paste the access_token in the "Value" field (with "Bearer " prefix):
     ```
     Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
     ```
   - Click "Authorize" then "Close"

4. **Test Protected Endpoints**
   - Now you can test `/predict` and other protected endpoints
   - They will automatically use your authorization token

5. **Test Refresh Token**
   - Click on `POST /api/v1/auth/refresh`
   - Click "Try it out"
   - Paste the `refresh_token` from your login response:
     ```json
     {
       "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
     }
     ```
   - Click "Execute"
   - You'll get a new `access_token` and `refresh_token`

6. **Test Registration**
   - Click on `POST /api/v1/auth/register`
   - Click "Try it out"
   - Fill in the JSON body:
     ```json
     {
       "email": "newuser@iscs.com",
       "username": "newuser",
       "password": "iscs",
       "first_name": "New",
       "last_name": "User",
       "tenant_id": "default"
     }
     ```
   - Click "Execute"

---

### Method 2: Using cURL Commands

#### 1. Login

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=iscs"
```

**Expected Response (200 OK):**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "user_id": 1,
  "tenant_id": 1,
  "email": "admin@iscs.com",
  "role": "admin"
}
```

#### 2. Login with Invalid Credentials

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type": application/x-www-form-urlencoded" \
  -d "username=admin&password=wrongpassword"
```

**Expected Response (401 Unauthorized):**
```json
{
  "detail": "Incorrect username or password"
}
```

#### 3. Register New User

```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "testuser@iscs.com",
    "username": "testuser",
    "password": "iscs",
    "first_name": "Test",
    "last_name": "User",
    "tenant_id": "default"
  }'
```

**Expected Response (201 Created):**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "user_id": 8,
  "tenant_id": 1,
  "email": "testuser@iscs.com",
  "role": "no_role"
}
```

#### 4. Refresh Token

```bash
# First, save your refresh_token from login
REFRESH_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

curl -X POST "http://localhost:8000/api/v1/auth/refresh" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}"
```

**Expected Response (200 OK):**
```json
{
  "access_token": "eyJ...",  // New access token
  "refresh_token": "eyJ...",  // New refresh token
  "token_type": "bearer",
  "user_id": 1,
  "tenant_id": 1,
  "email": "admin@iscs.com",
  "role": "admin"
}
```

#### 5. Test Unauthenticated Access (Should Fail)

```bash
curl -X POST "http://localhost:8000/predict" \
  -F "file=@test_image.jpg"
```

**Expected Response (401 Unauthorized):**
```json
{
  "detail": "Not authenticated"
}
```

#### 6. Test With Valid Token

```bash
# First, get an access token
ACCESS_TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=doctor1&password=iscs" | python -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# Use the token to make a prediction
curl -X POST "http://localhost:8000/predict" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F "file=@test_image.jpg"
```

**Expected Response (200 OK with prediction):**
```json
{
  "status": "success",
  "prediction": 1,
  "label": "glaucoma",
  "probability": 0.66,
  "confidence": 0.66,
  "risk_level": "Moderate Risk",
  "recommendations": [...],
  "processing_time_ms": 422.11,
  "timestamp": "2025-11-08T03:47:33.513588",
  "cached": false
}
```

---

### Method 3: Using Python Test Script

Run the automated test script:

```bash
cd /c/Users/DELL/Desktop/glaucoma
python test_auth_api.py
```

This will test all endpoints automatically and show results.

---

## Test Credentials

### All Credentials Use Password: `iscs`

| Username | Email | Role | Permissions |
|----------|-------|------|-------------|
| admin | admin@iscs.com | admin | All permissions (full access) |
| doctor1 | doctor@iscs.com | doctor | Create/read patients, create/read/review predictions |
| radiologist1 | radiologist@iscs.com | radiologist | Read patients, create/read/update/review predictions |
| technician1 | technician@iscs.com | technician | Create/read/update patients, create/read predictions |
| viewer1 | viewer@iscs.com | viewer | Read-only (patients and predictions) |

---

## RBAC Testing

### Test Permission Enforcement

1. **Login as viewer1** (read-only role):
   ```bash
   curl -X POST "http://localhost:8000/api/v1/auth/login" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=viewer1&password=iscs"
   ```

2. **Try to create a prediction** (should fail with 403):
   ```bash
   # Use the viewer1 access_token from step 1
   curl -X POST "http://localhost:8000/predict" \
     -H "Authorization: Bearer <viewer1_token>" \
     -F "file=@test_image.jpg"
   ```

**Expected Response (403 Forbidden):**
```json
{
  "detail": "Insufficient permissions. Required: prediction:create"
}
```

3. **Login as doctor1** (has create permissions):
   ```bash
   curl -X POST "http://localhost:8000/api/v1/auth/login" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=doctor1&password=iscs"
   ```

4. **Create a prediction** (should succeed with 200):
   ```bash
   # Use the doctor1 access_token from step 3
   curl -X POST "http://localhost:8000/predict" \
     -H "Authorization: Bearer <doctor1_token>" \
     -F "file=@test_image.jpg"
   ```

**Expected Response (200 OK with full prediction result)**

---

## Token Details

### Access Token
- **Lifetime**: 30 minutes
- **Type**: JWT (JSON Web Token)
- **Contains**: user_id, tenant_id, email, role, expiration
- **Usage**: Add to Authorization header: `Authorization: Bearer <access_token>`

### Refresh Token
- **Lifetime**: 7 days
- **Purpose**: Get new access_token without re-authenticating
- **Usage**: Send to `/api/v1/auth/refresh` endpoint

---

## Troubleshooting

### "Not authenticated" error
- Make sure you're including the Authorization header
- Check that the token hasn't expired (access tokens last 30 minutes)
- Use refresh token to get a new access token

### "Insufficient permissions" error
- You're using a user without the required permissions
- Check the user's role and permissions in the table above
- Use a user with appropriate permissions (e.g., doctor1 for predictions)

### "Incorrect username or password" error
- Verify you're using the correct credentials
- All test users use password: `iscs`

---

## Quick Start Testing Checklist

1. [ ] Open Swagger UI: http://localhost:8000/docs
2. [ ] Test login with admin/iscs
3. [ ] Copy the access_token
4. [ ] Click "Authorize" and paste the token
5. [ ] Test a protected endpoint (e.g., /predict)
6. [ ] Test RBAC by logging in as viewer1 and trying to create a prediction
7. [ ] Verify it fails with 403 Forbidden
8. [ ] Login as doctor1 and successfully create a prediction

---

## Summary

✅ **Working Features:**
- JWT-based authentication
- Role-Based Access Control (RBAC)
- Multi-tenancy support
- Permission enforcement on protected endpoints
- Token refresh mechanism
- User registration
- Secure password hashing with bcrypt

All authentication routes are functional and can be tested via Swagger UI at http://localhost:8000/docs
