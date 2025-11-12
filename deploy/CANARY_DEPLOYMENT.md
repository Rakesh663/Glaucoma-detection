# Canary Deployment Guide

## Overview

Canary deployment is a progressive delivery strategy that reduces the risk of introducing new versions by gradually rolling out changes to a small subset of users before making it available to everyone.

## Architecture

```
                          ┌─────────────────┐
                          │  Load Balancer  │
                          └────────┬────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
            10% Traffic                   90% Traffic
                    │                             │
          ┌─────────▼─────────┐         ┌─────────▼─────────┐
          │  Canary Version   │         │  Stable Version   │
          │    (v2.0.0)       │         │    (v1.0.0)       │
          └───────────────────┘         └───────────────────┘
                    │                             │
                    └──────────────┬──────────────┘
                                   │
                          ┌────────▼────────┐
                          │   Prometheus    │
                          │   Monitoring    │
                          └─────────────────┘
```

## Deployment Methods

### Method 1: Automated Canary with Flagger

Flagger automates the canary deployment process with built-in analysis and rollback.

#### Prerequisites

1. Install Flagger:
```bash
kubectl apply -k github.com/fluxcd/flagger/kustomize/istio
```

2. Install Prometheus (for metrics):
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/prometheus -n monitoring
```

#### Deploy

```bash
# Apply canary configuration
kubectl apply -f deploy/kubernetes/canary-deployment.yaml

# Monitor canary progress
kubectl -n glaucoma describe canary glaucoma-api-canary

# Watch events
kubectl -n glaucoma get events --watch
```

#### Flagger Configuration

The canary configuration includes:
- **Initial Traffic**: Starts at 0%
- **Step Weight**: Increases by 10% per interval
- **Max Weight**: Maximum 50% canary traffic
- **Interval**: Metrics checked every 30 seconds
- **Threshold**: Rollback after 5 failed checks

**Success Criteria**:
- Request success rate ≥ 99%
- P99 latency ≤ 2 seconds
- Prediction accuracy ≥ 85%

### Method 2: Manual Canary Deployment

For environments without Flagger, use the manual deployment script.

#### Deploy Canary

```bash
# Deploy version v2.0.0 with 10% traffic for 5 minutes
./deploy/canary-deploy.sh v2.0.0 10 300 10

# Parameters:
# 1. Version (required)
# 2. Initial canary percentage (default: 10)
# 3. Monitoring duration in seconds (default: 300)
# 4. Traffic increment per step (default: 10)
```

#### What the script does:

1. **Deploy Canary**
   - Creates a new deployment with `-canary` suffix
   - Deploys 1 replica initially
   - Waits for health checks to pass

2. **Traffic Splitting**
   - Routes specified % of traffic to canary
   - Uses Istio VirtualService for traffic control
   - Monitors metrics continuously

3. **Progressive Rollout**
   - Incrementally increases traffic by step percentage
   - Monitors error rate and latency
   - Requires manual approval at each step

4. **Automatic Rollback**
   - Rolls back if error rate > 5%
   - Rolls back if deployment becomes unhealthy
   - Preserves stable version

5. **Promotion**
   - Updates stable deployment to new version
   - Removes canary deployment
   - Resets traffic to 100% stable

#### Rollback Manually

```bash
./deploy/rollback-canary.sh
```

### Method 3: GitHub Actions Workflow

Trigger canary deployment via GitHub Actions for full CI/CD integration.

#### Trigger Workflow

1. Go to Actions tab in GitHub
2. Select "Canary Deployment" workflow
3. Click "Run workflow"
4. Fill in parameters:
   - Version: `v2.0.0`
   - Initial traffic: `10`
   - Auto promote: `false` (for manual approval)
   - Environment: `production`

#### Workflow Steps

1. **Validate Prerequisites**
   - Checks stable deployment exists
   - Validates version format

2. **Deploy Canary**
   - Creates canary deployment
   - Configures traffic split
   - Sends Slack notification

3. **Monitor Metrics**
   - Monitors for 5 minutes
   - Checks error rate (must be < 5%)
   - Checks P99 latency (must be < 2s)
   - Auto-rollback on failure

4. **Promote (Manual or Auto)**
   - Gradually increases traffic: 20% → 50% → 75% → 100%
   - Updates stable deployment
   - Cleans up canary
   - Creates git tag

## Monitoring

### Key Metrics to Watch

1. **Error Rate**
   ```promql
   sum(rate(http_requests_total{status_code=~"5.."}[1m]))
   /
   sum(rate(http_requests_total[1m])) * 100
   ```

2. **Request Duration (P99)**
   ```promql
   histogram_quantile(0.99,
     sum(rate(http_request_duration_seconds_bucket[1m])) by (le)
   )
   ```

3. **Prediction Accuracy**
   ```promql
   avg(prediction_confidence{result="positive"}) * 100
   ```

4. **Request Rate**
   ```promql
   sum(rate(http_requests_total[1m])) by (version)
   ```

### Grafana Dashboard

Access the canary dashboard at:
```
http://grafana.example.com/d/canary/canary-deployment
```

Key panels:
- Traffic split percentage
- Error rate by version
- Latency comparison (stable vs canary)
- Prediction metrics by version

## Best Practices

### 1. Start Small
- Begin with 5-10% traffic
- Monitor closely for first 10-15 minutes
- Increase gradually in 10-20% increments

### 2. Define Clear Success Criteria
- **Error Rate**: < 1% (recommended), < 5% (maximum)
- **Latency**: P99 < 2s
- **Accuracy**: Maintain or improve prediction confidence
- **Memory/CPU**: Within resource limits

### 3. Monitor Business Metrics
- User complaints/feedback
- Prediction accuracy in production
- False positive/negative rates
- API usage patterns

### 4. Have a Rollback Plan
- Always keep stable version running
- Test rollback procedure regularly
- Document rollback triggers
- Keep communication channels open

### 5. Timing
- Deploy during low-traffic periods initially
- Avoid deployments before weekends/holidays
- Have team available to monitor
- Schedule at least 2 hours for full rollout

## Traffic Split Strategies

### Conservative (Recommended for Production)
```
5% → 10% → 25% → 50% → 75% → 100%
Monitor: 10 min between each step
Total time: ~1 hour
```

### Moderate
```
10% → 25% → 50% → 100%
Monitor: 5 min between each step
Total time: ~20 minutes
```

### Aggressive (Staging Only)
```
20% → 50% → 100%
Monitor: 2 min between each step
Total time: ~6 minutes
```

## Rollback Triggers

Automatically rollback if:
- Error rate > 5%
- P99 latency > 2 seconds
- Canary pods become unhealthy
- Memory/CPU exceeds limits
- Manual trigger (emergency)

Manually consider rollback if:
- Increased user complaints
- Decreased prediction accuracy
- Unexpected behavior in logs
- Business metric degradation

## Example Scenarios

### Scenario 1: Model Update

Deploying new glaucoma detection model (v2.0):

```bash
# 1. Deploy canary with 10% traffic
./deploy/canary-deploy.sh v2.0.0 10 300 10

# 2. Monitor prediction accuracy
kubectl logs -f deployment/glaucoma-api-canary -n glaucoma | grep "prediction"

# 3. Compare with stable version
# Check Grafana dashboard for side-by-side metrics

# 4. If metrics are good, continue to next step (20%)
# Answer 'y' when prompted

# 5. Repeat until 100%
```

### Scenario 2: API Performance Improvement

Deploying optimized API (v1.5.0):

```bash
# Focus on latency metrics
./deploy/canary-deploy.sh v1.5.0 10 600 10

# Monitor P99 latency closely
# Expected: Lower latency in canary vs stable
```

### Scenario 3: Emergency Rollback

If issues detected during canary:

```bash
# Immediate rollback
./deploy/rollback-canary.sh

# Or via kubectl
kubectl delete deployment glaucoma-api-canary -n glaucoma
kubectl apply -f deploy/kubernetes/istio-virtualservice.yaml
# (with 100% stable traffic)
```

## Troubleshooting

### Canary pods not starting

```bash
# Check pod status
kubectl get pods -n glaucoma -l track=canary

# Check events
kubectl describe deployment glaucoma-api-canary -n glaucoma

# Check logs
kubectl logs -n glaucoma deployment/glaucoma-api-canary
```

### Traffic not splitting correctly

```bash
# Verify VirtualService
kubectl get virtualservice glaucoma-api -n glaucoma -o yaml

# Check Istio proxy
kubectl logs -n glaucoma deployment/glaucoma-api -c istio-proxy

# Test traffic distribution
for i in {1..100}; do
  curl -s http://glaucoma-api/health | grep version
done | sort | uniq -c
```

### Metrics not available

```bash
# Check Prometheus targets
kubectl port-forward -n monitoring svc/prometheus 9090:9090
# Open http://localhost:9090/targets

# Verify metrics endpoint
kubectl exec -n glaucoma deployment/glaucoma-api-canary -- \
  curl localhost:8000/metrics
```

## Reference

### Files
- `deploy/kubernetes/canary-deployment.yaml` - Flagger configuration
- `deploy/canary-deploy.sh` - Manual deployment script
- `deploy/rollback-canary.sh` - Rollback script
- `.github/workflows/canary-deploy.yml` - GitHub Actions workflow

### Commands
```bash
# View canary status
kubectl get canaries -n glaucoma

# View traffic split
kubectl get virtualservice glaucoma-api -n glaucoma

# Monitor in real-time
watch -n 5 'kubectl get pods -n glaucoma -l app=glaucoma-api'

# Check metrics
kubectl exec -n monitoring deployment/prometheus -- \
  promtool query instant http://localhost:9090 \
  'rate(http_requests_total[1m])'
```

### Resources
- [Flagger Documentation](https://docs.flagger.app/)
- [Istio Traffic Management](https://istio.io/latest/docs/concepts/traffic-management/)
- [Canary Deployments Best Practices](https://martinfowler.com/bliki/CanaryRelease.html)
