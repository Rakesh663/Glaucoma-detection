# Code Quality Guide

This document describes the code quality tools and practices used in the Glaucoma Detection API project.

## Overview

We use multiple complementary tools to ensure high code quality, security, and maintainability:

1. **CodeQL** - GitHub's semantic code analysis engine
2. **SonarQube/SonarCloud** - Continuous code quality and security analysis
3. **Pylint** - Python code static analysis
4. **Radon** - Code complexity metrics
5. **Semgrep** - Fast, lightweight static analysis
6. **Dependency scanning** - Automated dependency vulnerability detection

## Tools

### 1. CodeQL

CodeQL is GitHub's semantic code analysis engine that finds security vulnerabilities and code quality issues.

#### Features
- **Security vulnerabilities**: SQL injection, XSS, command injection, etc.
- **Code quality**: Bug patterns, anti-patterns, best practices
- **Custom queries**: Write your own security and quality checks
- **Pull request integration**: Automatic scanning on every PR

#### Configuration

File: [.github/codeql/codeql-config.yml](.github/codeql/codeql-config.yml)

```yaml
queries:
  - uses: security-extended
  - uses: security-and-quality
```

#### Running Locally

```bash
# Install CodeQL CLI
brew install codeql  # macOS
# or download from https://github.com/github/codeql-cli-binaries

# Create database
codeql database create glaucoma-db --language=python

# Run queries
codeql database analyze glaucoma-db \
  --format=sarif-latest \
  --output=results.sarif \
  codeql/python-queries:codeql-suites/python-security-and-quality.qls

# View results
codeql bqrs decode results.sarif --format=text
```

#### GitHub Integration

Automatic scanning is configured in [.github/workflows/codeql-analysis.yml](.github/workflows/codeql-analysis.yml)

- **Triggers**: Push to main/master, PRs, weekly schedule
- **Results**: Available in GitHub Security tab

### 2. SonarQube/SonarCloud

SonarQube provides comprehensive code quality and security analysis with detailed metrics.

#### Metrics Tracked

- **Bugs**: Likely code errors
- **Vulnerabilities**: Security issues
- **Code smells**: Maintainability issues
- **Coverage**: Test coverage percentage
- **Duplications**: Duplicate code blocks
- **Complexity**: Cyclomatic complexity

#### Configuration

File: [sonar-project.properties](sonar-project.properties)

Key settings:
```properties
sonar.projectKey=glaucoma-detection-api
sonar.sources=api
sonar.tests=tests
sonar.python.coverage.reportPaths=coverage.xml
sonar.python.version=3.11
```

#### Running Locally with Docker

```bash
# Start SonarQube server
docker run -d --name sonarqube \
  -p 9000:9000 \
  sonarqube:latest

# Wait for startup (check http://localhost:9000)
# Default credentials: admin/admin

# Run analysis
docker run --rm \
  --network=host \
  -v "$(pwd):/usr/src" \
  sonarsource/sonar-scanner-cli \
  -Dsonar.host.url=http://localhost:9000 \
  -Dsonar.login=YOUR_TOKEN
```

#### SonarCloud (Cloud-based)

1. Sign up at https://sonarcloud.io
2. Import your GitHub repository
3. Add secrets to GitHub:
   - `SONAR_TOKEN`: Your SonarCloud token
   - `SONAR_ORGANIZATION`: Your organization key

Workflow: [.github/workflows/sonarqube.yml](.github/workflows/sonarqube.yml)

#### Quality Gates

Default quality gate requirements:
- **Coverage**: ≥ 70%
- **Duplications**: ≤ 3%
- **Maintainability Rating**: A (≤ 5% debt ratio)
- **Reliability Rating**: A (0 bugs)
- **Security Rating**: A (0 vulnerabilities)

### 3. Pylint

Pylint is a comprehensive Python code analyzer.

#### Configuration

File: [.pylintrc](.pylintrc)

Key settings:
- Max line length: 120
- Max complexity: 15
- Naming conventions: snake_case for functions/variables, PascalCase for classes

#### Running Pylint

```bash
# Check entire codebase
pylint api

# Check specific file
pylint api/main.py

# Generate report
pylint api --output-format=text > pylint-report.txt

# JSON output for tools
pylint api --output-format=json > pylint-report.json

# With custom config
pylint --rcfile=.pylintrc api
```

#### Pylint Ratings

- **10.00**: Perfect score
- **9.00+**: Excellent
- **8.00+**: Good
- **7.00+**: Acceptable
- **< 7.00**: Needs improvement

### 4. Radon

Radon analyzes code complexity and maintainability.

#### Metrics

1. **Cyclomatic Complexity (CC)**
   - A: 1-5 (Simple)
   - B: 6-10 (Well structured)
   - C: 11-20 (Complex)
   - D: 21-30 (Very complex)
   - E: 31-40 (Extremely complex)
   - F: 41+ (Unmaintainable)

2. **Maintainability Index (MI)**
   - 100-20: Very maintainable
   - 20-10: Moderately maintainable
   - < 10: Difficult to maintain

#### Running Radon

```bash
# Install
pip install radon

# Cyclomatic complexity
radon cc api -a  # Show average

# Maintainability index
radon mi api -s  # Show all

# Raw metrics (LOC, SLOC, comments)
radon raw api -s

# Halstead metrics
radon hal api
```

#### Integration

```bash
# Check thresholds
pip install xenon

# Fail if complexity too high
xenon --max-average A --max-modules B --max-absolute C api/
```

### 5. Semgrep

Semgrep is a fast, lightweight static analysis tool.

#### Features
- **Fast**: Analyzes code in seconds
- **Customizable**: Write your own rules
- **Security-focused**: OWASP Top 10, CWE coverage
- **No false positives**: Pattern-based matching

#### Running Semgrep

```bash
# Install
pip install semgrep

# Run with default rules
semgrep --config=auto api/

# Run specific rulesets
semgrep --config=p/security-audit \
        --config=p/owasp-top-ten \
        --config=p/python \
        api/

# Generate SARIF output
semgrep --config=auto --sarif -o semgrep.sarif api/
```

#### GitHub Integration

Automatic scanning in [.github/workflows/codeql-analysis.yml](.github/workflows/codeql-analysis.yml)

### 6. Dependency Scanning

#### GitHub Dependency Review

Automatically scans for vulnerable dependencies in PRs.

#### Safety

```bash
# Install
pip install safety

# Check dependencies
safety check

# Check and output JSON
safety check --json

# Check requirements file
safety check -r requirements.txt
```

#### Trivy (Container scanning)

```bash
# Install
brew install trivy

# Scan Docker image
trivy image glaucoma-api:latest

# Scan filesystem
trivy fs .

# Output SARIF
trivy image --format sarif -o trivy-results.sarif glaucoma-api:latest
```

## Metrics & Thresholds

### Code Quality Thresholds

| Metric | Threshold | Tool |
|--------|-----------|------|
| Test Coverage | ≥ 70% | pytest-cov |
| Cyclomatic Complexity (avg) | ≤ 15 | radon |
| Maintainability Index | ≥ 20 | radon |
| Pylint Score | ≥ 8.0 | pylint |
| Code Duplication | ≤ 3% | SonarQube |
| Security Hotspots | 0 | SonarQube/CodeQL |
| Bugs | 0 | SonarQube |
| Vulnerabilities | 0 | SonarQube/Semgrep |

### Enforcement

Thresholds are enforced via:
1. **Pre-commit hooks** (local development)
2. **GitHub Actions** (CI/CD pipeline)
3. **Quality gates** (SonarQube)
4. **Branch protection** (required checks)

## Pre-commit Hooks

Install pre-commit hooks for automatic checking:

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black

  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8

  - repo: https://github.com/pycqa/pylint
    rev: v3.0.0
    hooks:
      - id: pylint

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.3.0
    hooks:
      - id: mypy

  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: ['-c', 'pyproject.toml']
```

## Best Practices

### 1. Write Clean Code

- **Keep functions small**: < 50 lines
- **Limit complexity**: Cyclomatic complexity < 10
- **Use meaningful names**: Descriptive variable/function names
- **Avoid deep nesting**: Max 3-4 levels
- **Single responsibility**: One function = one purpose

### 2. Write Tests

- **Aim for 80%+ coverage**
- **Test edge cases**
- **Use meaningful assertions**
- **Mock external dependencies**
- **Test both happy and error paths**

### 3. Security First

- **Never commit secrets**
- **Validate all inputs**
- **Use parameterized queries**
- **Sanitize outputs**
- **Keep dependencies updated**

### 4. Document Code

- **Docstrings for public APIs**
- **Comments for complex logic**
- **README for setup/usage**
- **Architecture docs for design**

### 5. Review Regularly

- **Check SonarQube dashboard weekly**
- **Review CodeQL alerts promptly**
- **Monitor dependency vulnerabilities**
- **Track metrics trends**

## CI/CD Integration

### GitHub Actions Workflows

1. **codeql-analysis.yml** - CodeQL scanning
2. **sonarqube.yml** - SonarQube analysis
3. **ci.yml** - Main CI pipeline with all checks

### Quality Gates in CI

```yaml
- name: Quality Gate
  run: |
    # Check coverage
    coverage report --fail-under=70

    # Check complexity
    xenon --max-average A api/

    # Check Pylint score
    pylint api --fail-under=8.0

    # Check for security issues
    bandit -r api -ll
```

## Viewing Results

### GitHub Security Tab

Navigate to **Security** → **Code scanning alerts**

View:
- CodeQL findings
- Semgrep results
- Dependency vulnerabilities

### SonarQube Dashboard

Access at: `https://sonarcloud.io/project/overview?id=glaucoma-detection-api`

View:
- Overview metrics
- Issues by severity
- Code coverage
- Code duplication
- Hotspots

### Local Reports

```bash
# Generate HTML coverage report
pytest --cov=api --cov-report=html
open htmlcov/index.html

# Generate Pylint report
pylint api --output-format=html > pylint-report.html
open pylint-report.html
```

## Troubleshooting

### CodeQL Analysis Failing

```bash
# Clear cache
rm -rf codeql-db

# Re-create database
codeql database create codeql-db --language=python

# Check logs
cat codeql-db/log/database-creation.log
```

### SonarQube Connection Issues

```bash
# Test connection
curl -u TOKEN: https://sonarcloud.io/api/system/status

# Verify token
echo $SONAR_TOKEN

# Check project key
grep sonar.projectKey sonar-project.properties
```

### Pylint Configuration Issues

```bash
# Generate default config
pylint --generate-rcfile > .pylintrc

# Test config
pylint --rcfile=.pylintrc --list-msgs

# Dry run
pylint --rcfile=.pylintrc --dry-run api/
```

## Resources

- [CodeQL Documentation](https://codeql.github.com/docs/)
- [SonarQube Documentation](https://docs.sonarqube.org/)
- [Pylint Documentation](https://pylint.pycqa.org/)
- [Radon Documentation](https://radon.readthedocs.io/)
- [Semgrep Documentation](https://semgrep.dev/docs/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Python Code Quality](https://realpython.com/python-code-quality/)
