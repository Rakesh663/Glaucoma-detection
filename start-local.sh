#!/bin/bash
# Quick start script for local development

set -e

echo "=========================================="
echo "Glaucoma Detection - Local Development"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "✓ .env file created"
else
    echo "✓ .env file already exists"
fi

echo ""
echo "Starting services with Docker Compose..."
docker-compose up -d postgres redis

echo ""
echo "Waiting for PostgreSQL to be ready..."
sleep 10

# Check if alembic is available
if command -v alembic &> /dev/null; then
    echo ""
    echo "Running database migrations..."
    alembic upgrade head

    echo ""
    echo "Seeding database with default data..."
    python -c "from api.database.seed import seed_database; seed_database()"
else
    echo ""
    echo "⚠ Alembic not found. Please run migrations manually:"
    echo "   pip install -r requirements.txt"
    echo "   alembic upgrade head"
fi

echo ""
echo "Starting all services..."
docker-compose up -d

echo ""
echo "=========================================="
echo "Services started successfully!"
echo "=========================================="
echo ""
echo "Access your services:"
echo "  API:        http://localhost:8000"
echo "  API Docs:   http://localhost:8000/docs"
echo "  Prometheus: http://localhost:9090"
echo "  Grafana:    http://localhost:3000 (admin/admin_changeme)"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f api"
echo ""
echo "To stop all services:"
echo "  docker-compose down"
echo ""
