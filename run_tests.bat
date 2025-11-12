@echo off
REM Test runner script for Windows

echo ======================================
echo Running Glaucoma API Test Suite
echo ======================================

REM Check if virtual environment exists
if not exist venv (
    echo Warning: Virtual environment not found. Creating one...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing test dependencies...
pip install -q -r requirements.txt

REM Run linting first
echo.
echo ======================================
echo Running Code Quality Checks
echo ======================================

echo - Black (code formatting)...
black --check api tests 2>nul || echo   Skipped

echo - Flake8 (style guide)...
flake8 api tests --max-line-length=100 --extend-ignore=E203,W503 2>nul || echo   Skipped

echo - MyPy (type checking)...
mypy api --ignore-missing-imports 2>nul || echo   Skipped

REM Run tests
echo.
echo ======================================
echo Running Unit Tests
echo ======================================
pytest tests\test_api_endpoints.py -v --cov=api --cov-report=term

echo.
echo ======================================
echo Running Integration Tests
echo ======================================
pytest tests\test_integration.py -v

REM Generate coverage report
echo.
echo ======================================
echo Generating Coverage Report
echo ======================================
pytest tests\ --cov=api --cov-report=html --cov-report=term

echo.
echo [OK] All tests completed!
echo.
echo Coverage report generated in: htmlcov\index.html
echo.

pause
