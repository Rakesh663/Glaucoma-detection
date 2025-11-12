# ============================================================================
# Multi-Stage Dockerfile for Glaucoma Detection API
# Production-grade with security best practices
# ============================================================================

# ============================================================================
# Stage 1: Builder - Install dependencies and compile wheels
# ============================================================================
FROM python:3.10-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install to wheels directory
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip wheel && \
    pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# ============================================================================
# Stage 2: Runtime - Minimal production image
# ============================================================================
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_HOME=/app \
    APP_USER=glaucoma \
    APP_UID=1000 \
    APP_GID=1000

WORKDIR ${APP_HOME}

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user and group
RUN groupadd -g ${APP_GID} ${APP_USER} && \
    useradd -u ${APP_UID} -g ${APP_GID} -m -s /bin/bash ${APP_USER} && \
    mkdir -p ${APP_HOME}/models ${APP_HOME}/logs ${APP_HOME}/data && \
    chown -R ${APP_USER}:${APP_USER} ${APP_HOME}

# Copy wheels from builder and install
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Copy application code
COPY --chown=${APP_USER}:${APP_USER} api/ ${APP_HOME}/api/
COPY --chown=${APP_USER}:${APP_USER} src/ ${APP_HOME}/src/
COPY --chown=${APP_USER}:${APP_USER} config/ ${APP_HOME}/config/
COPY --chown=${APP_USER}:${APP_USER} alembic/ ${APP_HOME}/alembic/
COPY --chown=${APP_USER}:${APP_USER} alembic.ini ${APP_HOME}/alembic.ini
COPY --chown=${APP_USER}:${APP_USER} models/best_model.pth ${APP_HOME}/models/
COPY --chown=${APP_USER}:${APP_USER} models/config.yaml ${APP_HOME}/models/

# Switch to non-root user
USER ${APP_USER}

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
