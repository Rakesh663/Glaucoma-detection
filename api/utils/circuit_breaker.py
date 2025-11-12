"""
Circuit Breaker pattern implementation
Prevents cascading failures by failing fast
"""
import os
import time
import logging
from typing import Callable, Any, Optional
from enum import Enum
from circuitbreaker import circuit

logger = logging.getLogger(__name__)

# ============================================================================
# Circuit Breaker Configuration
# ============================================================================

FAILURE_THRESHOLD = int(os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5"))
TIMEOUT_SECONDS = int(os.getenv("CIRCUIT_BREAKER_TIMEOUT_SECONDS", "60"))
RECOVERY_TIMEOUT = int(os.getenv("CIRCUIT_BREAKER_RECOVERY_TIMEOUT", "30"))

# ============================================================================
# Circuit Breaker Decorators
# ============================================================================

def database_circuit_breaker(func: Callable) -> Callable:
    """
    Circuit breaker for database operations

    Usage:
        @database_circuit_breaker
        async def query_database():
            ...
    """
    @circuit(
        failure_threshold=FAILURE_THRESHOLD,
        recovery_timeout=RECOVERY_TIMEOUT,
        expected_exception=Exception
    )
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Database circuit breaker triggered: {e}")
            raise

    return wrapper

def external_api_circuit_breaker(func: Callable) -> Callable:
    """
    Circuit breaker for external API calls

    Usage:
        @external_api_circuit_breaker
        async def call_external_api():
            ...
    """
    @circuit(
        failure_threshold=FAILURE_THRESHOLD,
        recovery_timeout=RECOVERY_TIMEOUT,
        expected_exception=Exception
    )
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"External API circuit breaker triggered: {e}")
            raise

    return wrapper

def redis_circuit_breaker(func: Callable) -> Callable:
    """
    Circuit breaker for Redis operations

    Usage:
        @redis_circuit_breaker
        async def cache_operation():
            ...
    """
    @circuit(
        failure_threshold=FAILURE_THRESHOLD,
        recovery_timeout=RECOVERY_TIMEOUT,
        expected_exception=Exception
    )
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Redis circuit breaker triggered: {e}")
            # Return None for cache misses - non-critical failure
            return None

    return wrapper
