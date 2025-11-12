"""
Utility modules for API
"""
from api.utils.redis_client import redis_client
from api.utils.circuit_breaker import (
    database_circuit_breaker,
    external_api_circuit_breaker,
    redis_circuit_breaker
)
from api.utils.retry import (
    retry_database_operation,
    retry_http_request,
    retry_redis_operation,
    retry_with_context
)
from api.utils.cache import CacheService, ImageHasher, CacheWarmer
from api.utils.metrics import MetricsCollector
from api.utils.logging_config import logger, setup_logging, set_correlation_id

__all__ = [
    "redis_client",
    "database_circuit_breaker",
    "external_api_circuit_breaker",
    "redis_circuit_breaker",
    "retry_database_operation",
    "retry_http_request",
    "retry_redis_operation",
    "retry_with_context",
    "CacheService",
    "ImageHasher",
    "CacheWarmer",
    "MetricsCollector",
    "logger",
    "setup_logging",
    "set_correlation_id",
]
