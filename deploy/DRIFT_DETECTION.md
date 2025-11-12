# Infrastructure Drift Detection Guide

## What is Infrastructure Drift?

Infrastructure drift occurs when the actual state of your infrastructure diverges from its intended state as defined in Infrastructure as Code (IaC). This can happen due to:

- Manual changes made directly to the cluster
- Automatic modifications by controllers (HPA, cert-manager, etc.)
- Failed deployments that partially apply changes
- External tools modifying resources
- Configuration updates not reflected in IaC

## Why Drift Detection Matters

1. **Security**: Unauthorized changes may introduce vulnerabilities
2. **Compliance**: Audit trails require accurate IaC
3. **Reliability**: Drift can cause unexpected behavior
4. **Reproducibility**: Ensures environments can be recreated
5. **Documentation**: IaC serves as source of truth

## Drift Detection Methods

### 1. Automated GitHub Actions Workflow

File: [.github/workflows/drift-detection.yml](../.github/workflows/drift-detection.yml)

**Schedule**: Runs every 6 hours automatically

**What it checks**:
- Kubernetes manifest drift (kubectl diff)
- Orphaned resources (resources in cluster but not in IaC)
- Configuration drift (ConfigMaps, Secrets)
- Image version drift
- Terraform state drift (if applicable)

**Notifications**:
- Creates GitHub issue on drift detection
- Sends Slack notification
- Uploads detailed reports as artifacts

**Trigger manually**:
```bash
# Via GitHub UI
# Go to Actions → Drift Detection → Run workflow

# Via GitHub CLI
gh workflow run drift-detection.yml
```

### 2. Manual Script

File: [deploy/check-drift.sh](check-drift.sh)

**Usage**:
```bash
# Run drift detection
./deploy/check-drift.sh

# With custom namespace
NAMESPACE=production ./deploy/check-drift.sh

# Output directory customization
OUTPUT_DIR=/tmp/drift ./deploy/check-drift.sh
```

**Output**: Generates markdown report in `drift-reports/` directory

### 3. Continuous Monitoring (Optional)

For production environments, consider setting up continuous drift monitoring:

```bash
# Using watch
watch -n 300 './deploy/check-drift.sh'  # Every 5 minutes

# Using cron
*/5 * * * * /path/to/check-drift.sh >> /var/log/drift.log 2>&1
```

## Understanding Drift Reports

### Report Structure

```markdown
# Infrastructure Drift Detection Report

**Generated**: 2025-01-15 14:30:00 UTC
**Namespace**: glaucoma
**Manifests Directory**: deploy/kubernetes

---

## Kubernetes Manifest Drift

### deployment.yaml
```diff
- replicas: 3
+ replicas: 5
```

## Orphaned Resources
- ⚠️  `debug-pod` (not in IaC)

## Configuration Drift
- ⚠️  `app-config` has configuration drift

## Summary
- Drift Issues: 3
- Critical Differences: 1
```

### Drift Indicators

- ✅ **No drift**: Resource matches IaC
- ⚠️ **Warning**: Potential drift detected
- ❌ **Error**: Critical difference found

## Common Drift Scenarios

### 1. HPA Scaling

**Symptom**: Replica count differs from manifest
```diff
- replicas: 2
+ replicas: 5
```

**Cause**: HorizontalPodAutoscaler scaled the deployment

**Action**: Expected behavior. Add to exceptions:
```yaml
# drift-exceptions.yaml
allowedModifications:
  - resource: Deployment
    field: spec.replicas
    managedBy: "HorizontalPodAutoscaler"
```

### 2. Manual Debugging Changes

**Symptom**: Pod found in cluster but not in IaC
```
- ⚠️  `debug-pod-12345` (not in IaC)
```

**Cause**: Developer created pod for debugging

**Action**: Delete temporary resources or document them

### 3. Configuration Updates

**Symptom**: ConfigMap data differs
```diff
ConfigMap: app-config
- LOG_LEVEL: info
+ LOG_LEVEL: debug
```

**Cause**: Manual update for troubleshooting

**Action**: Either update IaC or revert cluster change

### 4. Image Version Mismatch

**Symptom**: Running image doesn't match manifest
```
Pod: glaucoma-api-abc123
Expected: glaucoma-api:v1.0.0
Running:  glaucoma-api:v1.0.1
```

**Cause**: Deployment update not reflected in manifests

**Action**: Update manifest to match deployed version

### 5. Resource Quotas Changed

**Symptom**: Resource limits differ
```diff
- memory: 512Mi
+ memory: 1Gi
```

**Cause**: Manual resource adjustment

**Action**: Update manifest or restore original limits

## Remediation Workflow

### Step 1: Identify the Drift

Review the drift report and identify:
- **What** changed (resource, field)
- **When** it changed (check resource metadata)
- **Who** changed it (check annotations, audit logs)

```bash
# Check resource modification time
kubectl get deployment glaucoma-api -n glaucoma -o yaml | grep creationTimestamp

# Check annotations for last applied config
kubectl get deployment glaucoma-api -n glaucoma \
  -o jsonpath='{.metadata.annotations.kubectl\.kubernetes\.io/last-applied-configuration}'

# View recent events
kubectl get events -n glaucoma --sort-by='.lastTimestamp'
```

### Step 2: Determine if Intentional

Ask:
- Is this change documented?
- Was there a change ticket/PR?
- Is it managed by an operator (HPA, cert-manager)?
- Is it a temporary debugging change?

### Step 3: Choose Remediation Strategy

#### Option A: Update IaC (Change is Intentional)

```bash
# 1. Update manifest file
vim deploy/kubernetes/deployment.yaml

# 2. Commit changes
git add deploy/kubernetes/deployment.yaml
git commit -m "Update deployment config to match production"

# 3. Create PR
git push origin update-iac
gh pr create --title "Update IaC to match production state"
```

#### Option B: Restore IaC State (Change is Unauthorized)

```bash
# 1. Review the change
kubectl diff -f deploy/kubernetes/deployment.yaml -n glaucoma

# 2. Apply manifest to restore
kubectl apply -f deploy/kubernetes/deployment.yaml -n glaucoma

# 3. Verify
./deploy/check-drift.sh
```

#### Option C: Document Exception

If change is expected but shouldn't be in IaC:

```bash
# Edit drift-exceptions.yaml
vim deploy/drift-exceptions.yaml

# Add exception
allowedModifications:
  - resource: Deployment
    name: glaucoma-api
    field: spec.replicas
    reason: "Managed by HPA"
```

### Step 4: Document and Communicate

```bash
# Create incident report
cat > drift-incident-$(date +%Y%m%d).md <<EOF
# Drift Incident Report

**Date**: $(date)
**Resource**: Deployment/glaucoma-api
**Change**: Replicas scaled from 2 to 5
**Cause**: Load spike triggered HPA
**Action**: Added to drift exceptions
**Reviewer**: @username
EOF

# Notify team
# Post in Slack, update ticket, etc.
```

## Preventing Drift

### 1. Enforce GitOps

Use tools like ArgoCD or Flux to automatically sync cluster state with IaC:

```yaml
# ArgoCD Application
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: glaucoma-api
spec:
  syncPolicy:
    automated:
      prune: true  # Delete resources not in Git
      selfHeal: true  # Revert manual changes
```

### 2. RBAC Restrictions

Limit who can make manual changes:

```yaml
# Restrict direct modifications
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: developers-readonly
subjects:
  - kind: Group
    name: developers
roleRef:
  kind: ClusterRole
  name: view  # Read-only access
```

### 3. Admission Controllers

Validate changes before they're applied:

```yaml
# OPA Gatekeeper policy
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sRequireLabels
metadata:
  name: require-change-ticket
spec:
  match:
    kinds:
      - apiGroups: ["apps"]
        kinds: ["Deployment"]
  parameters:
    labels:
      - key: "change-ticket"
```

### 4. Change Management Process

Require all changes to go through:
1. **PR Review**: Code review for IaC changes
2. **Approval**: Manager/lead approval
3. **CI/CD**: Automated validation and deployment
4. **Audit**: Log all changes

### 5. Regular Audits

Schedule regular drift checks:

```bash
# Crontab entry
0 */6 * * * /path/to/check-drift.sh && send-report.sh

# Or use the GitHub Actions workflow (recommended)
```

## Drift Exceptions Configuration

File: [drift-exceptions.yaml](drift-exceptions.yaml)

### Structure

```yaml
# Ignored resources (won't be flagged)
ignoredResources:
  - kind: ConfigMap
    name: kube-root-ca.crt
    reason: "Auto-generated by Kubernetes"

# Ignored fields (expected to differ)
ignoredFields:
  - resource: Deployment
    fields:
      - metadata.generation
      - status

# Allowed modifications (specific permitted changes)
allowedModifications:
  - resource: Deployment
    name: glaucoma-api
    field: spec.replicas
    managedBy: "HPA"
```

## Alerting and Notifications

### Slack Integration

Configure in drift-exceptions.yaml:

```yaml
alerting:
  notifications:
    slack:
      enabled: true
      channel: "#infrastructure-alerts"
      severity: ["critical", "warning"]
```

Set Slack webhook in GitHub secrets:
```bash
gh secret set SLACK_WEBHOOK --body "https://hooks.slack.com/services/..."
```

### GitHub Issues

Automatically created for critical drift:
- Label: `infrastructure`, `drift`, `needs-review`
- Assignee: Platform team
- Template includes remediation steps

### Email Notifications

```yaml
alerting:
  notifications:
    email:
      enabled: true
      recipients: ["devops@example.com"]
      severity: ["critical"]
```

## Troubleshooting

### Drift Detection Not Running

Check workflow status:
```bash
gh workflow view drift-detection.yml
gh run list --workflow=drift-detection.yml
```

View logs:
```bash
gh run view <run-id> --log
```

### False Positives

Add to drift-exceptions.yaml:
```yaml
ignoredFields:
  - resource: Service
    fields:
      - spec.clusterIP
    reason: "Assigned by cluster"
```

### kubectl diff Errors

```bash
# Check API server connectivity
kubectl cluster-info

# Verify manifest syntax
kubectl apply --dry-run=client -f deploy/kubernetes/deployment.yaml

# Check RBAC permissions
kubectl auth can-i get deployments -n glaucoma
```

### Large Drift Reports

Filter by severity:
```bash
./deploy/check-drift.sh | grep "❌"  # Critical only
./deploy/check-drift.sh | grep "⚠️"   # Warnings
```

## Best Practices

1. **Regular Checks**: Run drift detection at least daily
2. **Quick Response**: Address critical drift within 24 hours
3. **Document Everything**: Update drift-exceptions.yaml
4. **Root Cause Analysis**: Investigate why drift occurred
5. **Automate Remediation**: Use GitOps tools when possible
6. **Communicate Changes**: Keep team informed
7. **Test in Staging**: Validate IaC changes before production
8. **Maintain Audit Trail**: Log all drift incidents

## Compliance and Auditing

### SOC 2 / ISO 27001

Drift detection supports compliance by:
- Providing audit trail of all changes
- Detecting unauthorized modifications
- Enforcing change management policies
- Maintaining documentation

### Audit Report Generation

```bash
# Generate compliance report
./deploy/check-drift.sh > compliance-report-$(date +%Y%m).md

# Include in quarterly audits
cat drift-reports/*.md > quarterly-drift-audit.md
```

## Resources

- [Kubernetes Drift Detection Best Practices](https://kubernetes.io/docs/concepts/cluster-administration/)
- [GitOps Principles](https://opengitops.dev/)
- [kubectl diff Documentation](https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#diff)
- [Infrastructure as Code Security](https://www.hashicorp.com/resources/what-is-infrastructure-as-code)

## Support

For issues or questions:
- Create GitHub issue with label `infrastructure`
- Contact platform team in #infrastructure Slack channel
- Review [ARCHITECTURE.md](../ARCHITECTURE.md) for system design
