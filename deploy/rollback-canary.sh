#!/bin/bash
# Canary Rollback Script
# Quickly rollback a failed canary deployment

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="${NAMESPACE:-glaucoma}"
APP_NAME="${APP_NAME:-glaucoma-api}"

echo -e "${RED}======================================${NC}"
echo -e "${RED}ROLLING BACK CANARY DEPLOYMENT${NC}"
echo -e "${RED}======================================${NC}"

# Step 1: Shift all traffic back to stable
echo -e "\n${YELLOW}Step 1: Shifting 100% traffic to stable version${NC}"

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
    - destination:
        host: ${APP_NAME}
        subset: canary
      weight: 0
EOF

echo "Traffic shifted to stable version"

# Step 2: Delete canary deployment
echo -e "\n${YELLOW}Step 2: Removing canary deployment${NC}"

kubectl delete deployment ${APP_NAME}-canary -n ${NAMESPACE} --ignore-not-found=true

echo "Canary deployment removed"

# Step 3: Verify stable deployment health
echo -e "\n${YELLOW}Step 3: Verifying stable deployment health${NC}"

REPLICAS=$(kubectl get deployment ${APP_NAME} -n ${NAMESPACE} -o jsonpath='{.status.replicas}')
READY=$(kubectl get deployment ${APP_NAME} -n ${NAMESPACE} -o jsonpath='{.status.readyReplicas}')

if [ "$REPLICAS" == "$READY" ] && [ "$READY" != "0" ]; then
    echo -e "${GREEN}✓ Stable deployment is healthy (${READY}/${REPLICAS} replicas ready)${NC}"
else
    echo -e "${RED}⚠ Warning: Stable deployment may be unhealthy (${READY}/${REPLICAS} replicas ready)${NC}"
fi

# Step 4: Get current metrics
echo -e "\n${YELLOW}Current metrics:${NC}"

# Get error rate
ERROR_RATE=$(kubectl exec -n monitoring deployment/prometheus -c prometheus -- \
    promtool query instant 'http://localhost:9090' \
    "sum(rate(http_requests_total{deployment=\"${APP_NAME}\",status_code=~\"5..\"}[1m])) / sum(rate(http_requests_total{deployment=\"${APP_NAME}\"}[1m])) * 100" \
    2>/dev/null | grep -oP '\d+\.\d+' || echo "0")

echo "  Error rate: ${ERROR_RATE}%"

# Get average response time
AVG_RESPONSE=$(kubectl exec -n monitoring deployment/prometheus -c prometheus -- \
    promtool query instant 'http://localhost:9090' \
    "histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{deployment=\"${APP_NAME}\"}[1m])) by (le))" \
    2>/dev/null | grep -oP '\d+\.\d+' || echo "0")

echo "  Avg response time: ${AVG_RESPONSE}s"

# Step 5: Clean up any leftover resources
echo -e "\n${YELLOW}Step 5: Cleaning up resources${NC}"

# Remove canary-specific ConfigMaps if any
kubectl delete configmap -n ${NAMESPACE} -l track=canary --ignore-not-found=true

# Remove canary-specific Secrets if any
kubectl delete secret -n ${NAMESPACE} -l track=canary --ignore-not-found=true

echo -e "\n${GREEN}✓ Rollback complete!${NC}"
echo -e "${GREEN}Stable version is now serving 100% of traffic${NC}"

# Log rollback event
CURRENT_VERSION=$(kubectl get deployment ${APP_NAME} -n ${NAMESPACE} -o jsonpath='{.spec.template.spec.containers[0].image}' | cut -d':' -f2)

cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Event
metadata:
  name: canary-rollback-$(date +%s)
  namespace: ${NAMESPACE}
message: "Canary deployment rolled back. Stable version: ${CURRENT_VERSION}"
reason: CanaryRollback
type: Warning
involvedObject:
  apiVersion: apps/v1
  kind: Deployment
  name: ${APP_NAME}
  namespace: ${NAMESPACE}
EOF

echo -e "\n${YELLOW}Rollback event logged${NC}"
