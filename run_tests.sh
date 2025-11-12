#!/bin/bash
# Test runner script

set -e

echo "======================================"
echo "Running Glaucoma API Test Suite"
echo "======================================"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "${YELLOW}Warning: Virtual environment not found. Creating one...${NC}"
    python -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate || . venv/Scripts/activate

# Install dependencies
echo "Installing test dependencies..."
pip install -q -r requirements.txt

# Run linting first
echo ""
echo "======================================"
echo "Running Code Quality Checks"
echo "======================================"

echo "→ Black (code formatting)..."
black --check api tests || true

echo "→ Flake8 (style guide)..."
flake8 api tests --max-line-length=100 --extend-ignore=E203,W503 || true

echo "→ MyPy (type checking)..."
mypy api --ignore-missing-imports || true

# Run tests
echo ""
echo "======================================"
echo "Running Unit Tests"
echo "======================================"
pytest tests/test_api_endpoints.py -v --cov=api --cov-report=term

echo ""
echo "======================================"
echo "Running Integration Tests"
echo "======================================"
pytest tests/test_integration.py -v

# Generate coverage report
echo ""
echo "======================================"
echo "Generating Coverage Report"
echo "======================================"
pytest tests/ --cov=api --cov-report=html --cov-report=term

echo ""
echo "${GREEN}✓ All tests completed!${NC}"
echo ""
echo "Coverage report generated in: htmlcov/index.html"
echo ""
