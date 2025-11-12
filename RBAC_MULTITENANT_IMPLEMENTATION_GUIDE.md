# RBAC & Multi-Tenancy Frontend Implementation Guide

## Table of Contents
1. [Overview](#overview)
2. [Understanding Roles in Real-World Context](#understanding-roles-in-real-world-context)
3. [Authentication Flow](#authentication-flow)
4. [Role-Based UI Implementation](#role-based-ui-implementation)
5. [Prediction API Integration by Role](#prediction-api-integration-by-role)
6. [Multi-Tenancy Implementation](#multi-tenancy-implementation)
7. [Complete Workflows by Role](#complete-workflows-by-role)
8. [Permission-Based Component Patterns](#permission-based-component-patterns)
9. [Error Handling & Edge Cases](#error-handling--edge-cases)
10. [Best Practices](#best-practices)

---

## Overview

This guide helps your frontend team integrate the glaucoma detection system's RBAC and multi-tenancy features. The system has 5 distinct roles, each with specific permissions and workflows.

### System Architecture
- **Authentication**: JWT-based (Access Token: 30 min, Refresh Token: 7 days)
- **Authorization**: Role-Based Access Control (RBAC) with granular permissions
- **Multi-Tenancy**: Data isolation by tenant_id (hospitals/clinics)
- **API Base URL**: `http://localhost:8000`

### All Test Credentials Use Password: `iscs`

---

## Understanding Roles in Real-World Context

### 1. Admin (admin@iscs.com)
**Real-World Persona**: Hospital IT Administrator or System Manager

**What They Do**:
- Manage users across the entire tenant (hospital/clinic)
- Configure system settings
- View all predictions and patient records
- Generate reports and analytics
- Handle user access and permissions

**Permissions**: ALL (full system access)
- `patient:*` - Full patient management
- `prediction:*` - Full prediction access
- `user:*` - Full user management

**Typical Dashboard**:
- System overview with statistics
- User management panel
- All predictions from all users
- System configuration options

---

### 2. Doctor (doctor@iscs.com)
**Real-World Persona**: Ophthalmologist or Eye Doctor

**What They Do**:
- Create and manage patient records
- Upload retinal images for glaucoma screening
- Review prediction results
- Make clinical decisions based on AI predictions
- Cannot modify AI predictions (only review)

**Permissions**:
- `patient:create`, `patient:read`
- `prediction:create`, `prediction:read`, `prediction:review`

**Typical Dashboard**:
- Patient list (only their patients)
- Upload new scans
- Pending reviews
- Recent predictions

**Workflow Example**:
1. Add new patient to system
2. Upload patient's retinal image
3. Receive AI prediction
4. Review and make clinical decision
5. Document findings

---

### 3. Radiologist (radiologist@iscs.com)
**Real-World Persona**: Medical Imaging Specialist

**What They Do**:
- Review AI predictions in detail
- Update prediction status (pending → reviewed → confirmed)
- Access all patient scans for analysis
- Provide expert second opinion on AI results
- Cannot create patients (works with existing records)

**Permissions**:
- `patient:read`
- `prediction:create`, `prediction:read`, `prediction:update`, `prediction:review`

**Typical Dashboard**:
- Queue of predictions to review
- Advanced image analysis tools
- Prediction history
- Statistics on prediction accuracy

**Workflow Example**:
1. View pending predictions queue
2. Open patient scan
3. Review AI prediction
4. Upload additional angles if needed
5. Update prediction status
6. Add expert notes

---

### 4. Technician (technician@iscs.com)
**Real-World Persona**: Medical Technician or Lab Technician

**What They Do**:
- Register new patients
- Update patient demographic information
- Capture and upload retinal images
- Initiate screening process
- Cannot review or modify predictions (only view results)

**Permissions**:
- `patient:create`, `patient:read`, `patient:update`
- `prediction:create`, `prediction:read`

**Typical Dashboard**:
- Patient registration form
- Image upload interface
- Recent uploads
- Scan queue

**Workflow Example**:
1. Register walk-in patient
2. Capture retinal images using fundus camera
3. Upload images to system
4. View preliminary AI result
5. Flag for doctor review

---

### 5. Viewer (viewer@iscs.com)
**Real-World Persona**: Medical Student, Researcher, or Audit Staff

**What They Do**:
- View patient records (read-only)
- View prediction results (read-only)
- Generate reports for research
- Audit system usage
- **CANNOT create, upload, or modify anything**

**Permissions**:
- `patient:read`
- `prediction:read`

**Typical Dashboard**:
- Read-only patient list
- View-only prediction results
- Search and filter options
- Export reports (if allowed)

**What They CANNOT Do**:
- Upload images (will get 403 Forbidden)
- Create patients
- Modify any data

---

## Authentication Flow

### Step 1: Login
```javascript
// Login function for all roles
async function login(username, password) {
  const formData = new URLSearchParams();
  formData.append('username', username);
  formData.append('password', password);

  const response = await fetch('http://localhost:8000/api/v1/auth/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: formData
  });

  if (response.ok) {
    const data = await response.json();
    // Store tokens securely
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    localStorage.setItem('user_role', data.role);
    localStorage.setItem('user_email', data.email);
    localStorage.setItem('tenant_id', data.tenant_id);

    return data;
  } else {
    throw new Error('Login failed');
  }
}

// Example: Doctor logging in
login('doctor1', 'iscs').then(data => {
  console.log('Logged in as:', data.role); // "doctor"
  // Redirect to role-specific dashboard
  redirectToDashboard(data.role);
});
```

**Response Example**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user_id": 2,
  "tenant_id": 1,
  "email": "doctor@iscs.com",
  "role": "doctor"
}
```

---

### Step 2: Get Current User Info
```javascript
async function getCurrentUser() {
  const token = localStorage.getItem('access_token');

  const response = await fetch('http://localhost:8000/api/v1/auth/me', {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });

  if (response.ok) {
    const user = await response.json();
    return user;
  } else if (response.status === 401) {
    // Token expired, try refresh
    await refreshToken();
    return getCurrentUser(); // Retry
  }
}

// Example response
/*
{
  "id": 2,
  "user_id": "USR-1730889600-002",
  "email": "doctor@iscs.com",
  "username": "doctor1",
  "first_name": "Dr. Jane",
  "last_name": "Smith",
  "tenant_id": 1,
  "role": "doctor",
  "is_active": true,
  "is_verified": true,
  "is_superuser": false
}
*/
```

---

### Step 3: Token Refresh (Automatic)
```javascript
async function refreshToken() {
  const refresh_token = localStorage.getItem('refresh_token');

  const response = await fetch('http://localhost:8000/api/v1/auth/refresh', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ refresh_token })
  });

  if (response.ok) {
    const data = await response.json();
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    return data;
  } else {
    // Refresh token expired, force re-login
    logout();
    window.location.href = '/login';
  }
}

// Auto-refresh before expiration (25 minutes)
setInterval(() => {
  refreshToken();
}, 25 * 60 * 1000);
```

---

## Role-Based UI Implementation

### Dashboard Routing by Role
```javascript
function redirectToDashboard(role) {
  const dashboards = {
    'admin': '/admin/dashboard',
    'doctor': '/doctor/dashboard',
    'radiologist': '/radiologist/dashboard',
    'technician': '/technician/dashboard',
    'viewer': '/viewer/dashboard'
  };

  window.location.href = dashboards[role] || '/dashboard';
}
```

---

### Permission-Based Component Rendering

#### Example: Show/Hide Upload Button
```javascript
function UploadButton() {
  const userRole = localStorage.getItem('user_role');

  // Only show for roles that can create predictions
  const canUpload = ['admin', 'doctor', 'radiologist', 'technician'].includes(userRole);

  if (!canUpload) {
    return null; // Don't render for viewer
  }

  return (
    <button onClick={handleUpload}>
      Upload Retinal Image
    </button>
  );
}
```

#### Example: Conditional UI Elements
```javascript
function PatientDetailsPage() {
  const userRole = localStorage.getItem('user_role');

  return (
    <div>
      <h1>Patient Details</h1>

      {/* Everyone can view */}
      <PatientInfo />

      {/* Only technician and admin can edit patient info */}
      {(['admin', 'technician'].includes(userRole)) && (
        <button onClick={editPatient}>Edit Patient</button>
      )}

      {/* Only doctor and radiologist can review predictions */}
      {(['admin', 'doctor', 'radiologist'].includes(userRole)) && (
        <ReviewPredictionPanel />
      )}

      {/* Viewer sees read-only notice */}
      {userRole === 'viewer' && (
        <p className="info">You have read-only access</p>
      )}
    </div>
  );
}
```

---

## Prediction API Integration by Role

### 1. Doctor Workflow: Single Image Upload

**Scenario**: Doctor uploads a patient's retinal scan during consultation

```javascript
async function doctorUploadScan(imageFile, patientId) {
  const token = localStorage.getItem('access_token');
  const formData = new FormData();
  formData.append('file', imageFile);

  try {
    const response = await fetch('http://localhost:8000/predict', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`
      },
      body: formData
    });

    if (response.ok) {
      const result = await response.json();

      // Show result to doctor
      displayPredictionResult(result);

      // Doctor can now make clinical decision
      return result;
    } else if (response.status === 403) {
      alert('Insufficient permissions');
    } else if (response.status === 401) {
      // Token expired, refresh and retry
      await refreshToken();
      return doctorUploadScan(imageFile, patientId);
    }
  } catch (error) {
    console.error('Upload failed:', error);
  }
}

function displayPredictionResult(result) {
  /*
  result = {
    "status": "success",
    "prediction": 1,
    "label": "glaucoma",
    "probability": 0.89,
    "confidence": 0.89,
    "risk_level": "High Risk",
    "recommendations": [
      "Immediate ophthalmologist consultation recommended",
      "Schedule comprehensive eye exam",
      "Monitor intraocular pressure"
    ],
    "processing_time_ms": 245.33,
    "timestamp": "2025-11-08T10:30:00.000000",
    "cached": false
  }
  */

  // Show in UI with color coding
  const riskColor = {
    'Low Risk': 'green',
    'Moderate Risk': 'orange',
    'High Risk': 'red'
  }[result.risk_level];

  document.getElementById('prediction-result').innerHTML = `
    <div class="prediction-card">
      <h3>AI Prediction Result</h3>
      <div class="result ${result.label}" style="color: ${riskColor}">
        <strong>${result.label.toUpperCase()}</strong>
      </div>
      <p>Confidence: ${(result.confidence * 100).toFixed(1)}%</p>
      <p>Risk Level: <span style="color: ${riskColor}">${result.risk_level}</span></p>
      <div class="recommendations">
        <h4>Recommendations:</h4>
        <ul>
          ${result.recommendations.map(r => `<li>${r}</li>`).join('')}
        </ul>
      </div>
      <button onclick="reviewPrediction()">Review & Confirm</button>
    </div>
  `;
}
```

**UI Flow**:
1. Doctor selects patient
2. Clicks "Upload Retinal Scan"
3. Selects image from camera/file
4. System shows loading indicator
5. AI result appears with recommendations
6. Doctor reviews and confirms/rejects
7. Saved to patient record

---

### 2. Radiologist Workflow: Batch Upload & Review

**Scenario**: Radiologist reviews multiple scans from screening camp

```javascript
async function radiologistBatchUpload(imageFiles) {
  const token = localStorage.getItem('access_token');
  const formData = new FormData();

  // Add multiple files
  imageFiles.forEach(file => {
    formData.append('files', file);
  });

  try {
    const response = await fetch('http://localhost:8000/batch-predict', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`
      },
      body: formData
    });

    if (response.ok) {
      const result = await response.json();

      // Display batch results
      displayBatchResults(result);

      return result;
    } else if (response.status === 403) {
      alert('Insufficient permissions');
    }
  } catch (error) {
    console.error('Batch upload failed:', error);
  }
}

function displayBatchResults(result) {
  /*
  result = {
    "status": "success",
    "total_images": 10,
    "successful": 10,
    "failed": 0,
    "cache_hits": 2,
    "cache_misses": 8,
    "cache_hit_rate": "20.0%",
    "processing_time_ms": 2456.78,
    "timestamp": "2025-11-08T10:35:00.000000",
    "results": [
      {
        "index": 0,
        "filename": "patient_001.jpg",
        "status": "success",
        "prediction": 0,
        "label": "normal",
        "probability": 0.95,
        "confidence": 0.95,
        "risk_level": "Low Risk",
        "recommendations": [...],
        "cached": false
      },
      // ... more results
    ]
  }
  */

  // Summary view
  document.getElementById('batch-summary').innerHTML = `
    <div class="batch-summary">
      <h3>Batch Processing Complete</h3>
      <p>Processed: ${result.total_images} images</p>
      <p>Successful: ${result.successful}</p>
      <p>Failed: ${result.failed}</p>
      <p>Processing Time: ${(result.processing_time_ms / 1000).toFixed(2)}s</p>
      <p>Cache Hit Rate: ${result.cache_hit_rate}</p>
    </div>
  `;

  // Individual results table
  const tableRows = result.results.map(r => `
    <tr class="${r.risk_level === 'High Risk' ? 'urgent' : ''}">
      <td>${r.filename}</td>
      <td>${r.label}</td>
      <td>${(r.confidence * 100).toFixed(1)}%</td>
      <td style="color: ${getRiskColor(r.risk_level)}">${r.risk_level}</td>
      <td>
        <button onclick="reviewImage(${r.index})">Review</button>
      </td>
    </tr>
  `).join('');

  document.getElementById('results-table').innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Filename</th>
          <th>Result</th>
          <th>Confidence</th>
          <th>Risk Level</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        ${tableRows}
      </tbody>
    </table>
  `;
}

function getRiskColor(riskLevel) {
  return {
    'Low Risk': 'green',
    'Moderate Risk': 'orange',
    'High Risk': 'red'
  }[riskLevel];
}
```

**UI Flow**:
1. Radiologist selects multiple images (up to 20)
2. Clicks "Batch Upload"
3. Progress bar shows processing status
4. Summary appears showing:
   - Total processed
   - High-risk cases flagged in red
   - Cache efficiency
5. Radiologist reviews high-risk cases first
6. Updates prediction status (pending → reviewed)

---

### 3. Technician Workflow: Quick Screening

**Scenario**: Technician processes walk-in patients for screening

```javascript
async function technicianQuickScan(patientData, imageFile) {
  // Step 1: Register patient (if new)
  const patient = await registerPatient(patientData);

  // Step 2: Upload scan
  const prediction = await uploadScan(imageFile, patient.id);

  // Step 3: Print preliminary result for patient
  printScreeningResult(patient, prediction);

  // Step 4: If high risk, flag for doctor review
  if (prediction.risk_level === 'High Risk') {
    await flagForReview(patient.id, prediction);
  }
}

async function registerPatient(patientData) {
  // Technician has patient:create permission
  const token = localStorage.getItem('access_token');

  const response = await fetch('http://localhost:8000/api/v1/patients', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(patientData)
  });

  return await response.json();
}

async function uploadScan(imageFile, patientId) {
  const token = localStorage.getItem('access_token');
  const formData = new FormData();
  formData.append('file', imageFile);

  const response = await fetch('http://localhost:8000/predict', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    },
    body: formData
  });

  return await response.json();
}

function printScreeningResult(patient, prediction) {
  // Generate simple report for patient
  const report = `
    GLAUCOMA SCREENING RESULT
    ========================
    Patient: ${patient.first_name} ${patient.last_name}
    Date: ${new Date().toLocaleDateString()}

    Result: ${prediction.label.toUpperCase()}
    Risk Level: ${prediction.risk_level}
    Confidence: ${(prediction.confidence * 100).toFixed(1)}%

    ${prediction.risk_level === 'High Risk' ?
      'URGENT: Please consult ophthalmologist immediately' :
      'Recommendations:\n' + prediction.recommendations.join('\n')}
  `;

  // Send to printer or show print dialog
  window.print(report);
}
```

**UI Flow**:
1. Technician clicks "New Screening"
2. Enters patient demographics
3. Captures retinal image
4. System processes and shows result
5. Technician prints result for patient
6. High-risk cases automatically flagged
7. Patient referred to doctor if needed

---

### 4. Viewer Workflow: Cannot Upload

**Scenario**: Viewer (researcher) tries to upload - gets blocked

```javascript
async function viewerAttemptUpload(imageFile) {
  const token = localStorage.getItem('access_token');
  const formData = new FormData();
  formData.append('file', imageFile);

  try {
    const response = await fetch('http://localhost:8000/predict', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`
      },
      body: formData
    });

    if (response.status === 403) {
      // Expected for viewer role
      const error = await response.json();

      alert(`Access Denied: ${error.detail}`);
      // Error: "Insufficient permissions. Required: prediction:create"

      // Redirect to read-only view
      window.location.href = '/viewer/predictions';
    }
  } catch (error) {
    console.error('Upload blocked:', error);
  }
}
```

**UI Implementation**: Hide upload button entirely for viewers
```javascript
function ImageUploadSection() {
  const userRole = localStorage.getItem('user_role');

  if (userRole === 'viewer') {
    return (
      <div className="no-access">
        <p>You have read-only access. Contact admin to upload scans.</p>
      </div>
    );
  }

  return (
    <div className="upload-section">
      <input type="file" accept="image/*" onChange={handleUpload} />
      <button>Upload Scan</button>
    </div>
  );
}
```

---

### 5. Admin Workflow: System Management

**Scenario**: Admin monitors all predictions and manages users

```javascript
async function adminGetAllPredictions() {
  const token = localStorage.getItem('access_token');

  // Admin can see all predictions across all users
  const response = await fetch('http://localhost:8000/api/v1/predictions?limit=100', {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });

  const predictions = await response.json();

  // Show analytics dashboard
  displayAdminAnalytics(predictions);
}

function displayAdminAnalytics(predictions) {
  // Calculate statistics
  const stats = {
    total: predictions.length,
    glaucoma_detected: predictions.filter(p => p.label === 'glaucoma').length,
    high_risk: predictions.filter(p => p.risk_level === 'High Risk').length,
    avg_confidence: predictions.reduce((sum, p) => sum + p.confidence, 0) / predictions.length
  };

  // Display in admin dashboard
  document.getElementById('admin-stats').innerHTML = `
    <div class="admin-analytics">
      <h3>System Analytics</h3>
      <div class="stat-card">
        <h4>Total Scans</h4>
        <p class="stat-value">${stats.total}</p>
      </div>
      <div class="stat-card">
        <h4>Glaucoma Detected</h4>
        <p class="stat-value">${stats.glaucoma_detected}</p>
      </div>
      <div class="stat-card urgent">
        <h4>High Risk Cases</h4>
        <p class="stat-value">${stats.high_risk}</p>
      </div>
      <div class="stat-card">
        <h4>Avg Confidence</h4>
        <p class="stat-value">${(stats.avg_confidence * 100).toFixed(1)}%</p>
      </div>
    </div>
  `;
}
```

---

## Multi-Tenancy Implementation

### Understanding Multi-Tenancy

**Concept**: Multiple hospitals/clinics use the same system, but their data is completely isolated.

**Example**:
- **Tenant 1**: City Hospital (tenant_id: 1)
  - Has users: admin, doctor1, technician1
  - Has 500 patients
- **Tenant 2**: Rural Clinic (tenant_id: 2)
  - Has users: doctor2, viewer2
  - Has 200 patients

**Rule**: Users from Tenant 1 CANNOT see data from Tenant 2

---

### How Tenant Isolation Works

#### 1. Automatic Tenant Filtering (Backend Handles This)
When you make a request, the backend automatically filters by your `tenant_id`:

```javascript
// You make this request
fetch('http://localhost:8000/api/v1/patients', {
  headers: { 'Authorization': `Bearer ${token}` }
});

// Backend automatically adds: WHERE tenant_id = 1
// You only get patients from YOUR tenant
```

**You don't need to send tenant_id in requests** - it's extracted from your JWT token.

---

#### 2. Multi-Tenant Login Selection (Optional)

If users belong to multiple tenants, implement tenant selection:

```javascript
async function loginWithTenantSelection(username, password, selectedTenant) {
  // Login as usual
  const loginData = await login(username, password);

  // Check if user has access to selected tenant
  if (loginData.tenant_id !== selectedTenant) {
    alert('You do not have access to this tenant');
    return;
  }

  // Store tenant context
  localStorage.setItem('current_tenant_id', loginData.tenant_id);

  return loginData;
}
```

---

#### 3. Display Tenant Context in UI

```javascript
function TenantIndicator() {
  const tenantId = localStorage.getItem('tenant_id');
  const userEmail = localStorage.getItem('user_email');

  return (
    <div className="tenant-badge">
      <p>Logged in as: {userEmail}</p>
      <p>Organization: {getTenantName(tenantId)}</p>
    </div>
  );
}

function getTenantName(tenantId) {
  // You can fetch this from an endpoint or hardcode
  const tenants = {
    1: 'City Hospital',
    2: 'Rural Clinic'
  };
  return tenants[tenantId] || `Tenant ${tenantId}`;
}
```

---

## Complete Workflows by Role

### Workflow 1: Doctor's Morning Routine

```javascript
// 1. Login
const doctorSession = await login('doctor1', 'iscs');

// 2. Get today's appointments
const appointments = await fetch('/api/v1/appointments/today', {
  headers: { 'Authorization': `Bearer ${doctorSession.access_token}` }
}).then(r => r.json());

// 3. For each patient appointment
for (const appointment of appointments) {
  // 3a. View patient history
  const patient = await fetch(`/api/v1/patients/${appointment.patient_id}`, {
    headers: { 'Authorization': `Bearer ${doctorSession.access_token}` }
  }).then(r => r.json());

  // 3b. Upload new retinal scan
  const scanResult = await doctorUploadScan(newScanFile, patient.id);

  // 3c. Review AI prediction
  if (scanResult.risk_level === 'High Risk') {
    // Doctor makes clinical decision
    await updatePatientNotes(patient.id, 'Urgent follow-up required');
    await scheduleFollowup(patient.id, '1 week');
  }

  // 3d. Move to next patient
}

// 4. End of day: Review pending cases
const pendingReviews = await fetch('/api/v1/predictions?status=pending&assigned_to=me', {
  headers: { 'Authorization': `Bearer ${doctorSession.access_token}` }
}).then(r => r.json());
```

---

### Workflow 2: Radiologist's Review Queue

```javascript
// 1. Login
const radiologistSession = await login('radiologist1', 'iscs');

// 2. Get all pending predictions
const pendingPredictions = await fetch('/api/v1/predictions?status=pending', {
  headers: { 'Authorization': `Bearer ${radiologistSession.access_token}` }
}).then(r => r.json());

// 3. Sort by priority (High Risk first)
const sortedQueue = pendingPredictions.sort((a, b) => {
  const priority = { 'High Risk': 3, 'Moderate Risk': 2, 'Low Risk': 1 };
  return priority[b.risk_level] - priority[a.risk_level];
});

// 4. Review each case
for (const prediction of sortedQueue) {
  // 4a. View image and AI result
  displayPredictionDetails(prediction);

  // 4b. Radiologist makes expert assessment
  const expertReview = await getUserInput('Do you agree with AI prediction?');

  // 4c. Update prediction status
  await fetch(`/api/v1/predictions/${prediction.id}`, {
    method: 'PATCH',
    headers: {
      'Authorization': `Bearer ${radiologistSession.access_token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      status: 'reviewed',
      expert_opinion: expertReview,
      reviewed_at: new Date().toISOString()
    })
  });
}
```

---

### Workflow 3: Technician's Screening Camp

```javascript
// 1. Login at screening camp
const techSession = await login('technician1', 'iscs');

// 2. Set up mobile workstation
setupMobileScanner();

// 3. Process walk-in patients
async function processWalkIn(patientInfo, retinalImage) {
  // 3a. Quick registration
  const patient = await fetch('/api/v1/patients', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${techSession.access_token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      first_name: patientInfo.firstName,
      last_name: patientInfo.lastName,
      age: patientInfo.age,
      contact: patientInfo.phone
    })
  }).then(r => r.json());

  // 3b. Upload scan
  const formData = new FormData();
  formData.append('file', retinalImage);

  const prediction = await fetch('/predict', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${techSession.access_token}`
    },
    body: formData
  }).then(r => r.json());

  // 3c. Print result slip
  printPatientSlip({
    patient: patient,
    result: prediction.label,
    riskLevel: prediction.risk_level,
    nextSteps: prediction.recommendations[0]
  });

  // 3d. Flag urgent cases
  if (prediction.risk_level === 'High Risk') {
    await sendUrgentAlert(patient, prediction);
    showUrgentMessage('Please advise patient to see doctor immediately');
  }

  // 3e. Next patient
}

// 4. End of day: Upload summary
const dailySummary = {
  total_screened: 45,
  high_risk: 8,
  moderate_risk: 12,
  low_risk: 25
};
await submitDailySummary(dailySummary);
```

---

### Workflow 4: Viewer's Research Analysis

```javascript
// 1. Login
const viewerSession = await login('viewer1', 'iscs');

// 2. Query predictions for research
const researchData = await fetch('/api/v1/predictions?date_from=2025-01-01&date_to=2025-11-08', {
  headers: { 'Authorization': `Bearer ${viewerSession.access_token}` }
}).then(r => r.json());

// 3. Analyze data (read-only)
const analysis = {
  total: researchData.length,
  accuracy: calculateAccuracy(researchData),
  demographics: analyzeDemographics(researchData)
};

// 4. Export for publication (if export permission exists)
exportToCSV(analysis);

// 5. CANNOT upload new scans (will be blocked)
// This will fail with 403:
try {
  await fetch('/predict', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${viewerSession.access_token}` },
    body: formData
  });
} catch (error) {
  console.log('Expected: Viewer cannot upload');
}
```

---

## Permission-Based Component Patterns

### Pattern 1: Higher-Order Component (HOC)

```javascript
function RequirePermission(Component, requiredPermission) {
  return function ProtectedComponent(props) {
    const userRole = localStorage.getItem('user_role');

    // Permission map
    const permissions = {
      'admin': ['*'], // All permissions
      'doctor': ['patient:create', 'patient:read', 'prediction:create', 'prediction:read', 'prediction:review'],
      'radiologist': ['patient:read', 'prediction:create', 'prediction:read', 'prediction:update', 'prediction:review'],
      'technician': ['patient:create', 'patient:read', 'patient:update', 'prediction:create', 'prediction:read'],
      'viewer': ['patient:read', 'prediction:read']
    };

    const hasPermission = permissions[userRole]?.includes(requiredPermission) ||
                          permissions[userRole]?.includes('*');

    if (!hasPermission) {
      return <div className="no-permission">Access Denied</div>;
    }

    return <Component {...props} />;
  };
}

// Usage
const UploadButton = RequirePermission(
  ({ onClick }) => <button onClick={onClick}>Upload Scan</button>,
  'prediction:create'
);
```

---

### Pattern 2: Permission Hook

```javascript
function usePermission(requiredPermission) {
  const userRole = localStorage.getItem('user_role');

  const permissions = {
    'admin': ['*'],
    'doctor': ['patient:create', 'patient:read', 'prediction:create', 'prediction:read', 'prediction:review'],
    'radiologist': ['patient:read', 'prediction:create', 'prediction:read', 'prediction:update', 'prediction:review'],
    'technician': ['patient:create', 'patient:read', 'patient:update', 'prediction:create', 'prediction:read'],
    'viewer': ['patient:read', 'prediction:read']
  };

  const hasPermission = permissions[userRole]?.includes(requiredPermission) ||
                        permissions[userRole]?.includes('*');

  return hasPermission;
}

// Usage
function PredictionPage() {
  const canCreate = usePermission('prediction:create');
  const canUpdate = usePermission('prediction:update');

  return (
    <div>
      {canCreate && <button>Upload New Scan</button>}
      {canUpdate && <button>Update Status</button>}
    </div>
  );
}
```

---

### Pattern 3: Route Protection

```javascript
function ProtectedRoute({ path, component: Component, requiredRole }) {
  const userRole = localStorage.getItem('user_role');

  // Role hierarchy
  const roleHierarchy = {
    'admin': 5,
    'doctor': 4,
    'radiologist': 3,
    'technician': 2,
    'viewer': 1
  };

  const requiredLevel = roleHierarchy[requiredRole] || 0;
  const userLevel = roleHierarchy[userRole] || 0;

  if (userLevel < requiredLevel) {
    return <Redirect to="/access-denied" />;
  }

  return <Route path={path} component={Component} />;
}

// Usage
<Router>
  <ProtectedRoute path="/admin" component={AdminDashboard} requiredRole="admin" />
  <ProtectedRoute path="/doctor" component={DoctorDashboard} requiredRole="doctor" />
  <ProtectedRoute path="/viewer" component={ViewerDashboard} requiredRole="viewer" />
</Router>
```

---

## Error Handling & Edge Cases

### 1. Handle 401 Unauthorized (Token Expired)

```javascript
async function apiRequest(url, options = {}) {
  const token = localStorage.getItem('access_token');

  const response = await fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      'Authorization': `Bearer ${token}`
    }
  });

  if (response.status === 401) {
    // Token expired, try refresh
    const refreshed = await refreshToken();

    if (refreshed) {
      // Retry original request with new token
      const newToken = localStorage.getItem('access_token');
      return fetch(url, {
        ...options,
        headers: {
          ...options.headers,
          'Authorization': `Bearer ${newToken}`
        }
      });
    } else {
      // Refresh failed, force login
      logout();
      window.location.href = '/login';
    }
  }

  return response;
}
```

---

### 2. Handle 403 Forbidden (Insufficient Permissions)

```javascript
async function handlePredictionUpload(file) {
  try {
    const response = await apiRequest('/predict', {
      method: 'POST',
      body: file
    });

    if (response.status === 403) {
      const error = await response.json();

      // Show user-friendly message
      showPermissionError(error.detail);

      // Log for debugging
      console.error('Permission denied:', error.detail);

      // Suggest action
      suggestContactAdmin();
    }
  } catch (error) {
    console.error('Upload failed:', error);
  }
}

function showPermissionError(message) {
  alert(`Access Denied: ${message}\n\nPlease contact your administrator for access.`);
}
```

---

### 3. Handle Network Errors

```javascript
async function robustApiCall(url, options, maxRetries = 3) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const response = await apiRequest(url, options);
      return response;
    } catch (error) {
      if (attempt === maxRetries) {
        // All retries failed
        showErrorNotification('Network error. Please check your connection.');
        throw error;
      }

      // Wait before retry (exponential backoff)
      await new Promise(resolve => setTimeout(resolve, 1000 * attempt));
    }
  }
}
```

---

### 4. Handle Large File Uploads

```javascript
async function uploadWithProgress(file, onProgress) {
  const token = localStorage.getItem('access_token');
  const formData = new FormData();
  formData.append('file', file);

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    // Track upload progress
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        const percentComplete = (e.loaded / e.total) * 100;
        onProgress(percentComplete);
      }
    });

    xhr.addEventListener('load', () => {
      if (xhr.status === 200) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        reject(new Error(`Upload failed: ${xhr.statusText}`));
      }
    });

    xhr.addEventListener('error', () => reject(new Error('Network error')));

    xhr.open('POST', 'http://localhost:8000/predict');
    xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    xhr.send(formData);
  });
}

// Usage
uploadWithProgress(imageFile, (progress) => {
  updateProgressBar(progress);
}).then(result => {
  console.log('Upload complete:', result);
});
```

---

## Best Practices

### 1. Token Storage

**DO**:
- Store tokens in `localStorage` or `sessionStorage`
- Clear tokens on logout
- Implement auto-refresh before expiration

**DON'T**:
- Store tokens in cookies (CSRF risk)
- Store tokens in global variables
- Log tokens to console

```javascript
// Good
function secureTokenStorage() {
  const tokens = {
    set: (access, refresh) => {
      localStorage.setItem('access_token', access);
      localStorage.setItem('refresh_token', refresh);
    },
    get: () => ({
      access: localStorage.getItem('access_token'),
      refresh: localStorage.getItem('refresh_token')
    }),
    clear: () => {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user_role');
      localStorage.removeItem('user_email');
    }
  };
  return tokens;
}
```

---

### 2. Role-Based UI Rendering

**DO**:
- Check permissions on the frontend AND backend
- Hide UI elements users can't access
- Show helpful messages when access is denied

**DON'T**:
- Rely only on frontend permission checks (security risk)
- Show buttons that will fail when clicked
- Confuse users with cryptic error messages

```javascript
// Good
function ActionButton({ action, requiredPermission }) {
  const hasPermission = usePermission(requiredPermission);

  if (!hasPermission) {
    return (
      <Tooltip content="You don't have permission for this action">
        <button disabled className="disabled">
          {action}
        </button>
      </Tooltip>
    );
  }

  return <button onClick={handleAction}>{action}</button>;
}
```

---

### 3. Error User Experience

**DO**:
- Show user-friendly error messages
- Provide next steps or suggestions
- Log technical details for debugging

**DON'T**:
- Show raw API errors to users
- Leave users stuck without guidance
- Ignore errors silently

```javascript
// Good
function handleApiError(error, context) {
  const userMessages = {
    401: 'Your session expired. Please log in again.',
    403: 'You don\'t have permission for this action. Contact your administrator.',
    404: 'Resource not found. It may have been deleted.',
    500: 'Server error. Please try again later.'
  };

  const userMessage = userMessages[error.status] || 'Something went wrong. Please try again.';

  showNotification({
    type: 'error',
    message: userMessage,
    action: context === 'upload' ? 'Try uploading again' : null
  });

  // Log for debugging
  console.error('API Error:', {
    status: error.status,
    context: context,
    timestamp: new Date().toISOString(),
    details: error
  });
}
```

---

### 4. Multi-Tenant Data Handling

**DO**:
- Always display which tenant/organization user belongs to
- Prevent accidental cross-tenant data access
- Log tenant context in all API calls

**DON'T**:
- Assume users belong to only one tenant
- Mix data from different tenants in UI
- Allow manual tenant_id input in forms

```javascript
// Good
function PatientList() {
  const tenantId = localStorage.getItem('tenant_id');
  const [patients, setPatients] = useState([]);

  useEffect(() => {
    // Backend automatically filters by tenant_id from JWT
    fetchPatients().then(data => {
      // Verify all patients belong to current tenant
      const validPatients = data.filter(p => p.tenant_id === parseInt(tenantId));
      setPatients(validPatients);
    });
  }, [tenantId]);

  return (
    <div>
      <TenantBadge tenantId={tenantId} />
      <table>
        {patients.map(patient => (
          <PatientRow key={patient.id} patient={patient} />
        ))}
      </table>
    </div>
  );
}
```

---

### 5. Caching Strategy

**DO**:
- Use `use_cache=true` parameter for predictions
- Implement client-side caching for frequently accessed data
- Show cache status to users (especially for repeat uploads)

**DON'T**:
- Cache sensitive patient data insecurely
- Cache without expiration
- Ignore cache invalidation

```javascript
// Good
async function predictWithCache(imageFile) {
  // Check if this exact image was uploaded before
  const imageHash = await computeImageHash(imageFile);
  const cached = sessionStorage.getItem(`prediction_${imageHash}`);

  if (cached) {
    const result = JSON.parse(cached);
    showNotification('Using cached result (same image uploaded before)');
    return result;
  }

  // Upload with backend cache enabled
  const formData = new FormData();
  formData.append('file', imageFile);

  const response = await fetch('/predict?use_cache=true', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` },
    body: formData
  });

  const result = await response.json();

  // Cache locally for session
  sessionStorage.setItem(`prediction_${imageHash}`, JSON.stringify(result));

  if (result.cached) {
    showNotification('Result retrieved from server cache (faster processing)');
  }

  return result;
}
```

---

## Quick Reference

### Role Permission Matrix

| Action | Admin | Doctor | Radiologist | Technician | Viewer |
|--------|-------|--------|-------------|------------|--------|
| View patients | ✅ | ✅ | ✅ | ✅ | ✅ |
| Create patients | ✅ | ✅ | ❌ | ✅ | ❌ |
| Edit patients | ✅ | ❌ | ❌ | ✅ | ❌ |
| Upload scans | ✅ | ✅ | ✅ | ✅ | ❌ |
| View predictions | ✅ | ✅ | ✅ | ✅ | ✅ |
| Update predictions | ✅ | ❌ | ✅ | ❌ | ❌ |
| Review predictions | ✅ | ✅ | ✅ | ❌ | ❌ |
| Manage users | ✅ | ❌ | ❌ | ❌ | ❌ |

---

### Test Credentials

| Username | Password | Role | Email |
|----------|----------|------|-------|
| admin | iscs | admin | admin@iscs.com |
| doctor1 | iscs | doctor | doctor@iscs.com |
| radiologist1 | iscs | radiologist | radiologist@iscs.com |
| technician1 | iscs | technician | technician@iscs.com |
| viewer1 | iscs | viewer | viewer@iscs.com |

---

### API Endpoints Quick Reference

| Method | Endpoint | Purpose | Required Permission |
|--------|----------|---------|---------------------|
| POST | /api/v1/auth/login | User login | None (public) |
| POST | /api/v1/auth/register | New user signup | None (public) |
| POST | /api/v1/auth/refresh | Refresh token | None (with refresh token) |
| GET | /api/v1/auth/me | Get user info | Authenticated |
| POST | /predict | Single prediction | prediction:create |
| POST | /batch-predict | Batch prediction | prediction:create |

---

## Support

For questions or issues:
1. Check the [Authentication Testing Guide](AUTHENTICATION_TESTING_GUIDE.md)
2. Test APIs using Swagger UI: http://localhost:8000/docs
3. Review API logs for debugging

---

**Document Version**: 1.0
**Last Updated**: 2025-11-08
**API Version**: 1.0.0
