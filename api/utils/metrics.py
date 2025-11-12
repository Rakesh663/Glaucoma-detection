"""
Prometheus metrics collection for API monitoring
"""
from prometheus_client import Counter, Histogram, Gauge, Info
from functools import wraps
import time
from typing import Callable


# ============================================================================
# API Request Metrics
# ============================================================================

# Request counter by endpoint and status
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

# Request duration histogram
http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=(0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0)
)

# Active requests gauge
http_requests_in_progress = Gauge(
    'http_requests_in_progress',
    'Number of HTTP requests in progress',
    ['method', 'endpoint']
)

# ============================================================================
# Prediction Metrics
# ============================================================================

# Prediction counter by result
predictions_total = Counter(
    'predictions_total',
    'Total predictions made',
    ['model_version', 'result']
)

# Prediction duration
prediction_duration_seconds = Histogram(
    'prediction_duration_seconds',
    'Prediction processing duration in seconds',
    ['model_version'],
    buckets=(0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0)
)

# Batch prediction size
batch_prediction_size = Histogram(
    'batch_prediction_size',
    'Number of images in batch predictions',
    buckets=(1, 2, 5, 10, 15, 20)
)

# Prediction confidence
prediction_confidence = Histogram(
    'prediction_confidence',
    'Prediction confidence scores',
    ['result'],
    buckets=(0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.99, 1.0)
)

# ============================================================================
# Cache Metrics
# ============================================================================

# Cache hits/misses
cache_operations_total = Counter(
    'cache_operations_total',
    'Total cache operations',
    ['operation', 'result']  # operation: get/set, result: hit/miss/error
)

# Cache hit rate (calculated metric)
cache_hit_rate = Gauge(
    'cache_hit_rate',
    'Cache hit rate percentage',
    ['cache_type']
)

# ============================================================================
# Rate Limiting Metrics
# ============================================================================

# Rate limit counter
rate_limit_total = Counter(
    'rate_limit_total',
    'Total rate limit checks',
    ['tier', 'endpoint', 'result']  # result: allowed/blocked
)

# Rate limit rejections
rate_limit_rejections_total = Counter(
    'rate_limit_rejections_total',
    'Total rate limit rejections',
    ['tier', 'endpoint']
)

# ============================================================================
# Model Metrics
# ============================================================================

# Model info
model_info = Info(
    'model_info',
    'Information about the loaded model'
)

# Model loaded status
model_loaded = Gauge(
    'model_loaded',
    'Whether the model is loaded (1) or not (0)'
)

# ============================================================================
# Database Metrics
# ============================================================================

# Database query duration
db_query_duration_seconds = Histogram(
    'db_query_duration_seconds',
    'Database query duration in seconds',
    ['query_type'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
)

# Database connection pool
db_connections = Gauge(
    'db_connections',
    'Database connection pool status',
    ['state']  # state: active/idle/total
)

# ============================================================================
# Error Metrics
# ============================================================================

# Application errors
errors_total = Counter(
    'errors_total',
    'Total application errors',
    ['error_type', 'endpoint']
)

# Validation errors
validation_errors_total = Counter(
    'validation_errors_total',
    'Total validation errors',
    ['field', 'error_type']
)

# ============================================================================
# Business Metrics
# ============================================================================

# User registrations
user_registrations_total = Counter(
    'user_registrations_total',
    'Total user registrations',
    ['tier']
)

# Active users
active_users = Gauge(
    'active_users',
    'Number of active users',
    ['tier']
)

# Predictions by risk level
predictions_by_risk_level = Counter(
    'predictions_by_risk_level',
    'Predictions grouped by risk level',
    ['risk_level']
)

# ============================================================================
# System Metrics
# ============================================================================

# Application uptime
application_uptime_seconds = Gauge(
    'application_uptime_seconds',
    'Application uptime in seconds'
)

# Application version
application_info = Info(
    'application_info',
    'Application version and build information'
)


# ============================================================================
# Metric Decorators
# ============================================================================

def track_prediction_time(model_version: str = "v1"):
    """Decorator to track prediction execution time"""
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                prediction_duration_seconds.labels(
                    model_version=model_version
                ).observe(duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                prediction_duration_seconds.labels(
                    model_version=model_version
                ).observe(duration)
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                prediction_duration_seconds.labels(
                    model_version=model_version
                ).observe(duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                prediction_duration_seconds.labels(
                    model_version=model_version
                ).observe(duration)
                raise

        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def track_cache_operation(operation: str):
    """Decorator to track cache operations"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)
                if result is not None:
                    cache_operations_total.labels(
                        operation=operation,
                        result="hit" if operation == "get" else "success"
                    ).inc()
                else:
                    cache_operations_total.labels(
                        operation=operation,
                        result="miss" if operation == "get" else "failure"
                    ).inc()
                return result
            except Exception as e:
                cache_operations_total.labels(
                    operation=operation,
                    result="error"
                ).inc()
                raise

        return wrapper
    return decorator


class MetricsCollector:
    """Centralized metrics collection service"""

    @staticmethod
    def record_prediction(
        model_version: str,
        result: str,
        confidence: float,
        risk_level: str,
        duration: float
    ):
        """Record a prediction event"""
        predictions_total.labels(
            model_version=model_version,
            result=result
        ).inc()

        prediction_confidence.labels(result=result).observe(confidence)
        predictions_by_risk_level.labels(risk_level=risk_level).inc()
        prediction_duration_seconds.labels(model_version=model_version).observe(duration)

    @staticmethod
    def record_batch_prediction(batch_size: int):
        """Record a batch prediction event"""
        batch_prediction_size.observe(batch_size)

    @staticmethod
    def record_cache_hit_rate(cache_type: str, hit_rate: float):
        """Record cache hit rate"""
        cache_hit_rate.labels(cache_type=cache_type).set(hit_rate)

    @staticmethod
    def record_rate_limit(tier: str, endpoint: str, allowed: bool):
        """Record rate limit check"""
        result = "allowed" if allowed else "blocked"
        rate_limit_total.labels(tier=tier, endpoint=endpoint, result=result).inc()

        if not allowed:
            rate_limit_rejections_total.labels(tier=tier, endpoint=endpoint).inc()

    @staticmethod
    def record_error(error_type: str, endpoint: str):
        """Record an error"""
        errors_total.labels(error_type=error_type, endpoint=endpoint).inc()

    @staticmethod
    def record_validation_error(field: str, error_type: str):
        """Record a validation error"""
        validation_errors_total.labels(field=field, error_type=error_type).inc()

    @staticmethod
    def set_model_loaded(loaded: bool, model_info_dict: dict = None):
        """Set model loaded status"""
        model_loaded.set(1 if loaded else 0)
        if loaded and model_info_dict:
            model_info.info(model_info_dict)

    @staticmethod
    def update_db_connections(active: int, idle: int, total: int):
        """Update database connection pool metrics"""
        db_connections.labels(state="active").set(active)
        db_connections.labels(state="idle").set(idle)
        db_connections.labels(state="total").set(total)

    @staticmethod
    def record_db_query(query_type: str, duration: float):
        """Record database query"""
        db_query_duration_seconds.labels(query_type=query_type).observe(duration)

    @staticmethod
    def set_application_info(version: str, build_date: str, commit_sha: str = None):
        """Set application information"""
        info = {
            "version": version,
            "build_date": build_date,
        }
        if commit_sha:
            info["commit_sha"] = commit_sha

        application_info.info(info)

    @staticmethod
    def update_uptime(seconds: float):
        """Update application uptime"""
        application_uptime_seconds.set(seconds)
