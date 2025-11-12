# Backend Setup Guide for Frontend Developers

This guide helps frontend developers set up and run the Glaucoma Detection API backend on their local machine.

---

## Prerequisites

Before starting, install the following on your laptop:

### 1. Docker Desktop
- **Download**: https://www.docker.com/products/docker-desktop
- **Windows**: Docker Desktop for Windows
- **Mac**: Docker Desktop for Mac
- **Linux**: Docker Engine + Docker Compose

**Verify Installation**:
```bash
docker --version
docker-compose --version
```

You should see versions like:
```
Docker version 24.0.0 or higher
Docker Compose version 2.20.0 or higher
```

### 2. Git (Optional, if cloning from repository)
- **Download**: https://git-scm.com/downloads

**Verify Installation**:
```bash
git --version
```

---

## Setup Steps

### Step 1: Get the Project Files

**Option A: If you have a Git repository**
```bash
git clone <repository-url>
cd glaucoma
```

**Option B: If you have a ZIP file**
1. Extract the ZIP file
2. Open terminal/command prompt
3. Navigate to the project folder:
   ```bash
   cd path/to/glaucoma
   ```

---

### Step 2: Verify Project Structure

Make sure you have these key files:
```
glaucoma/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── api/
│   ├── main.py
│   ├── routes/
│   ├── auth/
│   └── database/
├── models/
│   └── best_model.pth
└── README.md
```

---

### Step 3: Start the Backend

#### On Windows (PowerShell or Command Prompt):
```bash
cd C:\path\to\glaucoma
docker-compose up -d
```

#### On Mac/Linux (Terminal):
```bash
cd /path/to/glaucoma
docker-compose up -d
```

**Expected Output**:
```
Creating network "glaucoma_default" with the default driver
Creating glaucoma_db_1    ... done
Creating glaucoma_redis_1 ... done
Creating glaucoma_api_1   ... done
```

**This command will**:
- Download required Docker images (PostgreSQL, Redis)
- Build the API container
- Start all services in the background

⏱️ **First-time setup takes 5-10 minutes** (downloading images and building)

---

### Step 4: Wait for Services to Start

Check if containers are running:
```bash
docker-compose ps
```

**Expected Output**:
```
      Name                     Command               State           Ports
---------------------------------------------------------------------------------
glaucoma_api_1     python -m uvicorn api.mai ...   Up      0.0.0.0:8000->8000/tcp
glaucoma_db_1      docker-entrypoint.sh postgres    Up      5432/tcp
glaucoma_redis_1   docker-entrypoint.sh redis ...   Up      6379/tcp
```

**All containers should show "Up"**

---

### Step 5: Verify API is Running

Open your browser and go to:
```
http://localhost:8000
```

**You should see**:
```json
{
  "service": "Glaucoma Detection API",
  "version": "1.0.0",
  "status": "active",
  "endpoints": { ... },
  "model_status": "loaded"
}
```

---

### Step 6: Test API Documentation

Open Swagger UI:
```
http://localhost:8000/docs
```

**You should see**:
- Interactive API documentation
- List of all endpoints
- "Authorize" button in top right

---

### Step 7: Test Authentication

#### Quick Test Using Swagger UI:

1. Go to http://localhost:8000/docs
2. Find `POST /api/v1/auth/login` endpoint
3. Click "Try it out"
4. Fill in:
   - **username**: `admin`
   - **password**: `iscs`
5. Click "Execute"

**Expected Response** (200 OK):
```json
{
  "access_token": "eyJhbGci...",
  "refresh_token": "eyJhbGci...",
  "token_type": "bearer",
  "user_id": 1,
  "tenant_id": 1,
  "email": "admin@iscs.com",
  "role": "admin"
}
```

✅ **If you see this, backend is ready for frontend integration!**

---

## Quick Reference for Frontend Development

### API Base URL
```
http://localhost:8000
```

### Test Credentials

| Username | Password | Role | Use Case |
|----------|----------|------|----------|
| admin | iscs | admin | Full access testing |
| doctor1 | iscs | doctor | Doctor workflow testing |
| radiologist1 | iscs | radiologist | Radiologist workflow testing |
| technician1 | iscs | technician | Technician workflow testing |
| viewer1 | iscs | viewer | Read-only access testing |

### Key Endpoints for Frontend

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | /api/v1/auth/login | Login |
| POST | /api/v1/auth/register | Register new user |
| POST | /api/v1/auth/refresh | Refresh access token |
| GET | /api/v1/auth/me | Get current user info |
| POST | /predict | Upload single image |
| POST | /batch-predict | Upload multiple images |
| GET | /docs | API documentation |

---

## Common Commands

### Start Backend
```bash
docker-compose up -d
```

### Stop Backend
```bash
docker-compose down
```

### View Logs (Debug)
```bash
docker-compose logs -f api
```

### Restart Backend (After Changes)
```bash
docker-compose restart api
```

### Rebuild Backend (If Docker files changed)
```bash
docker-compose down
docker-compose up -d --build
```

### Check Container Status
```bash
docker-compose ps
```

---

## Troubleshooting

### Problem 1: "Port 8000 is already in use"

**Solution**: Stop the process using port 8000 or change the port

**Change Port** (edit `docker-compose.yml`):
```yaml
api:
  ports:
    - "8001:8000"  # Change 8000 to 8001
```

Then access API at: http://localhost:8001

---

### Problem 2: "Cannot connect to Docker daemon"

**Solution**: Make sure Docker Desktop is running

**Windows/Mac**:
- Open Docker Desktop application
- Wait for it to fully start (icon in system tray should be green)

**Linux**:
```bash
sudo systemctl start docker
```

---

### Problem 3: Containers keep restarting

**Check logs**:
```bash
docker-compose logs api
```

**Common causes**:
- Database not ready (wait 30 seconds and check again)
- Port conflicts
- Missing environment variables

**Fix**: Restart all services
```bash
docker-compose down
docker-compose up -d
```

---

### Problem 4: "Model not loaded" in API response

**Check if model file exists**:
```bash
# Windows
dir models\best_model.pth

# Mac/Linux
ls -la models/best_model.pth
```

**If missing**: Contact backend team for model file

---

### Problem 5: API responds but database errors appear

**Solution**: Reset database
```bash
docker-compose down -v
docker-compose up -d
```

**Warning**: This deletes all data. Only use in development!

---

## Testing the API

### Test with cURL (Command Line)

#### Login:
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=iscs"
```

#### Get User Info:
```bash
# First, get token from login response above, then:
curl -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN_HERE"
```

---

### Test with JavaScript (Browser Console)

Open browser console (F12) and paste:

```javascript
// Login
fetch('http://localhost:8000/api/v1/auth/login', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/x-www-form-urlencoded',
  },
  body: new URLSearchParams({
    username: 'admin',
    password: 'iscs'
  })
})
.then(res => res.json())
.then(data => {
  console.log('Login success:', data);
  localStorage.setItem('access_token', data.access_token);
})
.catch(err => console.error('Login failed:', err));
```

---

## Environment Variables (Optional Configuration)

If you need to customize settings, create a `.env` file in the project root:

```bash
# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=glaucoma_db

# API
API_HOST=0.0.0.0
API_PORT=8000

# JWT
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
```

**Note**: Default values work fine for local development. Only change if needed.

---

## Daily Workflow

### Morning (Start work):
```bash
docker-compose up -d
# Wait 30 seconds
# Open http://localhost:8000/docs to verify
```

### During Development:
- Backend runs in background
- Frontend connects to http://localhost:8000
- Check logs if issues: `docker-compose logs -f api`

### Evening (End work):
```bash
docker-compose down
```

---

## Integration Examples

### Example 1: Login and Store Token

```javascript
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
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    localStorage.setItem('user_role', data.role);
    return data;
  } else {
    throw new Error('Login failed');
  }
}

// Usage
login('doctor1', 'iscs')
  .then(user => console.log('Logged in as:', user.role))
  .catch(err => console.error(err));
```

---

### Example 2: Upload Image for Prediction

```javascript
async function uploadImage(imageFile) {
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

  if (response.ok) {
    const result = await response.json();
    console.log('Prediction:', result);
    return result;
  } else if (response.status === 401) {
    // Token expired, refresh and retry
    console.log('Token expired, please login again');
  } else if (response.status === 403) {
    console.log('Insufficient permissions');
  }
}

// Usage with file input
document.getElementById('imageInput').addEventListener('change', (e) => {
  const file = e.target.files[0];
  uploadImage(file);
});
```

---

### Example 3: Auto-Refresh Token

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
    localStorage.clear();
    window.location.href = '/login';
  }
}

// Auto-refresh every 25 minutes (before 30-min expiration)
setInterval(refreshToken, 25 * 60 * 1000);
```

---

## Performance Tips

### 1. Keep Docker Desktop Running
- Stopping and starting Docker Desktop takes time
- Keep it running during development hours

### 2. Use Cache
- The API caches prediction results
- Uploading the same image twice will be faster (cache hit)

### 3. Check Container Resources
- Docker Desktop → Settings → Resources
- Allocate at least:
  - **CPUs**: 2
  - **Memory**: 4 GB
  - **Disk**: 20 GB

---

## Need Help?

### Documentation Files
- `AUTHENTICATION_TESTING_GUIDE.md` - How to test auth APIs
- `FRONTEND_INTEGRATION_GUIDE.md` - Complete API reference
- `RBAC_MULTITENANT_IMPLEMENTATION_GUIDE.md` - Role-based implementation guide

### Check API Logs
```bash
docker-compose logs -f api
```

### Check Database Connection
```bash
docker-compose exec db psql -U postgres -d glaucoma_db -c "\dt"
```

### Check Redis Connection
```bash
docker-compose exec redis redis-cli ping
```

**Expected**: `PONG`

---

## Quick Health Check Script

Save this as `check_backend.sh` (Mac/Linux) or `check_backend.bat` (Windows):

**Mac/Linux** (`check_backend.sh`):
```bash
#!/bin/bash
echo "Checking Docker containers..."
docker-compose ps

echo -e "\nChecking API health..."
curl -s http://localhost:8000/health | python3 -m json.tool

echo -e "\nChecking API root..."
curl -s http://localhost:8000 | python3 -m json.tool
```

**Windows** (`check_backend.bat`):
```batch
@echo off
echo Checking Docker containers...
docker-compose ps

echo.
echo Checking API health...
curl -s http://localhost:8000/health

echo.
echo Checking API root...
curl -s http://localhost:8000
```

Run: `./check_backend.sh` or `check_backend.bat`

---

## What Frontend Developers Need to Know

### ✅ You DON'T need to:
- Install Python
- Install PostgreSQL
- Install Redis
- Understand FastAPI code
- Modify backend code

### ✅ You only need to:
- Install Docker Desktop
- Run `docker-compose up -d`
- Use the API at http://localhost:8000
- Read API documentation at http://localhost:8000/docs

---

## Summary of Setup (TL;DR)

```bash
# 1. Install Docker Desktop
# Download from: https://www.docker.com/products/docker-desktop

# 2. Navigate to project
cd path/to/glaucoma

# 3. Start backend
docker-compose up -d

# 4. Wait 30 seconds, then verify
# Open: http://localhost:8000/docs

# 5. Test login
# Username: admin
# Password: iscs

# Done! ✅
```

---

## Contact

If you encounter issues not covered in this guide, contact the backend team with:
1. Error message
2. Output of `docker-compose logs api`
3. Your operating system (Windows/Mac/Linux)

---

**Last Updated**: 2025-11-08
**API Version**: 1.0.0
**Minimum Docker Version**: 20.10.0
