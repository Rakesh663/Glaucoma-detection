#!/bin/bash
# Canary Deployment Script
# This script performs a manual canary deployment with gradual traffic shifting

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="${NAMESPACE:-glaucoma}"
APP_NAME="${APP_NAME:-glaucoma-api}"
NEW_VERSION="${1}"
CANARY_PERCENTAGE="${2:-10}"  # Default 10%
MONITORING_DURATION="${3:-300}"  # Default 5 minutes
STEP_PERCENTAGE="${4:-10}"  # Traffic increment per step

# Validate arguments
if [ -z "$NEW_VERSION" ]; then
    echo -e "${RED}Error: Version number required${NC}"
    echo "Usage: $0 <version> [canary_percentage] [monitoring_duration] [step_percentage]"
    echo "Example: $0 v2.0.0 10 300 10"
    exit 1
fi

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}Canary Deployment for $APP_NAME${NC}"
echo -e "${GREEN}Version: $NEW_VERSION${NC}"
echo -e "${GREEN}======================================${NC}"

# Function to check deployment health
check_deployment_health() {
    local deployment=$1
    local replicas=$(kubectl get deployment $deployment -n $NAMESPACE -o jsonpath='{.status.replicas}')
    local ready=$(kubectl get deployment $deployment -n $NAMESPACE -o jsonpath='{.status.readyReplicas}')

    if [ "$replicas" == "$ready" ] && [ "$ready" != "0" ]; then
        return 0
    else
        return 1
    fi
}

# Function to get error rate from Prometheus
get_error_rate() {
    local deployment=$1

    # Query Prometheus for 5xx error rate
    kubectl exec -n monitoring deployment/prometheus -c prometheus -- \
        promtool query instant 'http://localhost:9090' \
        "sum(rate(http_requests_total{deployment=\"$deployment\",status_code=~\"5..\"}[1m])) / sum(rate(http_requests_total{deployment=\"$deployment\"}[1m])) * 100" \
        2>/dev/null | grep -oP '\d+\.\d+' || echo "0"
}

# Function to get average response time
get_avg_response_time() {
    local deployment=$1

    kubectl exec -n monitoring deployment/prometheus -c prometheus -- \
        promtool query instant 'http://localhost:9090' \
        "histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{deployment=\"$deployment\"}[1m])) by (le))" \
        2>/dev/null | grep -oP '\d+\.\d+' || echo "0"
}

# Step 1: Deploy canary version
echo -e "\n${YELLOW}Step 1: Deploying canary version ($NEW_VERSION)${NC}"

# Create canary deployment
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${APP_NAME}-canary
  namespace: ${NAMESPACE}
  labels:
    app: ${APP_NAME}
    version: ${NEW_VERSION}
    track: canary
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ${APP_NAME}
      version: ${NEW_VERSION}
      track: canary
  template:
    metadata:
      labels:
        app: ${APP_NAME}
        version: ${NEW_VERSION}
        track: canary
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    spec:
      containers:
      - name: api
        image: glaucoma-api:${NEW_VERSION}
        ports:
        - containerPort: 8000
        env:
        - name: VERSION
          value: "${NEW_VERSION}"
        - name: TRACK
          value: "canary"
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
EOF

# Wait for canary deployment to be ready
echo "Waiting for canary deployment to be ready..."
kubectl rollout status deployment/${APP_NAME}-canary -n ${NAMESPACE} --timeout=5m

# Step 2: Configure traffic splitting
echo -e "\n${YELLOW}Step 2: Starting canary analysis with ${CANARY_PERCENTAGE}% traffic${NC}"

# Update service to include canary pods (if using native K8s services)
kubectl patch service ${APP_NAME} -n ${NAMESPACE} --type='json' \
  -p='[{"op": "remove", "path": "/spec/selector/track"}]' || true

# Set initial traffic split using weighted services
CURRENT_PERCENTAGE=0

while [ $CURRENT_PERCENTAGE -lt 100 ]; do
    NEXT_PERCENTAGE=$((CURRENT_PERCENTAGE + STEP_PERCENTAGE))
    if [ $NEXT_PERCENTAGE -gt 100 ]; then
        NEXT_PERCENTAGE=100
    fi

    echo -e "\n${YELLOW}Shifting traffic: Canary ${NEXT_PERCENTAGE}% | Stable $((100 - NEXT_PERCENTAGE))%${NC}"

    # Update traffic split (this example uses Istio VirtualService)
    # For native K8s, you would scale deployments proportionally
    cat <<EOF | kubectl apply -f -
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: ${APP_NAME}
  namespace: ${NAMESPACE}
spec:
  hosts:
  - ${APP_NAME}
  http:
  - route:
    - destination:
        host: ${APP_NAME}
        subset: stable
      weight: $((100 - NEXT_PERCENTAGE))
    - destination:
        host: ${APP_NAME}
        subset: canary
      weight: ${NEXT_PERCENTAGE}
EOF

    # Monitor for duration
    echo "Monitoring metrics for ${MONITORING_DURATION} seconds..."

    for i in $(seq 1 $((MONITORING_DURATION / 10))); do
        sleep 10

        # Check canary health
        if ! check_deployment_health "${APP_NAME}-canary"; then
            echo -e "${RED}❌ Canary deployment is unhealthy. Rolling back...${NC}"
            bash "$(dirname "$0")/rollback-canary.sh"
            exit 1
        fi

        # Check error rate
        ERROR_RATE=$(get_error_rate "${APP_NAME}-canary")
        ERROR_RATE_INT=$(echo "$ERROR_RATE" | awk '{print int($1+0.5)}')

        if [ "$ERROR_RATE_INT" -gt 5 ]; then
            echo -e "${RED}❌ High error rate detected: ${ERROR_RATE}%. Rolling back...${NC}"
            bash "$(dirname "$0")/rollback-canary.sh"
            exit 1
        fi

        # Check response time
        AVG_RESPONSE=$(get_avg_response_time "${APP_NAME}-canary")

        echo "  [$(date +%H:%M:%S)] Error rate: ${ERROR_RATE}% | Avg response: ${AVG_RESPONSE}s"
    done

    # Manual approval for next step
    if [ $NEXT_PERCENTAGE -lt 100 ]; then
        echo -e "\n${YELLOW}Current metrics look good.${NC}"
        read -p "Continue to next traffic increment? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${YELLOW}Pausing canary rollout at ${NEXT_PERCENTAGE}%${NC}"
            echo "To continue, re-run: $0 $NEW_VERSION $NEXT_PERCENTAGE"
            exit 0
        fi
    fi

    CURRENT_PERCENTAGE=$NEXT_PERCENTAGE
done

# Step 3: Promote canary to stable
echo -e "\n${YELLOW}Step 3: Promoting canary to stable${NC}"

# Update stable deployment to new version
kubectl set image deployment/${APP_NAME} api=glaucoma-api:${NEW_VERSION} -n ${NAMESPACE}
kubectl rollout status deployment/${APP_NAME} -n ${NAMESPACE} --timeout=5m

# Remove canary deployment
echo "Cleaning up canary deployment..."
kubectl delete deployment ${APP_NAME}-canary -n ${NAMESPACE}

# Reset traffic to 100% stable
cat <<EOF | kubectl apply -f -
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: ${APP_NAME}
  namespace: ${NAMESPACE}
spec:
  hosts:
  - ${APP_NAME}
  http:
  - route:
    - destination:
        host: ${APP_NAME}
        subset: stable
      weight: 100
EOF

echo -e "\n${GREEN}✓ Canary deployment successful!${NC}"
echo -e "${GREEN}Version ${NEW_VERSION} is now serving 100% of traffic${NC}"

# Final health check
echo -e "\n${YELLOW}Final health check:${NC}"
ERROR_RATE=$(get_error_rate "${APP_NAME}")
AVG_RESPONSE=$(get_avg_response_time "${APP_NAME}")
echo "  Error rate: ${ERROR_RATE}%"
echo "  Avg response time: ${AVG_RESPONSE}s"

echo -e "\n${GREEN}Deployment complete!${NC}"
