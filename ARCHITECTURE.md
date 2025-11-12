# System Architecture

This document provides a comprehensive overview of the Glaucoma Detection System architecture, design decisions, and implementation details.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Patterns](#architecture-patterns)
3. [Component Design](#component-design)
4. [Data Flow](#data-flow)
5. [Security Architecture](#security-architecture)
6. [Scalability & Performance](#scalability--performance)
7. [Deployment Architecture](#deployment-architecture)
8. [Monitoring & Observability](#monitoring--observability)
9. [Design Decisions](#design-decisions)

---

## System Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Internet                                     │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                    ┌─────────▼────────┐
                    │  Load Balancer   │
                    │   (Ingress)      │
                    └─────────┬────────┘
                              │
        ┌─────────────────────┴──────────────────────┐
        │        Kubernetes Cluster (GKE/EKS/AKS)    │
        │                                             │
        │  ┌────────────────────────────────────┐   │
        │  │  FastAPI Application Layer         │   │
        │  │  ┌──────────────────────────────┐  │   │
        │  │  │ Multi-Tenancy Middleware     │  │   │
        │  │  ├──────────────────────────────┤  │   │
        │  │  │ Authentication (JWT/OAuth)   │  │   │
        │  │  ├──────────────────────────────┤  │   │
        │  │  │ RBAC Permission Layer        │  │   │
        │  │  ├──────────────────────────────┤  │   │
        │  │  │ Circuit Breaker + Retry      │  │   │
        │  │  ├──────────────────────────────┤  │   │
        │  │  │ Rate Limiting (Redis)        │  │   │
        │  │  ├──────────────────────────────┤  │   │
        │  │  │ Business Logic               │  │   │
        │  │  │  - Prediction Service        │  │   │
        │  │  │  - Patient Service           │  │   │
        │  │  │  - User Service              │  │   │
        │  │  ├──────────────────────────────┤  │   │
        │  │  │ Audit Logging               │  │   │
        │  │  └──────────────────────────────┘  │   │
        │  └──────────┬────────────┬─────────────┘   │
        │             │            │                  │
        │    ┌────────▼───────┐ ┌─▼────────────┐    │
        │    │ PostgreSQL 15  │ │   Redis 7    │    │
        │    │ ┌────────────┐ │ │ ┌──────────┐ │    │
        │    │ │  Primary   │ │ │ │  Cache   │ │    │
        │    │ └─────┬──────┘ │ │ │  Layer   │ │    │
        │    │       │        │ │ └──────────┘ │    │
        │    │ ┌─────▼──────┐ │ │ ┌──────────┐ │    │
        │    │ │ Replica(s) │ │ │ │  Rate    │ │    │
        │    │ └────────────┘ │ │ │  Limiter │ │    │
        │    └────────────────┘ │ └──────────┘ │    │
        │                       └──────────────┘    │
        │                                           │
        │  ┌────────────────────────────────────┐  │
        │  │  Observability Stack               │  │
        │  │  ┌────────────┐   ┌─────────────┐ │  │
        │  │  │ Prometheus │◄──┤  Grafana    │ │  │
        │  │  │  (Metrics) │   │ (Dashboard) │ │  │
        │  │  └────────────┘   └─────────────┘ │  │
        │  └────────────────────────────────────┘  │
        └──────────────────────────────────────────┘
```

---

## Architecture Patterns

### 1. Multi-Tenancy Pattern

**Implementation**: Row-Level Tenancy (Shared Database, Shared Schema)

```python
# Every table has tenant_id foreign key
class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    # ... other fields
```

**Data Isolation**:
- Middleware extracts tenant context from headers/subdomain/JWT
- All database queries automatically filtered by tenant_id
- Cross-tenant queries blocked at application layer

**Why Row-Level?**
- ✅ Cost-effective (single database)
- ✅ Easy schema migrations
- ✅ Efficient resource utilization
- ✅ Suitable for 100s-1000s of tenants
- ❌ Not suitable for extremely large tenants (consider database-per-tenant)

### 2. RBAC (Role-Based Access Control)

**Model**: User → Role → Permissions

```
User
 ├─ Role (e.g., "doctor")
     ├─ Permission: patient:create
     ├─ Permission: patient:read
     ├─ Permission: prediction:create
     └─ Permission: prediction:review
```

**Permission Format**: `resource:action`
- `patient:create` - Create patients
- `prediction:read` - View predictions
- `audit:read` - View audit logs

**Enforcement**:
```python
# Declarative permission checking
@router.post("/patients")
async def create_patient(
    user: User = Depends(RequirePermission("patient:create"))
):
    # User is guaranteed to have permission
    pass
```

### 3. Circuit Breaker Pattern

**States**: Closed → Open → Half-Open

```python
@database_circuit_breaker
async def query_database():
    # If 5 consecutive failures, circuit opens for 60s
    # After 60s, enters half-open (allow 1 test request)
    # If success, circuit closes; if fail, stays open
    pass
```

**Benefits**:
- Prevents cascading failures
- Fails fast (no waiting for timeouts)
- Automatic recovery

### 4. Retry with Exponential Backoff + Jitter

```python
@retry_database_operation
async def insert_record():
    # Retry logic:
    # Attempt 1: Immediate
    # Attempt 2: Wait 2^1 = 2s ± jitter
    # Attempt 3: Wait 2^2 = 4s ± jitter
    # Attempt 4: Fail
    pass
```

**Jitter**: ±25% random variation prevents thundering herd

---

## Component Design

### 1. Authentication Layer

```
┌────────────────────────────────────────┐
│       Authentication Flow              │
│                                        │
│  ┌──────────┐     ┌──────────────┐   │
│  │  Login   │────►│ JWT Service  │   │
│  │  Request │     │ - Hash Check │   │
│  └──────────┘     │ - Token Gen  │   │
│                   └──────┬───────┘   │
│                          │            │
│                   ┌──────▼───────┐   │
│                   │  JWT Token   │   │
│                   │ - User ID    │   │
│                   │ - Tenant ID  │   │
│                   │ - Role       │   │
│                   │ - Expires    │   │
│                   └──────────────┘   │
└────────────────────────────────────────┘
```

**Token Structure**:
```json
{
  "sub": "123",              // User ID
  "tenant_id": 1,            // Tenant ID
  "email": "user@example.com",
  "role": "doctor",
  "exp": 1699264800,         // Expiration
  "iat": 1699263000,         // Issued at
  "type": "access"           // Token type
}
```

**OAuth 2.0 Flow**:
```
User → OAuth Provider (Google/GitHub) → Callback
  → Get User Info → Create/Link User → Generate JWT
```

### 2. Database Layer

**Connection Pooling** (SQLAlchemy + PgBouncer):

```python
# Application-level pooling
engine = create_engine(
    DATABASE_URL,
    pool_size=20,           # 20 persistent connections
    max_overflow=10,        # + 10 temporary connections
    pool_pre_ping=True,     # Verify connections
    pool_recycle=3600       # Recycle after 1 hour
)
```

**Plus PgBouncer**:
- Transaction-level pooling
- 1000 client connections → 50 database connections
- Reduces database load

**Primary/Replica Architecture**:
- **Primary**: All writes
- **Replica**: Read-only queries (reports, analytics)
- Replication lag: ~100ms

### 3. Caching Layer (Redis)

**Use Cases**:
1. **Prediction Cache**: Cache by image hash
   - TTL: 1 hour
   - Hit rate: ~30-40%

2. **Rate Limiting**: Token bucket algorithm
   - 60 requests/minute per user
   - 1000 requests/hour per tenant

3. **Session Storage**: Refresh tokens

**Cache Invalidation**:
- Time-based (TTL)
- Event-based (on data update)

### 4. Audit Logging

**What's Logged**:
- User authentication (login, logout, failed attempts)
- All CRUD operations (create, update, delete)
- Permission denied events
- API errors

**Log Structure**:
```json
{
  "log_id": "uuid",
  "tenant_id": 1,
  "user_id": 123,
  "action": "prediction:create",
  "resource": "prediction",
  "resource_id": "pred-456",
  "ip_address": "192.168.1.1",
  "user_agent": "Mozilla/5.0...",
  "request_id": "correlation-id",
  "status": "success",
  "timestamp": "2025-11-06T10:30:45Z"
}
```

---

## Data Flow

### Prediction Request Flow

```
┌─────────┐
│ Client  │
└────┬────┘
     │ 1. POST /predict + JWT
     ▼
┌────────────────┐
│ Load Balancer  │
└────┬───────────┘
     │ 2. Route to pod
     ▼
┌────────────────────────────────────────┐
│ FastAPI Pod                            │
│                                        │
│ 3. TenantMiddleware                    │
│    └─ Extract tenant from JWT         │
│                                        │
│ 4. JWT Verification                    │
│    └─ Validate token, extract user    │
│                                        │
│ 5. RBAC Check                          │
│    └─ Verify "prediction:create"      │
│                                        │
│ 6. Rate Limiter                        │
│    └─ Check Redis: 60/min OK?         │
│                                        │
│ 7. Check Cache (Redis)                │
│    └─ Hash image, check cache         │
│    └─ If HIT: return cached result    │
│                                        │
│ 8. ML Inference (if MISS)              │
│    └─ Load model                       │
│    └─ Preprocess image                │
│    └─ EfficientNet-B0 inference       │
│    └─ Post-process results            │
│                                        │
│ 9. Save to Database                    │
│    └─ Write to predictions table      │
│    └─ Multi-tenancy enforced          │
│                                        │
│ 10. Update Cache                       │
│    └─ Store result in Redis           │
│                                        │
│ 11. Audit Log                          │
│    └─ Log prediction created          │
│                                        │
│ 12. Metrics                            │
│    └─ Increment Prometheus counters   │
│                                        │
│ 13. Return Response                    │
└────┬───────────────────────────────────┘
     │ 14. JSON Response
     ▼
┌─────────┐
│ Client  │
└─────────┘
```

**Timing Breakdown**:
- Authentication: ~5ms
- RBAC Check: ~2ms
- Rate Limit Check: ~1ms
- Cache Check: ~1ms
- ML Inference: ~80ms (CPU)
- Database Write: ~5ms
- **Total**: ~95ms

---

## Security Architecture

### Defense in Depth

| Layer | Security Measure |
|-------|------------------|
| **Network** | TLS 1.3, Firewall rules, VPC isolation |
| **Ingress** | Rate limiting, DDoS protection, WAF |
| **API** | JWT validation, CORS, CSRF protection |
| **Application** | Input validation, SQL injection prevention, XSS filtering |
| **Authorization** | RBAC, Multi-tenancy isolation, Audit logs |
| **Data** | Encryption at rest, Encrypted connections (TLS) |
| **Infrastructure** | Non-root containers, Read-only FS, Security scanning |

### Threat Model

| Threat | Mitigation |
|--------|------------|
| **SQL Injection** | SQLAlchemy ORM (parameterized queries) |
| **XSS** | FastAPI auto-escaping, Content Security Policy |
| **CSRF** | Token-based auth (no cookies) |
| **Authentication Bypass** | JWT signature verification, Short expiration |
| **Privilege Escalation** | RBAC enforcement, Permission checks |
| **Data Breach** | Multi-tenancy isolation, Encryption at rest |
| **DoS** | Rate limiting, Circuit breakers, Auto-scaling |
| **Insider Threat** | Audit logging, Role separation |

---

## Scalability & Performance

### Horizontal Scaling

**Auto-scaling Configuration**:
```yaml
HorizontalPodAutoscaler:
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - CPU: 70%
    - Memory: 80%
  scaleUp: +100% every 30s (max +2 pods)
  scaleDown: -50% every 60s (stabilization: 5min)
```

**Scaling Triggers**:
- **CPU > 70%**: Scale up
- **Memory > 80%**: Scale up
- **Request queue depth > 100**: Scale up
- **Low utilization (5min)**: Scale down

### Performance Optimization

1. **Model Loading**: Singleton pattern (loaded once per pod)
2. **Image Preprocessing**: Vectorized operations (NumPy)
3. **Database**: Connection pooling, indexed queries
4. **Caching**: Redis for frequently accessed data
5. **Async I/O**: FastAPI async endpoints (where applicable)

### Capacity Planning

**Single Pod**:
- Memory: 512MB-2GB
- CPU: 0.5-2 cores
- Throughput: ~11 req/sec (with model inference)

**20 Pods** (max scale):
- Throughput: ~220 req/sec
- Concurrent users: ~2000
- Daily predictions: ~19M

---

## Deployment Architecture

### Blue-Green Deployment

```
┌────────────────────────────────────────┐
│  Load Balancer / Service              │
│  ┌──────────────────────────────────┐ │
│  │  Selector: version=blue          │ │
│  └──────────┬───────────────────────┘ │
└─────────────┼──────────────────────────┘
              │
    ┌─────────┴─────────┐
    │                   │
┌───▼──────┐     ┌──────▼───┐
│  Blue    │     │  Green   │
│ (Active) │     │ (Standby)│
│          │     │          │
│ v1.0.0   │     │ v1.1.0   │
│ 3 pods   │     │ 3 pods   │
└──────────┘     └──────────┘
```

**Deployment Steps**:
1. Deploy green version (new code)
2. Run smoke tests on green
3. Switch traffic: `selector: version=green`
4. Monitor for issues (5-15 minutes)
5. If OK: Delete blue
6. If issues: Instant rollback to blue

### Canary Deployment (Alternative)

```
Traffic Split:
┌────────────┐
│ 95% → v1.0 │ (Stable)
│  5% → v1.1 │ (Canary)
└────────────┘
      ↓
Gradual increase:
95/5 → 90/10 → 70/30 → 50/50 → 0/100
```

---

## Monitoring & Observability

### Metrics (Prometheus)

**Application Metrics**:
- `http_requests_total{method, path, status}`
- `http_request_duration_seconds{method, path}`
- `prediction_total{tenant_id, label}`
- `prediction_duration_seconds`
- `cache_hit_total` / `cache_miss_total`
- `circuit_breaker_state{name}`

**Infrastructure Metrics**:
- `container_cpu_usage_seconds_total`
- `container_memory_usage_bytes`
- `postgres_connections{state}`
- `redis_commands_total{command}`

### Logging (Structured JSON)

```json
{
  "timestamp": "2025-11-06T10:30:45.123Z",
  "level": "INFO",
  "message": "Prediction created",
  "correlation_id": "req-abc-123",
  "tenant_id": 1,
  "user_id": 456,
  "prediction_id": "pred-789",
  "processing_time_ms": 87.3,
  "cache_hit": false
}
```

### Alerts

| Alert | Condition | Severity |
|-------|-----------|----------|
| High Error Rate | Error rate > 5% (5min) | Critical |
| High Latency | p95 latency > 500ms (5min) | Warning |
| Pod Crash Loop | 3+ restarts in 10min | Critical |
| Database Connections | > 80% pool used | Warning |
| Circuit Breaker Open | Open for > 5min | Warning |
| Disk Space | < 10% free | Critical |

---

## Design Decisions

### Why FastAPI?
- ✅ Async support (high concurrency)
- ✅ Auto-generated OpenAPI docs
- ✅ Built-in data validation (Pydantic)
- ✅ Fast development, production-ready
- ❌ Alternative: Flask (older, synchronous)

### Why PostgreSQL?
- ✅ ACID compliance (critical for medical data)
- ✅ Rich data types (JSON, Arrays)
- ✅ Strong ecosystem (pgbouncer, replicas)
- ✅ Mature and battle-tested
- ❌ Alternative: MongoDB (eventual consistency issues)

### Why EfficientNet-B0?
- ✅ Good accuracy/speed tradeoff
- ✅ Pre-trained on ImageNet
- ✅ Lightweight (51MB model)
- ✅ CPU-friendly inference (~87ms)
- ❌ Alternative: EfficientNet-B7 (better accuracy, slower)

### Why Redis?
- ✅ Fast (in-memory)
- ✅ Multiple data structures (strings, hashes, sorted sets)
- ✅ Built-in expiration (TTL)
- ✅ Pub/Sub capabilities
- ❌ Alternative: Memcached (less features)

### Why Kubernetes?
- ✅ Auto-scaling (HPA)
- ✅ Self-healing (liveness/readiness probes)
- ✅ Rolling updates (zero downtime)
- ✅ Service discovery
- ✅ Cloud-agnostic
- ❌ Alternative: Docker Swarm (simpler, less features)

---

## Future Enhancements

### Short-term (Next 3 months)
- [ ] Async refactor (database queries, Redis calls)
- [ ] gRPC support (for service-to-service)
- [ ] GraphQL API (flexible queries)
- [ ] Real-time notifications (WebSockets)

### Medium-term (6-12 months)
- [ ] Model versioning (A/B test models)
- [ ] Explainable AI (Grad-CAM visualizations)
- [ ] Federated learning (privacy-preserving)
- [ ] Mobile app (Flutter/React Native)

### Long-term (12+ months)
- [ ] Multi-disease detection (DR, AMD, etc.)
- [ ] Video analysis (optic nerve head videos)
- [ ] Integration with EHR systems (HL7 FHIR)
- [ ] Edge deployment (on-device inference)

---

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Kubernetes Best Practices](https://kubernetes.io/docs/concepts/)
- [12-Factor App Methodology](https://12factor.net)
- [Martin Fowler: Circuit Breaker](https://martinfowler.com/bliki/CircuitBreaker.html)
- [Multi-Tenancy in SaaS](https://docs.microsoft.com/en-us/azure/architecture/guide/multitenant/approaches/overview)

---

**Last Updated**: 2025-11-06
**Version**: 1.0.0
