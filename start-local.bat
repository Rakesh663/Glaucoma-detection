@echo off
REM Quick start script for local development (Windows)

echo ==========================================
echo Glaucoma Detection - Local Development
echo ==========================================
echo.

REM Check if .env exists
if not exist .env (
    echo Creating .env file from .env.example...
    copy .env.example .env
    echo [OK] .env file created
) else (
    echo [OK] .env file already exists
)

echo.
echo Starting PostgreSQL and Redis...
docker-compose up -d postgres redis

echo.
echo Waiting for PostgreSQL to be ready...
timeout /t 10 /nobreak >nul

echo.
echo Starting all services...
docker-compose up -d

echo.
echo ==========================================
echo Services started successfully!
echo ==========================================
echo.
echo Access your services:
echo   API:        http://localhost:8000
echo   API Docs:   http://localhost:8000/docs
echo   Prometheus: http://localhost:9090
echo   Grafana:    http://localhost:3000 (admin/admin_changeme)
echo.
echo To view logs:
echo   docker-compose logs -f api
echo.
echo To stop all services:
echo   docker-compose down
echo.

pause
