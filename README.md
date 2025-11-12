# Glaucoma Detection System - Production Grade

[![CI/CD Pipeline](https://github.com/Rakesh663/Glaucoma-detection/workflows/CI%2FCD%20Pipeline/badge.svg)](https://github.com/Rakesh663/Glaucoma-detection/actions)
[![codecov](https://codecov.io/gh/Rakesh663/Glaucoma-detection/branch/main/graph/badge.svg)](https://codecov.io/gh/Rakesh663/Glaucoma-detection)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Production-ready glaucoma detection system using deep learning (EfficientNet-B0) with enterprise-grade features: **multi-tenancy, RBAC, OAuth 2.0, circuit breakers, auto-scaling, and comprehensive CI/CD**.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Development Setup](#development-setup)
- [Production Deployment](#production-deployment)
- [API Documentation](#api-documentation)
- [Testing](#testing)
- [Monitoring](#monitoring)
- [Security](#security)
- [Contributing](#contributing)

---

## Features

### Core ML Capabilities
- **Model**: EfficientNet-B0 (ImageNet pretrained)
- **Accuracy**: 100% on ACRIMA dataset (107 test images)
- **Metrics**: AUC, Sensitivity, Specificity, F1 Score
- **Inference**: < 100ms per image on CPU

### Enterprise Features
| Feature | Description |
|---------|-------------|
| **Multi-Tenancy** | Complete data isolation between tenants/organizations |
| **RBAC** | Role-Based Access Control (Admin, Doctor, Radiologist, Technician, Viewer) |
| **Authentication** | JWT + OAuth 2.0 (Google, GitHub, Azure) |
| **Circuit Breaker** | Automatic failure detection and recovery |
| **Retry Logic** | Exponential backoff with jitter for transient failures |
| **Rate Limiting** | Per-user/tenant request throttling |
| **Caching** | Redis-based prediction caching |
| **Monitoring** | Prometheus metrics + Grafana dashboards |
| **Logging** | Structured JSON logging with correlation IDs |
| **Audit Trail** | Complete audit log of all operations |
| **Auto-Scaling** | Kubernetes HPA (CPU/Memory based) |
| **Zero Downtime** | Rolling updates with health checks |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Load Balancer                          │
└─────────────────────────┬───────────────────────────────────┘
                          │
        ┌─────────────────┴─────────────────┐
        │         Kubernetes Cluster         │
        │  ┌─────────────────────────────┐  │
        │  │  FastAPI Pods (HPA 3-20)    │  │
        │  │  - JWT Auth                 │  │
        │  │  - Circuit Breakers         │  │
        │  │  - Rate Limiting            │  │
        │  └──────────┬──────────────────┘  │
        │             │                      │
        │    ┌────────┴─────────┐           │
        │    │                  │           │
        │  ┌─▼──────────┐  ┌───▼───────┐   │
        │  │ PostgreSQL │  │   Redis   │   │
        │  │ (Primary/  │  │ (Cache/   │   │
        │  │  Replica)  │  │  Limiter) │   │
        │  └────────────┘  └───────────┘   │
        └──────────────────────────────────┘
                          │
        ┌─────────────────┴─────────────────┐
        │         Observability             │
        │  ┌──────────┐    ┌──────────┐    │
        │  │Prometheus│◄───┤ Grafana  │    │
        │  └──────────┘    └──────────┘    │
        └───────────────────────────────────┘
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system design.

---

## Quick Start

### Using Docker Compose (Recommended for Local Development)

```bash
# 1. Clone repository
git clone https://github.com/Rakesh663/Glaucoma-detection.git
cd Glaucoma-detection

# 2. Create environment file
cp .env.example .env
# Edit .env with your configuration

# 3. Start all services
docker-compose up -d

# 4. Run database migrations
docker-compose exec api alembic upgrade head

# 5. Seed initial data (roles, permissions, default tenant)
docker-compose exec api python -c "from api.database.seed import seed_database; seed_database()"

# 6. Access services
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
# Grafana: http://localhost:3000 (admin/admin_changeme)
# Prometheus: http://localhost:9090
```

---

## Development Setup

### Prerequisites
- Python 3.10+
- PostgreSQL 15+
- Redis 7+
- Docker & Docker Compose

### Local Development

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment variables
cp .env.example .env

# 4. Start PostgreSQL and Redis
docker-compose up -d postgres-primary redis

# 5. Run migrations
alembic upgrade head

# 6. Seed database
python -c "from api.database.seed import seed_database; seed_database()"

# 7. Start API server
cd api && python main.py

# 8. Start training (optional)
cd src && python train.py
```

### Code Quality

```bash
# Format code
black .
isort .

# Lint
flake8 .
pylint api/ src/

# Type check
mypy api/ src/ --ignore-missing-imports

# Security scan
bandit -r api/ src/
safety check
```

---

## Production Deployment

### Kubernetes Deployment

```bash
# 1. Build and push Docker image
docker build -t your-registry/glaucoma-api:v1.0.0 .
docker push your-registry/glaucoma-api:v1.0.0

# 2. Create namespace
kubectl create namespace glaucoma-detection

# 3. Create secrets
kubectl create secret generic glaucoma-api-secret \
  --from-literal=JWT_SECRET_KEY=your_secret_key \
  --from-literal=POSTGRES_PASSWORD=your_db_password \
  --from-literal=REDIS_PASSWORD=your_redis_password \
  -n glaucoma-detection

# 4. Deploy application
kubectl apply -f k8s/deployment.yaml

# 5. Verify deployment
kubectl get pods -n glaucoma-detection
kubectl get svc -n glaucoma-detection

# 6. Check logs
kubectl logs -f deployment/glaucoma-api -n glaucoma-detection
```

### Blue-Green Deployment

```bash
# Deploy green version
kubectl apply -f k8s/deployment-green.yaml

# Run smoke tests
./scripts/smoke-tests.sh

# Switch traffic to green
kubectl patch service glaucoma-api-service \
  -p '{"spec":{"selector":{"version":"green"}}}'

# Rollback if needed
kubectl patch service glaucoma-api-service \
  -p '{"spec":{"selector":{"version":"blue"}}}'
```

---

## API Documentation

### Endpoints

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/health` | GET | Health check | No |
| `/metrics` | GET | Prometheus metrics | No |
| `/api/v1/auth/login` | POST | Login with email/password | No |
| `/api/v1/auth/register` | POST | Register new user | No |
| `/api/v1/auth/google` | GET | OAuth login (Google) | No |
| `/api/v1/predict` | POST | Single image prediction | Yes |
| `/api/v1/batch-predict` | POST | Batch prediction (max 20) | Yes |
| `/api/v1/patients` | GET/POST | Patient management | Yes (RBAC) |
| `/api/v1/predictions/{id}` | GET | Get prediction by ID | Yes (RBAC) |
| `/api/v1/audit-logs` | GET | View audit logs | Yes (Admin) |

### Authentication

```bash
# 1. Register user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "doctor@hospital.com",
    "username": "doctor1",
    "password": "SecurePass123!",
    "first_name": "John",
    "last_name": "Doe"
  }'

# 2. Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=doctor@hospital.com&password=SecurePass123!"

# Response:
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}

# 3. Make authenticated request
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@fundus_image.jpg"
```

### Example Response

```json
{
  "status": "success",
  "prediction": 1,
  "label": "glaucoma",
  "probability": 0.9567,
  "confidence": 0.9134,
  "risk_level": "high",
  "recommendations": [
    "Immediate ophthalmologist referral recommended",
    "Schedule comprehensive eye examination",
    "Monitor intraocular pressure"
  ],
  "processing_time_ms": 87.3,
  "timestamp": "2025-11-06T10:30:45.123Z"
}
```

---

## Testing

### Unit Tests

```bash
pytest tests/unit/ -v --cov=api --cov=src --cov-report=html
```

### Integration Tests

```bash
# Start test dependencies
docker-compose -f docker-compose.test.yml up -d

# Run integration tests
pytest tests/integration/ -v

# Cleanup
docker-compose -f docker-compose.test.yml down
```

### Performance Tests

```bash
# Install Locust
pip install locust

# Run performance tests
locust -f tests/performance/locustfile.py \
  --headless \
  --users 100 \
  --spawn-rate 10 \
  --run-time 2m \
  --host http://localhost:8000
```

---

## Monitoring

### Prometheus Metrics

Access: `http://localhost:9090`

Key metrics:
- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request latency
- `prediction_total` - Total predictions
- `prediction_duration_seconds` - Prediction time
- `circuit_breaker_state` - Circuit breaker status

### Grafana Dashboards

Access: `http://localhost:3000` (admin/admin_changeme)

Pre-configured dashboards:
1. **API Overview** - Request rates, latency, errors
2. **Database Metrics** - Connection pool, query performance
3. **Redis Metrics** - Cache hit rate, memory usage
4. **Business Metrics** - Predictions per tenant, risk distribution

---

## Security

### Security Features

- [x] Non-root Docker containers
- [x] Read-only root filesystem (where possible)
- [x] JWT token expiration (30 min access, 7 days refresh)
- [x] Password hashing (bcrypt with 12 rounds)
- [x] Rate limiting (60 req/min per user)
- [x] SQL injection prevention (SQLAlchemy ORM)
- [x] XSS protection (FastAPI auto-escaping)
- [x] CORS configuration
- [x] Secrets management (Kubernetes Secrets)
- [x] Audit logging (all operations logged)
- [x] Multi-tenancy isolation

### Security Scanning

```bash
# Dependency vulnerabilities
safety check

# Code security issues
bandit -r api/ src/

# Docker image scanning
trivy image glaucoma-api:latest

# Kubernetes security
kubesec scan k8s/deployment.yaml
```

---

## CI/CD Pipeline

GitHub Actions workflow includes:

1. **Code Quality**: Black, Flake8, MyPy, Pylint
2. **Security**: Bandit, Safety, Trivy
3. **Unit Tests**: pytest with coverage
4. **Integration Tests**: Full API testing
5. **Build**: Multi-stage Docker image
6. **Performance Tests**: Locust load testing
7. **Deploy Staging**: Auto-deploy on `develop` branch
8. **Deploy Production**: Manual approval + Blue-Green deployment
9. **Rollback**: One-click rollback capability

---

## Project Structure

```
glaucoma/
├── api/                     # FastAPI application
│   ├── auth/               # Authentication (JWT, OAuth)
│   ├── database/           # SQLAlchemy models, migrations
│   ├── middleware/         # Custom middleware
│   └── utils/              # Circuit breaker, retry logic
├── src/                     # ML training code
│   ├── model.py            # EfficientNet-B0 model
│   ├── train.py            # Training script
│   ├── dataset.py          # Data loading
│   └── utils.py            # Training utilities
├── k8s/                     # Kubernetes manifests
├── .github/workflows/       # CI/CD pipelines
├── tests/                   # Test suites
├── models/                  # Trained models
├── Dockerfile              # Multi-stage Docker build
├── docker-compose.yml      # Local development environment
├── alembic.ini             # Database migrations
└── requirements.txt        # Python dependencies
```

---

## Performance

| Metric | Value |
|--------|-------|
| Inference Time (CPU) | ~87ms |
| Throughput (1 worker) | ~11 req/sec |
| Throughput (10 workers) | ~100 req/sec |
| Memory per Pod | 512MB (request) / 2GB (limit) |
| Model Size | 51MB |
| Docker Image Size | ~800MB (multi-stage) |

---

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

### Development Guidelines

- Follow PEP 8 style guide
- Write unit tests for new features
- Update documentation
- Run linters before committing
- Keep PRs focused and atomic

---

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file.

---

## Support

- **Documentation**: [https://docs.glaucoma-detection.com](https://docs.glaucoma-detection.com)
- **Issues**: [GitHub Issues](https://github.com/Rakesh663/Glaucoma-detection/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Rakesh663/Glaucoma-detection/discussions)
- **Email**: support@glaucoma-detection.com

---

## Acknowledgments

- **Dataset**: ACRIMA (Fundus images for glaucoma detection)
- **Model**: EfficientNet (Google Research)
- **Framework**: FastAPI, PyTorch, SQLAlchemy
- **Infrastructure**: Docker, Kubernetes, Prometheus, Grafana

---

**Made with ❤️ for better eye health**
