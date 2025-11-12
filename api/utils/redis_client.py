"""
Redis client for caching and rate limiting
"""
import os
import json
from typing import Optional, Any
from datetime import timedelta
import redis.asyncio as redis


class RedisClient:
    """Async Redis client for caching and rate limiting"""

    def __init__(self):
        self.client: Optional[redis.Redis] = None
        self._initialized = False

    async def init(self):
        """Initialize Redis connection"""
        if self._initialized:
            return

        redis_url = os.getenv(
            "REDIS_URL",
            "redis://localhost:6379/0"
        )

        try:
            self.client = await redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=50,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            # Test connection
            await self.client.ping()
            self._initialized = True
            print(f"✓ Redis connected: {redis_url}")
        except Exception as e:
            print(f"⚠ Redis connection failed: {e}")
            print("  Rate limiting and caching will be disabled")
            self.client = None
            self._initialized = False

    async def close(self):
        """Close Redis connection"""
        if self.client:
            await self.client.close()
            self._initialized = False

    async def get(self, key: str) -> Optional[str]:
        """Get value from Redis"""
        if not self.client:
            return None
        try:
            return await self.client.get(key)
        except Exception as e:
            print(f"Redis GET error: {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        expire: Optional[int] = None
    ) -> bool:
        """Set value in Redis with optional expiration (seconds)"""
        if not self.client:
            return False
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)

            if expire:
                await self.client.setex(key, expire, value)
            else:
                await self.client.set(key, value)
            return True
        except Exception as e:
            print(f"Redis SET error: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from Redis"""
        if not self.client:
            return False
        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            print(f"Redis DELETE error: {e}")
            return False

    async def incr(self, key: str) -> Optional[int]:
        """Increment counter"""
        if not self.client:
            return None
        try:
            return await self.client.incr(key)
        except Exception as e:
            print(f"Redis INCR error: {e}")
            return None

    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration on key"""
        if not self.client:
            return False
        try:
            await self.client.expire(key, seconds)
            return True
        except Exception as e:
            print(f"Redis EXPIRE error: {e}")
            return False

    async def ttl(self, key: str) -> Optional[int]:
        """Get time to live for key"""
        if not self.client:
            return None
        try:
            return await self.client.ttl(key)
        except Exception as e:
            print(f"Redis TTL error: {e}")
            return None

    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        if not self.client:
            return False
        try:
            return await self.client.exists(key) > 0
        except Exception as e:
            print(f"Redis EXISTS error: {e}")
            return False

    async def get_json(self, key: str) -> Optional[dict]:
        """Get JSON value from Redis"""
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return None

    async def set_json(
        self,
        key: str,
        value: dict,
        expire: Optional[int] = None
    ) -> bool:
        """Set JSON value in Redis"""
        return await self.set(key, json.dumps(value), expire)

    def is_connected(self) -> bool:
        """Check if Redis is connected"""
        return self._initialized and self.client is not None


# Global Redis client instance
redis_client = RedisClient()
