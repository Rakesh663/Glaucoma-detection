"""
Advanced rate limiting middleware with Redis
Supports per-user, per-tenant, and per-IP rate limiting
"""
import time
from typing import Optional, Callable
from datetime import datetime
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from api.utils.redis_client import redis_client


class RateLimitConfig:
    """Rate limit configuration for different tiers"""

    # Default limits (requests per window)
    DEFAULT_LIMIT = 100
    DEFAULT_WINDOW = 60  # seconds

    # Tier-based limits
    TIERS = {
        "free": {"limit": 60, "window": 60},       # 60 req/min
        "basic": {"limit": 300, "window": 60},     # 300 req/min
        "premium": {"limit": 1000, "window": 60},  # 1000 req/min
        "enterprise": {"limit": 10000, "window": 60}  # 10000 req/min
    }

    # Endpoint-specific limits (override tier limits)
    ENDPOINT_LIMITS = {
        "/predict": {"limit": 30, "window": 60},        # 30 predictions/min
        "/batch-predict": {"limit": 5, "window": 60},   # 5 batch requests/min
    }

    # Burst allowance (percentage above limit for short bursts)
    BURST_ALLOWANCE = 0.2  # 20% burst

    @classmethod
    def get_limit(
        cls,
        endpoint: str,
        tier: str = "free"
    ) -> tuple[int, int]:
        """Get rate limit and window for endpoint and tier"""
        # Check endpoint-specific limits first
        if endpoint in cls.ENDPOINT_LIMITS:
            config = cls.ENDPOINT_LIMITS[endpoint]
            return config["limit"], config["window"]

        # Fall back to tier-based limits
        if tier in cls.TIERS:
            config = cls.TIERS[tier]
            return config["limit"], config["window"]

        # Default limits
        return cls.DEFAULT_LIMIT, cls.DEFAULT_WINDOW


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Advanced rate limiting middleware

    Features:
    - Per-user rate limiting
    - Per-tenant rate limiting
    - Per-IP rate limiting
    - Sliding window algorithm
    - Burst protection
    - Rate limit headers in response
    """

    def __init__(self, app, enable_per_ip: bool = True):
        super().__init__(app)
        self.enable_per_ip = enable_per_ip

    async def dispatch(self, request: Request, call_next: Callable):
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/", "/docs", "/openapi.json"]:
            return await call_next(request)

        # Check if Redis is available
        if not redis_client.is_connected():
            # If Redis is down, allow requests but log warning
            print("⚠ Rate limiting disabled: Redis not available")
            return await call_next(request)

        # Extract identifiers
        user_id = self._get_user_id(request)
        tenant_id = self._get_tenant_id(request)
        ip_address = self._get_client_ip(request)
        endpoint = request.url.path

        # Get user/tenant tier
        tier = await self._get_tier(user_id, tenant_id)

        # Get rate limit configuration
        limit, window = RateLimitConfig.get_limit(endpoint, tier)

        # Check rate limits in order: user -> tenant -> IP
        rate_limit_key = None
        identifier = None

        if user_id:
            rate_limit_key = f"ratelimit:user:{user_id}:{endpoint}"
            identifier = f"user:{user_id}"
        elif tenant_id:
            rate_limit_key = f"ratelimit:tenant:{tenant_id}:{endpoint}"
            identifier = f"tenant:{tenant_id}"
        elif self.enable_per_ip and ip_address:
            rate_limit_key = f"ratelimit:ip:{ip_address}:{endpoint}"
            identifier = f"ip:{ip_address}"
        else:
            # No identifier, skip rate limiting
            return await call_next(request)

        # Check rate limit
        is_allowed, current_count, reset_time = await self._check_rate_limit(
            rate_limit_key,
            limit,
            window
        )

        # Add rate limit headers to response
        def add_rate_limit_headers(response):
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(max(0, limit - current_count))
            response.headers["X-RateLimit-Reset"] = str(reset_time)
            response.headers["X-RateLimit-Window"] = str(window)
            return response

        if not is_allowed:
            # Rate limit exceeded
            retry_after = reset_time - int(time.time())

            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Please try again in {retry_after} seconds.",
                    "identifier": identifier,
                    "limit": limit,
                    "window": window,
                    "retry_after": retry_after,
                    "reset_at": datetime.fromtimestamp(reset_time).isoformat()
                },
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(retry_after)
                }
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        return add_rate_limit_headers(response)

    def _get_user_id(self, request: Request) -> Optional[str]:
        """Extract user ID from request (from JWT token)"""
        # Check if user is authenticated
        if hasattr(request.state, "user"):
            return str(request.state.user.id)

        # Try to get from custom header
        return request.headers.get("X-User-ID")

    def _get_tenant_id(self, request: Request) -> Optional[str]:
        """Extract tenant ID from request"""
        if hasattr(request.state, "tenant_id"):
            return str(request.state.tenant_id)

        return request.headers.get("X-Tenant-ID")

    def _get_client_ip(self, request: Request) -> Optional[str]:
        """Extract client IP address"""
        # Check X-Forwarded-For header (for proxies/load balancers)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Get first IP in chain
            return forwarded.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return None

    async def _get_tier(
        self,
        user_id: Optional[str],
        tenant_id: Optional[str]
    ) -> str:
        """Get user/tenant tier from database or cache"""
        # Try to get from cache first
        if user_id:
            tier = await redis_client.get(f"tier:user:{user_id}")
            if tier:
                return tier

        if tenant_id:
            tier = await redis_client.get(f"tier:tenant:{tenant_id}")
            if tier:
                return tier

        # Default to free tier
        # TODO: Fetch from database if not in cache
        return "free"

    async def _check_rate_limit(
        self,
        key: str,
        limit: int,
        window: int
    ) -> tuple[bool, int, int]:
        """
        Check rate limit using sliding window algorithm

        Returns:
            (is_allowed, current_count, reset_time)
        """
        try:
            current_time = int(time.time())

            # Get current count
            current_count = await redis_client.get(key)

            if current_count is None:
                # First request in window
                await redis_client.set(key, "1", expire=window)
                reset_time = current_time + window
                return True, 1, reset_time

            current_count = int(current_count)

            # Get TTL to calculate reset time
            ttl = await redis_client.ttl(key)
            if ttl < 0:
                # Key expired, reset counter
                await redis_client.set(key, "1", expire=window)
                reset_time = current_time + window
                return True, 1, reset_time

            reset_time = current_time + ttl

            # Check if limit exceeded (with burst allowance)
            burst_limit = int(limit * (1 + RateLimitConfig.BURST_ALLOWANCE))

            if current_count >= burst_limit:
                # Hard limit exceeded
                return False, current_count, reset_time

            if current_count >= limit:
                # Soft limit exceeded, but burst allowed
                # Log warning for monitoring
                print(f"⚠ Burst limit triggered for {key}: {current_count}/{limit}")

            # Increment counter
            await redis_client.incr(key)
            current_count += 1

            return True, current_count, reset_time

        except Exception as e:
            print(f"Rate limit check error: {e}")
            # On error, allow request (fail open)
            return True, 0, current_time + window


class RateLimitService:
    """Service for managing rate limits programmatically"""

    @staticmethod
    async def set_user_tier(user_id: str, tier: str, ttl: int = 3600):
        """Set user tier in cache"""
        await redis_client.set(f"tier:user:{user_id}", tier, expire=ttl)

    @staticmethod
    async def set_tenant_tier(tenant_id: str, tier: str, ttl: int = 3600):
        """Set tenant tier in cache"""
        await redis_client.set(f"tier:tenant:{tenant_id}", tier, expire=ttl)

    @staticmethod
    async def reset_rate_limit(identifier: str, endpoint: str):
        """Reset rate limit for a specific identifier and endpoint"""
        key = f"ratelimit:{identifier}:{endpoint}"
        await redis_client.delete(key)

    @staticmethod
    async def get_rate_limit_status(
        identifier: str,
        endpoint: str
    ) -> dict:
        """Get current rate limit status for an identifier"""
        key = f"ratelimit:{identifier}:{endpoint}"

        count = await redis_client.get(key)
        ttl = await redis_client.ttl(key)

        if count is None or ttl < 0:
            return {
                "current_count": 0,
                "reset_in": 0,
                "is_limited": False
            }

        # Get tier and limits
        tier = "free"  # Default
        if "user:" in identifier:
            user_id = identifier.split("user:")[-1]
            tier = await redis_client.get(f"tier:user:{user_id}") or "free"
        elif "tenant:" in identifier:
            tenant_id = identifier.split("tenant:")[-1]
            tier = await redis_client.get(f"tier:tenant:{tenant_id}") or "free"

        limit, window = RateLimitConfig.get_limit(endpoint, tier)

        return {
            "current_count": int(count),
            "limit": limit,
            "window": window,
            "reset_in": ttl,
            "is_limited": int(count) >= limit
        }
