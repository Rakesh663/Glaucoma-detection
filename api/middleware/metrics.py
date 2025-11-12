"""
Prometheus metrics collection middleware
"""
import time
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from typing import Callable

from api.utils.metrics import (
    http_requests_total,
    http_request_duration_seconds,
    http_requests_in_progress
)


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to automatically collect HTTP metrics for all requests
    """

    async def dispatch(self, request: Request, call_next: Callable):
        # Extract route information
        method = request.method
        path = request.url.path

        # Normalize path to avoid high cardinality
        # Replace dynamic segments with placeholders
        endpoint = self._normalize_path(path)

        # Track in-progress requests
        http_requests_in_progress.labels(
            method=method,
            endpoint=endpoint
        ).inc()

        # Track request duration
        start_time = time.time()

        try:
            # Process request
            response = await call_next(request)
            status_code = response.status_code

            # Record metrics
            duration = time.time() - start_time

            http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code
            ).inc()

            http_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)

            return response

        except Exception as e:
            # Record error metrics
            duration = time.time() - start_time

            http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status_code=500
            ).inc()

            http_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)

            raise

        finally:
            # Decrement in-progress counter
            http_requests_in_progress.labels(
                method=method,
                endpoint=endpoint
            ).dec()

    def _normalize_path(self, path: str) -> str:
        """
        Normalize path to reduce cardinality in metrics

        Replaces dynamic segments (UUIDs, IDs, etc.) with placeholders
        """
        # Skip normalization for common static paths
        static_paths = {
            "/", "/health", "/metrics", "/docs", "/openapi.json", "/redoc"
        }

        if path in static_paths:
            return path

        # Known API paths
        if path.startswith("/predict"):
            return "/predict"
        if path.startswith("/batch-predict"):
            return "/batch-predict"

        # Replace UUID-like segments
        import re
        path = re.sub(
            r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            '/{id}',
            path,
            flags=re.IGNORECASE
        )

        # Replace numeric IDs
        path = re.sub(r'/\d+', '/{id}', path)

        return path
