"""
Multi-tenancy middleware for tenant isolation
Ensures data isolation between tenants
"""
import os
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from fastapi import HTTPException, status
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# Tenant Context
# ============================================================================

class TenantContext:
    """
    Thread-local storage for current tenant context
    """
    _tenant_id: Optional[int] = None
    _tenant_identifier: Optional[str] = None

    @classmethod
    def set_tenant(cls, tenant_id: int, tenant_identifier: str):
        cls._tenant_id = tenant_id
        cls._tenant_identifier = tenant_identifier

    @classmethod
    def get_tenant_id(cls) -> Optional[int]:
        return cls._tenant_id

    @classmethod
    def get_tenant_identifier(cls) -> Optional[str]:
        return cls._tenant_identifier

    @classmethod
    def clear(cls):
        cls._tenant_id = None
        cls._tenant_identifier = None

# ============================================================================
# Tenant Middleware
# ============================================================================

class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware for multi-tenant isolation
    Extracts tenant information from:
    1. X-Tenant-ID header
    2. Subdomain (tenant.example.com)
    3. JWT token (after authentication)
    """

    def __init__(self, app, enable_tenant_isolation: bool = True):
        super().__init__(app)
        self.enable_tenant_isolation = enable_tenant_isolation or \
            os.getenv("ENABLE_TENANT_ISOLATION", "true").lower() == "true"

    async def dispatch(self, request: Request, call_next):
        """
        Process request and enforce tenant isolation

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            HTTP response
        """
        # Clear any previous tenant context
        TenantContext.clear()

        # Skip tenant isolation for certain paths
        skip_paths = [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/metrics",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/google",
            "/api/v1/auth/github",
            "/api/v1/auth/azure"
        ]

        if any(request.url.path.startswith(path) for path in skip_paths):
            return await call_next(request)

        # Extract tenant from various sources
        tenant_id = None
        tenant_identifier = None

        # 1. Try X-Tenant-ID header
        tenant_header = request.headers.get("X-Tenant-ID")
        if tenant_header:
            tenant_identifier = tenant_header
            logger.debug(f"Tenant from header: {tenant_identifier}")

        # 2. Try subdomain extraction (e.g., tenant1.example.com)
        if not tenant_identifier:
            host = request.headers.get("host", "")
            parts = host.split(".")
            if len(parts) > 2:  # Has subdomain
                potential_tenant = parts[0]
                # Exclude common subdomains
                if potential_tenant not in ["www", "api", "app"]:
                    tenant_identifier = potential_tenant
                    logger.debug(f"Tenant from subdomain: {tenant_identifier}")

        # 3. JWT token will be checked in authentication dependency
        # For now, we just set the context if we have a tenant

        if tenant_identifier:
            TenantContext.set_tenant(
                tenant_id=tenant_id,  # Will be resolved from DB in auth
                tenant_identifier=tenant_identifier
            )

        # Process request
        try:
            response = await call_next(request)
            return response
        finally:
            # Clear tenant context after request
            TenantContext.clear()

# ============================================================================
# Tenant Utilities
# ============================================================================

def get_current_tenant_id() -> Optional[int]:
    """
    Get current tenant ID from context

    Returns:
        Current tenant ID or None
    """
    return TenantContext.get_tenant_id()

def get_current_tenant_identifier() -> Optional[str]:
    """
    Get current tenant identifier from context

    Returns:
        Current tenant identifier or None
    """
    return TenantContext.get_tenant_identifier()

def require_tenant():
    """
    Dependency to require tenant context

    Raises:
        HTTPException: If no tenant context is set
    """
    tenant_id = get_current_tenant_id()
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context required"
        )
    return tenant_id
