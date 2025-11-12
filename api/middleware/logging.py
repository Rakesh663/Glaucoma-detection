"""
Logging middleware for request/response tracking
"""
import time
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from typing import Callable

from api.utils.logging_config import (
    set_correlation_id,
    set_user_context,
    clear_context,
    logger
)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to automatically log all requests with correlation IDs
    """

    async def dispatch(self, request: Request, call_next: Callable):
        # Generate/extract correlation ID
        correlation_id = request.headers.get('X-Correlation-ID')
        if not correlation_id:
            correlation_id = set_correlation_id()
        else:
            set_correlation_id(correlation_id)

        # Extract user context if available
        user_id = None
        tenant_id = None

        if hasattr(request.state, 'user'):
            user_id = str(request.state.user.id)

        if hasattr(request.state, 'tenant_id'):
            tenant_id = str(request.state.tenant_id)

        # Or from headers
        if not user_id:
            user_id = request.headers.get('X-User-ID')
        if not tenant_id:
            tenant_id = request.headers.get('X-Tenant-ID')

        set_user_context(user_id=user_id, tenant_id=tenant_id)

        # Log incoming request
        start_time = time.time()

        logger.info(
            f"Request started: {request.method} {request.url.path}",
            method=request.method,
            path=request.url.path,
            query_params=dict(request.query_params),
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get('user-agent'),
            request_id=correlation_id
        )

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Add correlation ID to response headers
            response.headers['X-Correlation-ID'] = correlation_id

            # Log response
            logger.log_request(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                request_id=correlation_id
            )

            return response

        except Exception as e:
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Log error
            logger.log_error_with_context(
                error=e,
                context={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                    "request_id": correlation_id
                }
            )

            raise

        finally:
            # Clear context after request
            clear_context()
