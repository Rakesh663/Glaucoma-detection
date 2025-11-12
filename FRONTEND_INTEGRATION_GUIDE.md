# Frontend Integration Guide - Glaucoma Detection API

## Table of Contents
1. [Overview](#overview)
2. [Authentication Flow](#authentication-flow)
3. [API Endpoints](#api-endpoints)
4. [RBAC System](#rbac-system)
5. [Multi-Tenancy](#multi-tenancy)
6. [Token Management](#token-management)
7. [Error Handling](#error-handling)
8. [Integration Examples](#integration-examples)

---

## Overview

### Base URL
```
Production: https://your-domain.com
Development: http://localhost:8000
```

### Authentication Method
- **Type**: JWT (JSON Web Token) Bearer Authentication
- **Access Token Lifetime**: 30 minutes
- **Refresh Token Lifetime**: 7 days

### Content Types
- **Request**: `application/json` or `application/x-www-form-urlencoded` (for login)
- **Response**: `application/json`

---

## Authentication Flow

### Step-by-Step Authentication Flow

```
┌─────────────┐
│   User      │
│  Login      │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│  POST /api/v1/auth/login           │
│  Username + Password                │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  Receive Tokens:                    │
│  - access_token (30 min)            │
│  - refresh_token (7 days)           │
│  - user_id, role, email             │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  Store Tokens Securely:             │
│  - localStorage (not recommended)   │
│  - sessionStorage                   │
│  - HTTP-only cookies (recommended)  │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  Make API Calls with:               │
│  Authorization: Bearer {token}      │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  Token Expired? (401 error)         │
│  Use refresh_token to get new       │
│  access_token                        │
└─────────────────────────────────────┘
```

---

## API Endpoints

### 1. User Login

**Purpose**: Authenticate a user and receive access & refresh tokens

**Endpoint**: `POST /api/v1/auth/login`

**Request Headers**:
```http
Content-Type: application/x-www-form-urlencoded
```

**Request Body** (form-data):
```
username=admin
password=iscs
```

**OR as JSON** (alternative):
```json
{
  "username": "admin",
  "password": "iscs"
}
```

**Success Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user_id": 1,
  "tenant_id": 1,
  "email": "admin@iscs.com",
  "role": "admin"
}
```

**Error Response** (401 Unauthorized):
```json
{
  "detail": "Incorrect username or password"
}
```

**Error Response** (403 Forbidden):
```json
{
  "detail": "Inactive user account"
}
```

**Frontend Implementation Steps**:
1. Collect username and password from login form
2. Send POST request with form-data or JSON
3. On success (200):
   - Store `access_token` securely
   - Store `refresh_token` securely
   - Store user info (user_id, role, email)
   - Redirect to dashboard
4. On error (401/403):
   - Display error message to user
   - Keep user on login page

---

### 2. User Registration

**Purpose**: Register a new user account

**Endpoint**: `POST /api/v1/auth/register`

**Request Headers**:
```http
Content-Type: application/json
```

**Request Body**:
```json
{
  "email": "john.doe@example.com",
  "username": "johndoe",
  "password": "SecurePassword123!",
  "first_name": "John",
  "last_name": "Doe",
  "tenant_id": "default"
}
```

**Required Fields**:
- `email`: Valid email address (unique)
- `username`: Alphanumeric username (unique)
- `password`: Minimum 8 characters
- `first_name`: User's first name
- `last_name`: User's last name
- `tenant_id`: Tenant identifier (use "default" for single tenant)

**Success Response** (201 Created):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user_id": 11,
  "tenant_id": 1,
  "email": "john.doe@example.com",
  "role": "no_role"
}
```

**Error Response** (400 Bad Request):
```json
{
  "detail": "User with this email or username already exists"
}
```

**Error Response** (404 Not Found):
```json
{
  "detail": "Tenant 'invalid_tenant' not found"
}
```

**Frontend Implementation Steps**:
1. Collect user details from registration form
2. Validate email format and password strength
3. Send POST request with JSON body
4. On success (201):
   - Auto-login user (store tokens)
   - Redirect to onboarding or dashboard
5. On error (400):
   - Display appropriate error message
   - Highlight conflicting fields

---

### 3. Get Current User Info

**Purpose**: Retrieve authenticated user's profile information

**Endpoint**: `GET /api/v1/auth/me`

**Request Headers**:
```http
Authorization: Bearer {access_token}
```

**Success Response** (200 OK):
```json
{
  "id": 1,
  "user_id": "d9cf1916-2207-4214-87d2-4b6d917ff420",
  "email": "admin@iscs.com",
  "username": "admin",
  "first_name": "System",
  "last_name": "Administrator",
  "tenant_id": 1,
  "role": "admin",
  "is_active": true,
  "is_verified": true,
  "is_superuser": true
}
```

**Error Response** (401 Unauthorized):
```json
{
  "detail": "Not authenticated"
}
```

**Error Response** (401 Unauthorized - Token Expired):
```json
{
  "detail": "Token has expired"
}
```

**Frontend Implementation Steps**:
1. Include access_token in Authorization header
2. Call endpoint when app loads or user navigates to profile
3. On success (200):
   - Update user profile in app state
   - Display user information
4. On error (401):
   - If token expired, use refresh token
   - If refresh fails, redirect to login

---

### 4. Refresh Access Token

**Purpose**: Get a new access token using refresh token (without re-authentication)

**Endpoint**: `POST /api/v1/auth/refresh`

**Request Headers**:
```http
Content-Type: application/json
```

**Request Body**:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Success Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user_id": 1,
  "tenant_id": 1,
  "email": "admin@iscs.com",
  "role": "admin"
}
```

**Error Response** (401 Unauthorized):
```json
{
  "detail": "Invalid refresh token"
}
```

**Frontend Implementation Steps**:
1. Detect 401 error on any API call
2. Send refresh token to this endpoint
3. On success (200):
   - Update stored access_token
   - Update stored refresh_token
   - Retry the failed API call
4. On error (401):
   - Clear all stored tokens
   - Redirect to login page

---

### 5. Prediction Endpoint (Protected)

**Purpose**: Upload retinal image for glaucoma detection

**Endpoint**: `POST /predict`

**Request Headers**:
```http
Authorization: Bearer {access_token}
Content-Type: multipart/form-data
```

**Request Body** (multipart/form-data):
```
file: [Image File - JPG/PNG]
use_cache: true (optional, default: true)
```

**Required Permission**: `prediction:create`

**Success Response** (200 OK):
```json
{
  "status": "success",
  "prediction": 1,
  "label": "glaucoma",
  "probability": 0.85,
  "confidence": 0.85,
  "risk_level": "High Risk",
  "recommendations": [
    "Immediate consultation with ophthalmologist recommended",
    "Schedule comprehensive eye examination",
    "Consider additional diagnostic tests (OCT, visual field)"
  ],
  "processing_time_ms": 422.11,
  "timestamp": "2025-11-08T03:47:33.513588",
  "cached": false
}
```

**Error Response** (401 Unauthorized):
```json
{
  "detail": "Not authenticated"
}
```

**Error Response** (403 Forbidden):
```json
{
  "detail": "Insufficient permissions. Required: prediction:create"
}
```

**Frontend Implementation Steps**:
1. Check user has required permission (role: doctor, technician, radiologist, admin)
2. Collect image file from file input
3. Create FormData and append file
4. Include access_token in Authorization header
5. Send POST request
6. On success (200):
   - Display prediction results
   - Show risk level with appropriate styling
   - Display recommendations
7. On error (403):
   - Show "Insufficient permissions" message
   - Guide user to contact admin

---

### 6. Batch Prediction Endpoint (Protected)

**Purpose**: Upload multiple retinal images for batch processing

**Endpoint**: `POST /batch-predict`

**Request Headers**:
```http
Authorization: Bearer {access_token}
Content-Type: multipart/form-data
```

**Request Body** (multipart/form-data):
```
files: [Image File 1]
files: [Image File 2]
files: [Image File 3]
...
use_cache: true (optional, default: true)
```

**Limitations**: Maximum 20 images per batch

**Required Permission**: `prediction:create`

**Success Response** (200 OK):
```json
{
  "status": "success",
  "total_images": 3,
  "successful": 3,
  "failed": 0,
  "cache_hits": 1,
  "cache_misses": 2,
  "cache_hit_rate": "33.3%",
  "processing_time_ms": 1250.45,
  "timestamp": "2025-11-08T04:15:22.123456",
  "results": [
    {
      "index": 0,
      "filename": "eye_scan_1.jpg",
      "status": "success",
      "prediction": 0,
      "label": "normal",
      "probability": 0.92,
      "confidence": 0.92,
      "risk_level": "Low Risk",
      "recommendations": ["Continue regular eye check-ups"],
      "cached": false
    },
    {
      "index": 1,
      "filename": "eye_scan_2.jpg",
      "status": "success",
      "prediction": 1,
      "label": "glaucoma",
      "probability": 0.78,
      "confidence": 0.78,
      "risk_level": "Moderate Risk",
      "recommendations": ["Schedule follow-up examination"],
      "cached": true
    },
    {
      "index": 2,
      "filename": "eye_scan_3.jpg",
      "status": "success",
      "prediction": 1,
      "label": "glaucoma",
      "probability": 0.95,
      "confidence": 0.95,
      "risk_level": "High Risk",
      "recommendations": ["Immediate consultation recommended"],
      "cached": false
    }
  ]
}
```

**Error Response** (400 Bad Request):
```json
{
  "detail": "Maximum 20 images allowed"
}
```

---

## RBAC System

### Role-Based Access Control (RBAC) Overview

The system implements fine-grained permission-based access control with 5 predefined roles.

### Available Roles

| Role | Description | Use Case |
|------|-------------|----------|
| **admin** | Full system access | System administrators |
| **doctor** | Create/read patients, create/read/review predictions | Medical doctors |
| **radiologist** | Read patients, full prediction access | Radiologists |
| **technician** | Create/read/update patients, create/read predictions | Medical technicians |
| **viewer** | Read-only access | Auditors, read-only users |

### Permissions Matrix

| Permission | Admin | Doctor | Radiologist | Technician | Viewer |
|------------|-------|--------|-------------|------------|--------|
| **Patient Permissions** |
| `patient:create` | ✅ | ✅ | ❌ | ✅ | ❌ |
| `patient:read` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `patient:update` | ✅ | ❌ | ❌ | ✅ | ❌ |
| `patient:delete` | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Prediction Permissions** |
| `prediction:create` | ✅ | ✅ | ✅ | ✅ | ❌ |
| `prediction:read` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `prediction:update` | ✅ | ❌ | ✅ | ❌ | ❌ |
| `prediction:delete` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `prediction:review` | ✅ | ✅ | ✅ | ❌ | ❌ |
| **User Permissions** |
| `user:create` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `user:read` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `user:update` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `user:delete` | ✅ | ❌ | ❌ | ❌ | ❌ |

### How to Handle Permissions in Frontend

#### 1. Store User Role on Login
```javascript
// After successful login
const loginResponse = {
  access_token: "...",
  role: "doctor",  // Store this
  // ...
};

// Store in state management (Redux, Context, etc.)
localStorage.setItem('userRole', loginResponse.role);
```

#### 2. Create Permission Checker Function
```javascript
const ROLE_PERMISSIONS = {
  admin: ['*'], // All permissions
  doctor: [
    'patient:create', 'patient:read',
    'prediction:create', 'prediction:read', 'prediction:review'
  ],
  radiologist: [
    'patient:read',
    'prediction:create', 'prediction:read', 'prediction:update', 'prediction:review'
  ],
  technician: [
    'patient:create', 'patient:read', 'patient:update',
    'prediction:create', 'prediction:read'
  ],
  viewer: [
    'patient:read', 'prediction:read'
  ]
};

function hasPermission(userRole, requiredPermission) {
  const permissions = ROLE_PERMISSIONS[userRole] || [];
  return permissions.includes('*') || permissions.includes(requiredPermission);
}
```

#### 3. Use Permission Checks in UI
```javascript
// Example: Show/hide buttons based on permissions
const userRole = getUserRole(); // Get from state/localStorage

// Show "Upload Image" button only if user can create predictions
{hasPermission(userRole, 'prediction:create') && (
  <button>Upload Image for Prediction</button>
)}

// Show "Delete Patient" button only if user can delete patients
{hasPermission(userRole, 'patient:delete') && (
  <button>Delete Patient</button>
)}
```

#### 4. Handle 403 Permission Errors
```javascript
try {
  const response = await fetch('/predict', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`
    },
    body: formData
  });

  if (response.status === 403) {
    // Show permission denied message
    alert('You do not have permission to perform this action. Required: prediction:create');
  }
} catch (error) {
  // Handle error
}
```

---

## Multi-Tenancy

### What is Multi-Tenancy?

Multi-tenancy allows multiple organizations (hospitals, clinics) to use the same system while keeping their data completely isolated.

### How It Works

1. **Each organization has a unique `tenant_id`**
   - Default tenant: `tenant_id = "default"` (id: 1)
   - Hospital A: `tenant_id = "hospital_a"` (id: 2)
   - Clinic B: `tenant_id = "clinic_b"` (id: 3)

2. **Data Isolation**
   - Users can only see data from their own tenant
   - API automatically filters data by tenant_id
   - No manual filtering needed in frontend

3. **Tenant Assignment**
   - During registration, user is assigned to a tenant
   - `tenant_id` is stored in JWT token
   - Cannot be changed after registration (admin only)

### Frontend Considerations

#### Single-Tenant Application (Most Common)
```javascript
// Always use "default" tenant during registration
const registerData = {
  email: "user@example.com",
  username: "newuser",
  password: "password123",
  first_name: "John",
  last_name: "Doe",
  tenant_id: "default"  // Always "default" for single-tenant
};
```

#### Multi-Tenant Application (Advanced)
```javascript
// Show tenant selector during registration
const tenants = [
  { id: "default", name: "Main Organization" },
  { id: "hospital_a", name: "City Hospital" },
  { id: "clinic_b", name: "Eye Clinic" }
];

// User selects tenant during registration
const registerData = {
  email: "user@example.com",
  username: "newuser",
  password: "password123",
  first_name: "John",
  last_name: "Doe",
  tenant_id: selectedTenant.id  // User-selected tenant
};
```

#### Display Tenant Information
```javascript
// After login, show which organization user belongs to
const userInfo = await fetch('/api/v1/auth/me', {
  headers: { 'Authorization': `Bearer ${accessToken}` }
}).then(r => r.json());

console.log(`User belongs to tenant ID: ${userInfo.tenant_id}`);
// Display: "Organization: City Hospital"
```

**Important Notes**:
- Users cannot access data from other tenants
- Admin users within a tenant can only manage users in their tenant
- For single-tenant applications, always use `tenant_id: "default"`

---

## Token Management

### Best Practices for Token Storage

#### ❌ NOT Recommended: localStorage
```javascript
// SECURITY RISK: Vulnerable to XSS attacks
localStorage.setItem('access_token', token);
```

#### ✅ Recommended: HTTP-Only Cookies
```javascript
// Backend sets HTTP-only cookie (cannot be accessed by JavaScript)
// Frontend automatically includes cookie in requests
// Immune to XSS attacks
```

#### ✅ Alternative: sessionStorage (Better than localStorage)
```javascript
// Cleared when browser tab is closed
sessionStorage.setItem('access_token', token);
```

### Token Refresh Strategy

#### Automatic Token Refresh (Recommended)

```javascript
// Axios interceptor example
axios.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // If access token expired
    if (error.response.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        // Get new access token using refresh token
        const refreshToken = getRefreshToken(); // Get from storage
        const response = await axios.post('/api/v1/auth/refresh', {
          refresh_token: refreshToken
        });

        const { access_token, refresh_token } = response.data;

        // Update stored tokens
        setAccessToken(access_token);
        setRefreshToken(refresh_token);

        // Retry original request with new token
        originalRequest.headers['Authorization'] = `Bearer ${access_token}`;
        return axios(originalRequest);

      } catch (refreshError) {
        // Refresh token also expired - logout user
        logout();
        redirectToLogin();
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);
```

#### Manual Token Refresh

```javascript
// Check token expiration before making requests
function isTokenExpired(token) {
  const payload = JSON.parse(atob(token.split('.')[1]));
  const expirationTime = payload.exp * 1000; // Convert to milliseconds
  return Date.now() >= expirationTime;
}

async function makeAuthenticatedRequest(url, options) {
  let accessToken = getAccessToken();

  // Check if token is expired
  if (isTokenExpired(accessToken)) {
    // Refresh token
    const refreshToken = getRefreshToken();
    const response = await fetch('/api/v1/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken })
    });

    const data = await response.json();
    accessToken = data.access_token;
    setAccessToken(accessToken);
    setRefreshToken(data.refresh_token);
  }

  // Make request with valid token
  return fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      'Authorization': `Bearer ${accessToken}`
    }
  });
}
```

### Token Lifecycle

```
Login
  ↓
Store access_token (expires in 30 min)
Store refresh_token (expires in 7 days)
  ↓
Make API calls with access_token
  ↓
Access token expires (after 30 min)
  ↓
Use refresh_token to get new access_token
  ↓
Continue making API calls
  ↓
Refresh token expires (after 7 days)
  ↓
User must login again
```

---

## Error Handling

### Common HTTP Status Codes

| Status Code | Meaning | Action Required |
|-------------|---------|-----------------|
| **200 OK** | Success | Process response data |
| **201 Created** | Resource created | Process response data |
| **400 Bad Request** | Invalid input | Show validation errors to user |
| **401 Unauthorized** | Not authenticated or token expired | Refresh token or redirect to login |
| **403 Forbidden** | Insufficient permissions | Show permission denied message |
| **404 Not Found** | Resource not found | Show "not found" message |
| **422 Unprocessable Entity** | Validation failed | Show field-specific errors |
| **500 Internal Server Error** | Server error | Show generic error, retry later |
| **503 Service Unavailable** | Service down | Show maintenance message |

### Error Response Format

```json
{
  "detail": "Error message here"
}
```

### Frontend Error Handling Template

```javascript
async function callAPI(url, options) {
  try {
    const response = await fetch(url, options);

    // Success responses
    if (response.ok) {
      return await response.json();
    }

    // Error responses
    const errorData = await response.json();

    switch (response.status) {
      case 400:
        // Bad request - validation error
        showValidationError(errorData.detail);
        break;

      case 401:
        // Unauthorized - token expired or invalid
        if (errorData.detail.includes('expired')) {
          // Try to refresh token
          await refreshAccessToken();
          // Retry request
          return callAPI(url, options);
        } else {
          // Invalid credentials
          redirectToLogin();
        }
        break;

      case 403:
        // Forbidden - insufficient permissions
        showPermissionError(errorData.detail);
        break;

      case 404:
        // Not found
        showNotFoundError(errorData.detail);
        break;

      case 422:
        // Validation error
        showFieldErrors(errorData.detail);
        break;

      case 500:
        // Server error
        showServerError('Something went wrong. Please try again later.');
        break;

      case 503:
        // Service unavailable
        showMaintenanceMessage('Service is currently unavailable.');
        break;

      default:
        showGenericError(errorData.detail);
    }

    throw new Error(errorData.detail);

  } catch (error) {
    console.error('API Error:', error);
    throw error;
  }
}
```

---

## Integration Examples

### Complete Login Flow

```javascript
async function login(username, password) {
  try {
    // 1. Call login endpoint
    const response = await fetch('http://localhost:8000/api/v1/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: new URLSearchParams({
        username: username,
        password: password
      })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail);
    }

    const data = await response.json();

    // 2. Store tokens
    sessionStorage.setItem('access_token', data.access_token);
    sessionStorage.setItem('refresh_token', data.refresh_token);

    // 3. Store user info
    sessionStorage.setItem('user_role', data.role);
    sessionStorage.setItem('user_email', data.email);
    sessionStorage.setItem('user_id', data.user_id);

    // 4. Redirect to dashboard
    window.location.href = '/dashboard';

    return data;

  } catch (error) {
    console.error('Login failed:', error);
    alert('Login failed: ' + error.message);
    throw error;
  }
}

// Usage
await login('admin', 'iscs');
```

### Complete Registration Flow

```javascript
async function register(userData) {
  try {
    // 1. Validate input
    if (!userData.email || !userData.password) {
      throw new Error('Email and password are required');
    }

    if (userData.password.length < 8) {
      throw new Error('Password must be at least 8 characters');
    }

    // 2. Call register endpoint
    const response = await fetch('http://localhost:8000/api/v1/auth/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        email: userData.email,
        username: userData.username,
        password: userData.password,
        first_name: userData.firstName,
        last_name: userData.lastName,
        tenant_id: 'default'
      })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail);
    }

    const data = await response.json();

    // 3. Auto-login after registration
    sessionStorage.setItem('access_token', data.access_token);
    sessionStorage.setItem('refresh_token', data.refresh_token);
    sessionStorage.setItem('user_role', data.role);
    sessionStorage.setItem('user_email', data.email);

    // 4. Redirect to onboarding or dashboard
    window.location.href = '/onboarding';

    return data;

  } catch (error) {
    console.error('Registration failed:', error);
    alert('Registration failed: ' + error.message);
    throw error;
  }
}

// Usage
await register({
  email: 'john@example.com',
  username: 'johndoe',
  password: 'SecurePass123',
  firstName: 'John',
  lastName: 'Doe'
});
```

### Making Protected API Calls

```javascript
async function uploadImageForPrediction(imageFile) {
  try {
    // 1. Get access token
    const accessToken = sessionStorage.getItem('access_token');

    if (!accessToken) {
      throw new Error('Not authenticated');
    }

    // 2. Create FormData
    const formData = new FormData();
    formData.append('file', imageFile);
    formData.append('use_cache', 'true');

    // 3. Call prediction endpoint
    const response = await fetch('http://localhost:8000/predict', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${accessToken}`
      },
      body: formData
    });

    if (!response.ok) {
      if (response.status === 401) {
        // Token expired - try to refresh
        await refreshAccessToken();
        // Retry the request
        return uploadImageForPrediction(imageFile);
      }

      if (response.status === 403) {
        throw new Error('You do not have permission to create predictions');
      }

      const error = await response.json();
      throw new Error(error.detail);
    }

    const result = await response.json();

    // 4. Process result
    console.log('Prediction:', result.label);
    console.log('Confidence:', result.confidence);
    console.log('Risk Level:', result.risk_level);

    return result;

  } catch (error) {
    console.error('Prediction failed:', error);
    alert('Prediction failed: ' + error.message);
    throw error;
  }
}

// Usage
const fileInput = document.getElementById('imageInput');
const imageFile = fileInput.files[0];
const prediction = await uploadImageForPrediction(imageFile);
```

### Refresh Token Implementation

```javascript
async function refreshAccessToken() {
  try {
    const refreshToken = sessionStorage.getItem('refresh_token');

    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    const response = await fetch('http://localhost:8000/api/v1/auth/refresh', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        refresh_token: refreshToken
      })
    });

    if (!response.ok) {
      // Refresh token expired - user must login again
      logout();
      window.location.href = '/login';
      throw new Error('Session expired. Please login again.');
    }

    const data = await response.json();

    // Update tokens
    sessionStorage.setItem('access_token', data.access_token);
    sessionStorage.setItem('refresh_token', data.refresh_token);

    return data.access_token;

  } catch (error) {
    console.error('Token refresh failed:', error);
    throw error;
  }
}
```

### Get User Profile

```javascript
async function getUserProfile() {
  try {
    const accessToken = sessionStorage.getItem('access_token');

    const response = await fetch('http://localhost:8000/api/v1/auth/me', {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${accessToken}`
      }
    });

    if (!response.ok) {
      if (response.status === 401) {
        await refreshAccessToken();
        return getUserProfile(); // Retry
      }
      throw new Error('Failed to get user profile');
    }

    const userProfile = await response.json();

    // Update UI with user info
    document.getElementById('userName').textContent =
      `${userProfile.first_name} ${userProfile.last_name}`;
    document.getElementById('userEmail').textContent = userProfile.email;
    document.getElementById('userRole').textContent = userProfile.role;

    return userProfile;

  } catch (error) {
    console.error('Failed to get user profile:', error);
    throw error;
  }
}
```

### Logout Function

```javascript
function logout() {
  // Clear all stored data
  sessionStorage.removeItem('access_token');
  sessionStorage.removeItem('refresh_token');
  sessionStorage.removeItem('user_role');
  sessionStorage.removeItem('user_email');
  sessionStorage.removeItem('user_id');

  // Redirect to login
  window.location.href = '/login';
}
```

---

## Test Credentials

For development and testing purposes:

| Username | Password | Role | Permissions |
|----------|----------|------|-------------|
| `admin` | `iscs` | Admin | Full access to all features |
| `doctor1` | `iscs` | Doctor | Create/read patients, create/read/review predictions |
| `radiologist1` | `iscs` | Radiologist | Read patients, full prediction access |
| `technician1` | `iscs` | Technician | Create/read/update patients, create/read predictions |
| `viewer1` | `iscs` | Viewer | Read-only access to patients and predictions |

---

## Quick Start Checklist

### For Frontend Developers

- [ ] **1. Setup Base URL**
  - Development: `http://localhost:8000`
  - Production: Update to your domain

- [ ] **2. Implement Login Page**
  - Call `POST /api/v1/auth/login`
  - Store tokens securely
  - Store user role and info

- [ ] **3. Implement Registration Page**
  - Call `POST /api/v1/auth/register`
  - Use `tenant_id: "default"` for single-tenant
  - Auto-login after registration

- [ ] **4. Implement Token Management**
  - Store access_token and refresh_token
  - Implement automatic token refresh on 401 errors
  - Clear tokens on logout

- [ ] **5. Implement Authorization Headers**
  - Add `Authorization: Bearer {token}` to all protected endpoints
  - Handle 401 (expired token) with refresh
  - Handle 403 (permission denied) with error message

- [ ] **6. Implement RBAC in UI**
  - Show/hide features based on user role
  - Check permissions before API calls
  - Handle 403 errors gracefully

- [ ] **7. Test Error Scenarios**
  - Invalid credentials (401)
  - Expired token (401)
  - Insufficient permissions (403)
  - Server errors (500)

- [ ] **8. Implement User Profile Page**
  - Call `GET /api/v1/auth/me`
  - Display user information
  - Show role and tenant

---

## API Testing with Swagger

**Swagger UI**: http://localhost:8000/docs

1. Open Swagger UI
2. Click on `POST /api/v1/auth/login`
3. Click "Try it out"
4. Enter credentials (username: `admin`, password: `iscs`)
5. Click "Execute"
6. Copy the `access_token` from response
7. Click "Authorize" button (top right)
8. Paste token with "Bearer " prefix: `Bearer eyJhbGc...`
9. Now you can test all protected endpoints

---

## Support & Resources

- **API Documentation**: http://localhost:8000/docs
- **Authentication Testing Guide**: See `AUTHENTICATION_TESTING_GUIDE.md`
- **API Base URL**: http://localhost:8000
- **Test Script**: Run `python test_auth_api.py` for automated testing

---

## Appendix: Complete Request/Response Examples

### Example 1: Complete Authentication Flow

```javascript
// 1. Login
const loginResponse = await fetch('http://localhost:8000/api/v1/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  body: 'username=admin&password=iscs'
});
const loginData = await loginResponse.json();
// Store: loginData.access_token, loginData.refresh_token

// 2. Get user profile
const profileResponse = await fetch('http://localhost:8000/api/v1/auth/me', {
  headers: { 'Authorization': `Bearer ${loginData.access_token}` }
});
const profile = await profileResponse.json();
// Display: profile.first_name, profile.role

// 3. Make prediction (if user has permission)
const formData = new FormData();
formData.append('file', imageFile);
const predictionResponse = await fetch('http://localhost:8000/predict', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${loginData.access_token}` },
  body: formData
});
const prediction = await predictionResponse.json();
// Display: prediction.label, prediction.risk_level, prediction.recommendations

// 4. Token expired? Refresh it
const refreshResponse = await fetch('http://localhost:8000/api/v1/auth/refresh', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ refresh_token: loginData.refresh_token })
});
const newTokens = await refreshResponse.json();
// Update: newTokens.access_token, newTokens.refresh_token
```

---

**Document Version**: 1.0
**Last Updated**: November 8, 2025
**API Version**: 1.0.0
