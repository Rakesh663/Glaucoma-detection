# Patient API Guide

## Overview

The Patient API provides complete CRUD operations for managing patient records with RBAC enforcement and multi-tenancy support.

---

## New Endpoints Added (8 APIs)

| Method | Endpoint | Description | Permission Required |
|--------|----------|-------------|---------------------|
| POST | `/api/v1/patients` | Create new patient | `patient:create` |
| GET | `/api/v1/patients` | List patients with pagination | `patient:read` |
| GET | `/api/v1/patients/{patient_id}` | Get patient details | `patient:read` |
| PUT | `/api/v1/patients/{patient_id}` | Update patient info | `patient:update` |
| DELETE | `/api/v1/patients/{patient_id}` | Delete patient (soft delete) | `patient:delete` |
| GET | `/api/v1/patients/{patient_id}/predictions` | Get patient's predictions | `prediction:read` |
| GET | `/api/v1/patients/{patient_id}/stats` | Get patient statistics | `patient:read` |

**Total APIs in Project**: Now **16 APIs** (was 9)

---

## Permission Matrix

| Role | Create | Read | Update | Delete |
|------|--------|------|--------|--------|
| Admin | ✅ | ✅ | ✅ | ✅ |
| Doctor | ✅ | ✅ | ❌ | ❌ |
| Radiologist | ❌ | ✅ | ❌ | ❌ |
| Technician | ✅ | ✅ | ✅ | ❌ |
| Viewer | ❌ | ✅ | ❌ | ❌ |

---

## API Examples

### 1. Create Patient

**Endpoint**: `POST /api/v1/patients`

**Who can use**: admin, doctor, technician

**Request**:
```bash
curl -X POST "http://localhost:8000/api/v1/patients" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Doe",
    "mrn": "MRN001",
    "date_of_birth": "1980-05-15T00:00:00",
    "gender": "male",
    "email": "john.doe@example.com",
    "phone": "+1234567890",
    "address": "123 Main St, City, State",
    "medical_history": {
      "diabetes": true,
      "hypertension": false
    },
    "risk_factors": {
      "family_history": true,
      "smoking": false
    }
  }'
```

**Response** (201 Created):
```json
{
  "id": 1,
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": 1,
  "first_name": "John",
  "last_name": "Doe",
  "mrn": "MRN001",
  "date_of_birth": "1980-05-15T00:00:00",
  "gender": "male",
  "email": "john.doe@example.com",
  "phone": "+1234567890",
  "address": "123 Main St, City, State",
  "medical_history": {
    "diabetes": true,
    "hypertension": false
  },
  "risk_factors": {
    "family_history": true,
    "smoking": false
  },
  "is_active": true,
  "created_at": "2025-11-10T10:30:00.000000",
  "updated_at": null
}
```

**JavaScript Example**:
```javascript
async function createPatient(patientData) {
  const token = localStorage.getItem('access_token');

  const response = await fetch('http://localhost:8000/api/v1/patients', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(patientData)
  });

  if (response.ok) {
    const patient = await response.json();
    console.log('Patient created:', patient);
    return patient;
  } else if (response.status === 403) {
    alert('You do not have permission to create patients');
  } else if (response.status === 400) {
    const error = await response.json();
    alert(`Error: ${error.detail}`);
  }
}

// Usage
createPatient({
  first_name: "John",
  last_name: "Doe",
  mrn: "MRN001",
  email: "john.doe@example.com",
  phone: "+1234567890"
});
```

---

### 2. List Patients (with Pagination & Search)

**Endpoint**: `GET /api/v1/patients`

**Who can use**: ALL roles

**Request**:
```bash
# Basic list
curl -X GET "http://localhost:8000/api/v1/patients" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# With pagination
curl -X GET "http://localhost:8000/api/v1/patients?page=1&page_size=20" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# With search
curl -X GET "http://localhost:8000/api/v1/patients?search=John" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Filter by active status
curl -X GET "http://localhost:8000/api/v1/patients?is_active=true" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response** (200 OK):
```json
{
  "total": 45,
  "page": 1,
  "page_size": 20,
  "patients": [
    {
      "id": 1,
      "patient_id": "550e8400-e29b-41d4-a716-446655440000",
      "tenant_id": 1,
      "first_name": "John",
      "last_name": "Doe",
      "mrn": "MRN001",
      "date_of_birth": "1980-05-15T00:00:00",
      "gender": "male",
      "email": "john.doe@example.com",
      "phone": "+1234567890",
      "address": "123 Main St, City, State",
      "medical_history": {},
      "risk_factors": {},
      "is_active": true,
      "created_at": "2025-11-10T10:30:00.000000",
      "updated_at": null
    }
    // ... more patients
  ]
}
```

**JavaScript Example**:
```javascript
async function listPatients(page = 1, search = '') {
  const token = localStorage.getItem('access_token');
  const url = new URL('http://localhost:8000/api/v1/patients');
  url.searchParams.append('page', page);
  url.searchParams.append('page_size', 20);
  if (search) url.searchParams.append('search', search);

  const response = await fetch(url, {
    headers: { 'Authorization': `Bearer ${token}` }
  });

  if (response.ok) {
    const data = await response.json();
    return data;
  }
}

// Usage
listPatients(1, 'John').then(data => {
  console.log(`Total patients: ${data.total}`);
  console.log('Patients:', data.patients);
});
```

---

### 3. Get Patient Details (with Prediction History)

**Endpoint**: `GET /api/v1/patients/{patient_id}`

**Who can use**: ALL roles

**Request**:
```bash
curl -X GET "http://localhost:8000/api/v1/patients/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response** (200 OK):
```json
{
  "id": 1,
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": 1,
  "first_name": "John",
  "last_name": "Doe",
  "mrn": "MRN001",
  "date_of_birth": "1980-05-15T00:00:00",
  "gender": "male",
  "email": "john.doe@example.com",
  "phone": "+1234567890",
  "address": "123 Main St, City, State",
  "medical_history": {
    "diabetes": true
  },
  "risk_factors": {
    "family_history": true
  },
  "is_active": true,
  "created_at": "2025-11-10T10:30:00.000000",
  "updated_at": null,
  "predictions": [
    {
      "id": 5,
      "prediction_id": "pred_001",
      "label": "glaucoma",
      "confidence": 0.89,
      "risk_level": "High Risk",
      "created_at": "2025-11-10T11:00:00.000000",
      "status": "reviewed"
    },
    {
      "id": 3,
      "prediction_id": "pred_002",
      "label": "normal",
      "confidence": 0.95,
      "risk_level": "Low Risk",
      "created_at": "2025-11-09T10:00:00.000000",
      "status": "pending"
    }
  ],
  "total_predictions": 2,
  "latest_prediction": {
    "id": 5,
    "prediction_id": "pred_001",
    "label": "glaucoma",
    "confidence": 0.89,
    "risk_level": "High Risk",
    "created_at": "2025-11-10T11:00:00.000000",
    "status": "reviewed"
  }
}
```

**JavaScript Example**:
```javascript
async function getPatient(patientId) {
  const token = localStorage.getItem('access_token');

  const response = await fetch(
    `http://localhost:8000/api/v1/patients/${patientId}`,
    {
      headers: { 'Authorization': `Bearer ${token}` }
    }
  );

  if (response.ok) {
    const patient = await response.json();
    console.log('Patient:', patient);
    console.log('Total predictions:', patient.total_predictions);
    return patient;
  } else if (response.status === 404) {
    alert('Patient not found');
  }
}
```

---

### 4. Update Patient

**Endpoint**: `PUT /api/v1/patients/{patient_id}`

**Who can use**: admin, technician

**Request**:
```bash
curl -X PUT "http://localhost:8000/api/v1/patients/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "+9876543210",
    "address": "456 New Street, Updated City",
    "medical_history": {
      "diabetes": true,
      "hypertension": true,
      "last_checkup": "2025-11-01"
    }
  }'
```

**Response** (200 OK):
```json
{
  "id": 1,
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",
  "first_name": "John",
  "last_name": "Doe",
  "mrn": "MRN001",
  "phone": "+9876543210",
  "address": "456 New Street, Updated City",
  "medical_history": {
    "diabetes": true,
    "hypertension": true,
    "last_checkup": "2025-11-01"
  },
  // ... other fields
}
```

---

### 5. Delete Patient (Soft Delete)

**Endpoint**: `DELETE /api/v1/patients/{patient_id}`

**Who can use**: admin only

**Request**:
```bash
curl -X DELETE "http://localhost:8000/api/v1/patients/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response** (204 No Content):
```
(Empty response body)
```

**Note**: This is a **soft delete** - the patient is marked as `is_active=false` but not removed from the database.

---

### 6. Get Patient Predictions

**Endpoint**: `GET /api/v1/patients/{patient_id}/predictions`

**Who can use**: ALL roles (requires `prediction:read`)

**Request**:
```bash
curl -X GET "http://localhost:8000/api/v1/patients/550e8400-e29b-41d4-a716-446655440000/predictions" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response** (200 OK):
```json
{
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",
  "patient_name": "John Doe",
  "total": 5,
  "page": 1,
  "page_size": 20,
  "predictions": [
    {
      "id": 10,
      "prediction_id": "pred_010",
      "label": "glaucoma",
      "confidence": 0.92,
      "probability": 0.92,
      "risk_level": "High Risk",
      "recommendations": [
        "Immediate ophthalmologist consultation",
        "Schedule comprehensive eye exam"
      ],
      "status": "reviewed",
      "reviewed_by": 2,
      "reviewed_at": "2025-11-10T12:00:00.000000",
      "created_at": "2025-11-10T11:30:00.000000"
    }
    // ... more predictions
  ]
}
```

---

### 7. Get Patient Statistics

**Endpoint**: `GET /api/v1/patients/{patient_id}/stats`

**Who can use**: ALL roles

**Request**:
```bash
curl -X GET "http://localhost:8000/api/v1/patients/550e8400-e29b-41d4-a716-446655440000/stats" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Response** (200 OK):
```json
{
  "patient_id": "550e8400-e29b-41d4-a716-446655440000",
  "patient_name": "John Doe",
  "mrn": "MRN001",
  "total_predictions": 12,
  "glaucoma_detections": 3,
  "normal_results": 9,
  "risk_distribution": {
    "high": 3,
    "moderate": 2,
    "low": 7
  },
  "average_confidence": 0.87,
  "latest_prediction": {
    "label": "glaucoma",
    "risk_level": "High Risk",
    "confidence": 0.92,
    "date": "2025-11-10T11:30:00.000000"
  },
  "medical_history": {
    "diabetes": true,
    "hypertension": true
  },
  "risk_factors": {
    "family_history": true,
    "smoking": false
  }
}
```

**JavaScript Example**:
```javascript
async function getPatientStats(patientId) {
  const token = localStorage.getItem('access_token');

  const response = await fetch(
    `http://localhost:8000/api/v1/patients/${patientId}/stats`,
    {
      headers: { 'Authorization': `Bearer ${token}` }
    }
  );

  if (response.ok) {
    const stats = await response.json();
    console.log('Patient Statistics:', stats);

    // Display in UI
    document.getElementById('total-predictions').innerText = stats.total_predictions;
    document.getElementById('glaucoma-count').innerText = stats.glaucoma_detections;
    document.getElementById('avg-confidence').innerText =
      `${(stats.average_confidence * 100).toFixed(1)}%`;

    return stats;
  }
}
```

---

## Complete Workflow Examples

### Workflow 1: Doctor Registers New Patient and Orders Scan

```javascript
// Step 1: Login as doctor
const loginData = await login('doctor1', 'iscs');

// Step 2: Create patient
const patient = await createPatient({
  first_name: "Jane",
  last_name: "Smith",
  mrn: "MRN123",
  date_of_birth: "1975-08-20T00:00:00",
  email: "jane.smith@example.com",
  phone: "+1234567890"
});

console.log('Patient created:', patient.patient_id);

// Step 3: Upload retinal scan for patient
const scanFile = document.getElementById('scanInput').files[0];
const prediction = await uploadScan(scanFile, patient.patient_id);

console.log('Prediction result:', prediction.label, prediction.risk_level);

// Step 4: View patient with prediction history
const patientDetails = await getPatient(patient.patient_id);
console.log('Patient has', patientDetails.total_predictions, 'predictions');
```

---

### Workflow 2: Technician Updates Patient Contact Info

```javascript
// Step 1: Login as technician
const loginData = await login('technician1', 'iscs');

// Step 2: Search for patient
const searchResults = await listPatients(1, 'Jane Smith');
const patient = searchResults.patients[0];

// Step 3: Update patient info
const token = localStorage.getItem('access_token');
const response = await fetch(
  `http://localhost:8000/api/v1/patients/${patient.patient_id}`,
  {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      phone: "+9999999999",
      address: "New address after patient moved"
    })
  }
);

if (response.ok) {
  const updated = await response.json();
  console.log('Patient updated successfully');
}
```

---

### Workflow 3: Viewer Searches and Views Patient (Read-Only)

```javascript
// Step 1: Login as viewer
const loginData = await login('viewer1', 'iscs');

// Step 2: Search patients
const results = await listPatients(1, 'Doe');
console.log('Found', results.total, 'patients');

// Step 3: View patient details
const patient = await getPatient(results.patients[0].patient_id);

// Step 4: View patient stats
const stats = await getPatientStats(patient.patient_id);
console.log('Patient has', stats.total_predictions, 'predictions');
console.log('Glaucoma detected', stats.glaucoma_detections, 'times');

// Step 5: Try to update (will fail with 403)
try {
  await updatePatient(patient.patient_id, { phone: "new number" });
} catch (error) {
  console.log('Expected: Viewer cannot update patients');
}
```

---

## Multi-Tenancy Behavior

### Automatic Tenant Filtering

All patient operations are automatically filtered by the user's `tenant_id`:

**Example**:
- **Hospital A** (tenant_id=1): Has patients John, Jane, Bob
- **Clinic B** (tenant_id=2): Has patients Alice, Carol, Dave

**Scenario**:
```javascript
// Doctor from Hospital A logs in
const doctorA = await login('doctor_hospitalA', 'iscs');
// doctorA.tenant_id = 1

// List patients - only sees Hospital A patients
const patients = await listPatients();
// Returns: John, Jane, Bob
// Does NOT see: Alice, Carol, Dave (they belong to Clinic B)

// Try to access Clinic B patient (will return 404)
const patient = await getPatient('alice_patient_id');
// Error: "Patient with ID 'alice_patient_id' not found"
// (Patient exists, but belongs to different tenant)
```

---

## Error Handling

### Common Errors

**400 Bad Request** - MRN already exists:
```json
{
  "detail": "Patient with MRN 'MRN001' already exists in your organization"
}
```

**401 Unauthorized** - No token or expired token:
```json
{
  "detail": "Not authenticated"
}
```

**403 Forbidden** - Insufficient permissions:
```json
{
  "detail": "Insufficient permissions. Required: patient:create"
}
```

**404 Not Found** - Patient doesn't exist (or belongs to different tenant):
```json
{
  "detail": "Patient with ID '550e8400-e29b-41d4-a716-446655440000' not found"
}
```

---

## Testing in Swagger UI

1. **Open Swagger**: http://localhost:8000/docs

2. **Login**:
   - Use `POST /api/v1/auth/login`
   - Username: `doctor1`, Password: `iscs`

3. **Authorize**:
   - Click "Authorize" button
   - Enter username and password
   - Click "Authorize"

4. **Test Patient APIs**:
   - All `/api/v1/patients/*` endpoints are now visible
   - Try creating a patient
   - Try listing patients
   - Try viewing patient details

---

## Quick Reference

### HTTP Methods
- **POST** = Create new resource
- **GET** = Read/retrieve resource
- **PUT** = Update existing resource
- **DELETE** = Remove resource

### Status Codes
- **200 OK** = Success
- **201 Created** = Resource created successfully
- **204 No Content** = Success, no response body
- **400 Bad Request** = Invalid input
- **401 Unauthorized** = Not authenticated
- **403 Forbidden** = Insufficient permissions
- **404 Not Found** = Resource doesn't exist

---

## Summary

You now have **16 total APIs**:
- 3 Core APIs (/, /health, /metrics)
- 4 Authentication APIs (/api/v1/auth/*)
- 2 Prediction APIs (/predict, /batch-predict)
- **7 NEW Patient APIs** (/api/v1/patients/*)

**What Frontend Can Now Do**:
- ✅ Create patients
- ✅ List and search patients
- ✅ View patient details with prediction history
- ✅ Update patient information
- ✅ Delete patients (soft delete)
- ✅ View patient statistics
- ✅ View patient-specific predictions

**All with**:
- ✅ Role-based access control
- ✅ Multi-tenant data isolation
- ✅ Audit logging
- ✅ Pagination and search

---

**Document Version**: 1.0
**Date**: 2025-11-10
**API Version**: 1.0.0
