#!/bin/bash
# Infrastructure Drift Detection Script
# Checks for differences between IaC definitions and live infrastructure

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="${NAMESPACE:-glaucoma}"
MANIFESTS_DIR="deploy/kubernetes"
OUTPUT_DIR="drift-reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}Infrastructure Drift Detection${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Report file
REPORT_FILE="$OUTPUT_DIR/drift-report-$TIMESTAMP.md"

# Initialize report
cat > "$REPORT_FILE" <<EOF
# Infrastructure Drift Detection Report

**Generated**: $(date -u +'%Y-%m-%d %H:%M:%S UTC')
**Namespace**: $NAMESPACE
**Manifests Directory**: $MANIFESTS_DIR

---

EOF

# Function to check Kubernetes drift
check_k8s_drift() {
    echo -e "${YELLOW}Checking Kubernetes manifests...${NC}"

    echo "## Kubernetes Manifest Drift" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"

    DRIFT_FOUND=false

    for manifest in "$MANIFESTS_DIR"/*.yaml; do
        if [ ! -f "$manifest" ]; then
            continue
        fi

        MANIFEST_NAME=$(basename "$manifest")
        echo "  Checking $MANIFEST_NAME..."

        # Run kubectl diff
        DIFF_OUTPUT=$(kubectl diff -f "$manifest" -n "$NAMESPACE" 2>&1 || true)

        if [ -n "$DIFF_OUTPUT" ]; then
            echo -e "${RED}    ❌ Drift detected${NC}"

            echo "### $MANIFEST_NAME" >> "$REPORT_FILE"
            echo "" >> "$REPORT_FILE"
            echo '```diff' >> "$REPORT_FILE"
            echo "$DIFF_OUTPUT" >> "$REPORT_FILE"
            echo '```' >> "$REPORT_FILE"
            echo "" >> "$REPORT_FILE"

            DRIFT_FOUND=true
        else
            echo -e "${GREEN}    ✓ No drift${NC}"
        fi
    done

    if [ "$DRIFT_FOUND" = false ]; then
        echo "✅ No drift detected in manifests" >> "$REPORT_FILE"
        echo ""
    fi

    echo ""
}

# Function to check for orphaned resources
check_orphaned_resources() {
    echo -e "${YELLOW}Checking for orphaned resources...${NC}"

    echo "## Orphaned Resources" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    echo "Resources in cluster but not defined in IaC:" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"

    # Get all resource types
    RESOURCE_TYPES="deployments,services,configmaps,secrets,ingresses,persistentvolumeclaims,statefulsets"

    for resource_type in ${RESOURCE_TYPES//,/ }; do
        echo "  Checking $resource_type..."

        # Get resources from cluster
        CLUSTER_RESOURCES=$(kubectl get "$resource_type" -n "$NAMESPACE" -o name 2>/dev/null || true)

        if [ -z "$CLUSTER_RESOURCES" ]; then
            continue
        fi

        echo "### $resource_type" >> "$REPORT_FILE"

        FOUND_ORPHANS=false

        while IFS= read -r resource; do
            RESOURCE_NAME=$(echo "$resource" | cut -d'/' -f2)

            # Check if resource exists in manifests
            if ! grep -r "name: $RESOURCE_NAME" "$MANIFESTS_DIR" > /dev/null 2>&1; then
                # Exclude system resources
                if [[ ! "$RESOURCE_NAME" =~ ^(default-token|kube-|kubernetes-) ]]; then
                    echo "- ⚠️  \`$RESOURCE_NAME\` (not in IaC)" >> "$REPORT_FILE"
                    echo -e "${YELLOW}    ⚠️  Orphaned: $RESOURCE_NAME${NC}"
                    FOUND_ORPHANS=true
                fi
            fi
        done <<< "$CLUSTER_RESOURCES"

        if [ "$FOUND_ORPHANS" = false ]; then
            echo "- None" >> "$REPORT_FILE"
        fi

        echo "" >> "$REPORT_FILE"
    done

    echo ""
}

# Function to check configuration drift
check_config_drift() {
    echo -e "${YELLOW}Checking configuration drift...${NC}"

    echo "## Configuration Drift" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"

    # Check ConfigMaps
    echo "### ConfigMaps" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"

    for cm in $(kubectl get configmap -n "$NAMESPACE" -o name 2>/dev/null || true); do
        CM_NAME=$(echo "$cm" | cut -d'/' -f2)

        # Get live config
        kubectl get "$cm" -n "$NAMESPACE" -o yaml > "/tmp/live-$CM_NAME.yaml" 2>/dev/null || continue

        # Find in manifests
        MANIFEST_FILE=$(grep -l "name: $CM_NAME" "$MANIFESTS_DIR"/*.yaml 2>/dev/null | head -1)

        if [ -n "$MANIFEST_FILE" ]; then
            # Extract ConfigMap from manifest
            kubectl create --dry-run=client -o yaml -f "$MANIFEST_FILE" > "/tmp/expected-$CM_NAME.yaml" 2>/dev/null || continue

            # Compare (ignoring metadata)
            DIFF=$(diff <(yq e '.data' "/tmp/expected-$CM_NAME.yaml" 2>/dev/null || echo "{}") \
                        <(yq e '.data' "/tmp/live-$CM_NAME.yaml" 2>/dev/null || echo "{}") || true)

            if [ -n "$DIFF" ]; then
                echo "- ⚠️  \`$CM_NAME\` has configuration drift:" >> "$REPORT_FILE"
                echo '```diff' >> "$REPORT_FILE"
                echo "$DIFF" >> "$REPORT_FILE"
                echo '```' >> "$REPORT_FILE"
                echo -e "${YELLOW}    ⚠️  Config drift: $CM_NAME${NC}"
            fi
        fi
    done

    # Cleanup
    rm -f /tmp/live-*.yaml /tmp/expected-*.yaml

    echo ""
}

# Function to check image drift
check_image_drift() {
    echo -e "${YELLOW}Checking image versions...${NC}"

    echo "## Image Version Drift" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"

    # Get expected images from manifests
    echo "### Expected Images (from manifests):" >> "$REPORT_FILE"
    echo '```' >> "$REPORT_FILE"
    grep -h "image:" "$MANIFESTS_DIR"/*.yaml 2>/dev/null | sed 's/^[[:space:]]*//' | sort -u >> "$REPORT_FILE"
    echo '```' >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"

    # Get running images
    echo "### Running Images (in cluster):" >> "$REPORT_FILE"
    echo '```' >> "$REPORT_FILE"
    kubectl get pods -n "$NAMESPACE" \
        -o custom-columns=POD:.metadata.name,IMAGE:.spec.containers[*].image \
        2>/dev/null >> "$REPORT_FILE" || echo "No pods found" >> "$REPORT_FILE"
    echo '```' >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"

    # Compare
    echo "### Drift Analysis:" >> "$REPORT_FILE"

    PODS=$(kubectl get pods -n "$NAMESPACE" -o name 2>/dev/null || true)

    if [ -z "$PODS" ]; then
        echo "- No pods running" >> "$REPORT_FILE"
    else
        while IFS= read -r pod; do
            POD_NAME=$(echo "$pod" | cut -d'/' -f2)
            RUNNING_IMAGE=$(kubectl get "$pod" -n "$NAMESPACE" -o jsonpath='{.spec.containers[0].image}' 2>/dev/null || echo "unknown")

            # Check if image is in manifests
            if ! grep -q "$RUNNING_IMAGE" "$MANIFESTS_DIR"/*.yaml 2>/dev/null; then
                echo "- ⚠️  \`$POD_NAME\`: Image \`$RUNNING_IMAGE\` not in manifests" >> "$REPORT_FILE"
                echo -e "${YELLOW}    ⚠️  Image drift: $POD_NAME${NC}"
            else
                echo -e "${GREEN}    ✓ $POD_NAME: correct image${NC}"
            fi
        done <<< "$PODS"
    fi

    echo ""
}

# Function to check resource quotas
check_resource_drift() {
    echo -e "${YELLOW}Checking resource specifications...${NC}"

    echo "" >> "$REPORT_FILE"
    echo "## Resource Specification Drift" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"

    # Compare resource requests/limits
    for deployment in $(kubectl get deployments -n "$NAMESPACE" -o name 2>/dev/null || true); do
        DEPLOY_NAME=$(echo "$deployment" | cut -d'/' -f2)

        # Get live resources
        LIVE_RESOURCES=$(kubectl get "$deployment" -n "$NAMESPACE" \
            -o jsonpath='{.spec.template.spec.containers[0].resources}' 2>/dev/null || echo "{}")

        # Find in manifests
        MANIFEST_FILE=$(grep -l "name: $DEPLOY_NAME" "$MANIFESTS_DIR"/*.yaml 2>/dev/null | head -1)

        if [ -n "$MANIFEST_FILE" ]; then
            # Compare (basic check)
            if ! grep -q "resources:" "$MANIFEST_FILE" 2>/dev/null; then
                if [ "$LIVE_RESOURCES" != "{}" ]; then
                    echo "- ⚠️  \`$DEPLOY_NAME\`: Resources defined in cluster but not in manifest" >> "$REPORT_FILE"
                    echo -e "${YELLOW}    ⚠️  Resource drift: $DEPLOY_NAME${NC}"
                fi
            fi
        fi
    done

    echo ""
}

# Function to generate summary
generate_summary() {
    echo "" >> "$REPORT_FILE"
    echo "---" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    echo "## Summary" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"

    DRIFT_COUNT=$(grep -c "⚠️" "$REPORT_FILE" || echo "0")
    ERROR_COUNT=$(grep -c "❌" "$REPORT_FILE" || echo "0")

    echo "- **Drift Issues**: $DRIFT_COUNT" >> "$REPORT_FILE"
    echo "- **Critical Differences**: $ERROR_COUNT" >> "$REPORT_FILE"
    echo "- **Report Location**: \`$REPORT_FILE\`" >> "$REPORT_FILE"

    if [ "$DRIFT_COUNT" -gt 0 ] || [ "$ERROR_COUNT" -gt 0 ]; then
        echo "" >> "$REPORT_FILE"
        echo "### Recommended Actions" >> "$REPORT_FILE"
        echo "" >> "$REPORT_FILE"
        echo "1. **Review** each drift item carefully" >> "$REPORT_FILE"
        echo "2. **Decide** if changes are intentional or unauthorized" >> "$REPORT_FILE"
        echo "3. **Update** manifests if changes are intentional" >> "$REPORT_FILE"
        echo "4. **Apply** manifests to restore desired state if unauthorized" >> "$REPORT_FILE"
        echo "5. **Document** exceptions in \`drift-exceptions.yaml\`" >> "$REPORT_FILE"
    fi

    echo ""
    echo -e "${BLUE}======================================${NC}"
    echo -e "${BLUE}Drift Detection Summary${NC}"
    echo -e "${BLUE}======================================${NC}"
    echo -e "Drift Issues: ${YELLOW}$DRIFT_COUNT${NC}"
    echo -e "Critical Differences: ${RED}$ERROR_COUNT${NC}"
    echo -e "Report: ${GREEN}$REPORT_FILE${NC}"
    echo ""

    if [ "$DRIFT_COUNT" -eq 0 ] && [ "$ERROR_COUNT" -eq 0 ]; then
        echo -e "${GREEN}✓ No drift detected. Infrastructure matches IaC.${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️  Drift detected. Review the report for details.${NC}"
        return 1
    fi
}

# Main execution
main() {
    check_k8s_drift
    check_orphaned_resources
    check_config_drift
    check_image_drift
    check_resource_drift
    generate_summary

    # Open report if available
    if command -v xdg-open > /dev/null 2>&1; then
        echo ""
        echo "Opening report..."
        xdg-open "$REPORT_FILE" 2>/dev/null || true
    elif command -v open > /dev/null 2>&1; then
        echo ""
        echo "Opening report..."
        open "$REPORT_FILE" 2>/dev/null || true
    fi
}

# Run
main
EXIT_CODE=$?

exit $EXIT_CODE
