# ============================================================================
# Optimized Dockerfile for Glaucoma Detection API
# Uses pre-built wheels from PyPI for faster builds
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

# Install Python dependencies directly (uses pre-built wheels from PyPI)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=${APP_USER}:${APP_USER} api/ ${APP_HOME}/api/
COPY --chown=${APP_USER}:${APP_USER} src/ ${APP_HOME}/src/
COPY --chown=${APP_USER}:${APP_USER} config/ ${APP_HOME}/config/
COPY --chown=${APP_USER}:${APP_USER} alembic/ ${APP_HOME}/alembic/
COPY --chown=${APP_USER}:${APP_USER} alembic.ini ${APP_HOME}/alembic.ini

# Copy model files if they exist (optional)
COPY --chown=${APP_USER}:${APP_USER} models/ ${APP_HOME}/models/

# Switch to non-root user
USER ${APP_USER}

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
