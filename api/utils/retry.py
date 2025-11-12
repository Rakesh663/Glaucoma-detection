"""
Context-aware retry logic with exponential backoff and jitter
Handles transient failures gracefully
"""
import os
import random
import logging
from typing import Callable, Type, Tuple
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)
from sqlalchemy.exc import OperationalError, TimeoutError as SQLTimeoutError
import httpx

logger = logging.getLogger(__name__)

# ============================================================================
# Retry Configuration
# ============================================================================

MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
BACKOFF_FACTOR = int(os.getenv("RETRY_BACKOFF_FACTOR", "2"))
MAX_DELAY_SECONDS = int(os.getenv("RETRY_MAX_DELAY_SECONDS", "60"))

# ============================================================================
# Retry Decorators
# ============================================================================

def retry_database_operation(func: Callable) -> Callable:
    """
    Retry decorator for database operations
    Handles transient database connection failures

    Usage:
        @retry_database_operation
        async def query_database():
            ...
    """
    return retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(
            multiplier=BACKOFF_FACTOR,
            min=1,
            max=MAX_DELAY_SECONDS
        ),
        retry=retry_if_exception_type((
            OperationalError,
            SQLTimeoutError,
            ConnectionError
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.INFO)
    )(func)

def retry_http_request(func: Callable) -> Callable:
    """
    Retry decorator for HTTP requests
    Handles transient network failures and 5xx errors

    Usage:
        @retry_http_request
        async def call_api():
            ...
    """
    return retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(
            multiplier=BACKOFF_FACTOR,
            min=1,
            max=MAX_DELAY_SECONDS
        ),
        retry=retry_if_exception_type((
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.RemoteProtocolError,
            httpx.HTTPStatusError
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.INFO)
    )(func)

def retry_redis_operation(func: Callable) -> Callable:
    """
    Retry decorator for Redis operations
    Handles transient Redis connection failures

    Usage:
        @retry_redis_operation
        async def cache_get():
            ...
    """
    return retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(
            multiplier=BACKOFF_FACTOR,
            min=0.5,
            max=10  # Shorter max for cache operations
        ),
        retry=retry_if_exception_type((
            ConnectionError,
            TimeoutError
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.INFO)
    )(func)

# ============================================================================
# Custom Retry Logic with Jitter
# ============================================================================

def exponential_backoff_with_jitter(attempt: int) -> float:
    """
    Calculate backoff time with exponential growth and jitter

    Args:
        attempt: Current attempt number (starting from 1)

    Returns:
        Sleep time in seconds
    """
    # Exponential backoff: base * 2^attempt
    base_delay = min(BACKOFF_FACTOR ** attempt, MAX_DELAY_SECONDS)

    # Add jitter (±25% random variation)
    jitter = base_delay * 0.25 * (2 * random.random() - 1)

    return base_delay + jitter

# ============================================================================
# Context-Aware Retry Helper
# ============================================================================

async def retry_with_context(
    func: Callable,
    *args,
    max_attempts: int = MAX_RETRIES,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    context: str = "operation",
    **kwargs
) -> any:
    """
    Execute function with context-aware retry logic

    Args:
        func: Function to execute
        *args: Positional arguments for func
        max_attempts: Maximum number of retry attempts
        retryable_exceptions: Tuple of exception types to retry
        context: Context description for logging
        **kwargs: Keyword arguments for func

    Returns:
        Function result

    Raises:
        Last exception if all retries fail
    """
    last_exception = None

    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(f"Attempting {context} (attempt {attempt}/{max_attempts})")
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            logger.info(f"{context} succeeded on attempt {attempt}")
            return result

        except retryable_exceptions as e:
            last_exception = e
            logger.warning(f"{context} failed on attempt {attempt}: {e}")

            if attempt < max_attempts:
                sleep_time = exponential_backoff_with_jitter(attempt)
                logger.info(f"Retrying {context} after {sleep_time:.2f} seconds...")
                await asyncio.sleep(sleep_time) if asyncio.iscoroutinefunction(func) else time.sleep(sleep_time)
            else:
                logger.error(f"{context} failed after {max_attempts} attempts")

    raise last_exception


# Import asyncio and time
import asyncio
import time
