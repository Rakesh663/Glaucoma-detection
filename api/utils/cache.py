"""
Redis-based caching service for predictions and metadata
"""
import hashlib
import json
from typing import Optional, Any, Callable
from functools import wraps
import asyncio

from api.utils.redis_client import redis_client


class CacheService:
    """
    Advanced caching service with support for:
    - Prediction result caching
    - Model metadata caching
    - Cache invalidation strategies
    - Cache warming
    - TTL management
    """

    # Default TTL values (in seconds)
    PREDICTION_TTL = 3600  # 1 hour
    METADATA_TTL = 86400  # 24 hours
    USER_DATA_TTL = 1800  # 30 minutes
    STATS_TTL = 300  # 5 minutes

    @staticmethod
    def _generate_cache_key(prefix: str, *args, **kwargs) -> str:
        """
        Generate a deterministic cache key from function arguments

        Args:
            prefix: Key prefix (e.g., 'prediction', 'metadata')
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Cache key string
        """
        # Create a deterministic string from arguments
        key_parts = [prefix]

        # Add positional args
        for arg in args:
            if isinstance(arg, (str, int, float, bool)):
                key_parts.append(str(arg))
            elif isinstance(arg, bytes):
                # Hash bytes (e.g., image data)
                key_parts.append(hashlib.md5(arg).hexdigest())
            elif isinstance(arg, dict):
                # Sort dict and serialize
                key_parts.append(json.dumps(arg, sort_keys=True))

        # Add keyword args
        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            for k, v in sorted_kwargs:
                key_parts.append(f"{k}={v}")

        # Join and create hash if too long
        key = ":".join(key_parts)
        if len(key) > 200:
            # Use hash for very long keys
            key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
            return f"{prefix}:hash:{key_hash}"

        return key

    @staticmethod
    async def get_cached_prediction(
        image_hash: str,
        model_version: str = "v1"
    ) -> Optional[dict]:
        """
        Get cached prediction result

        Args:
            image_hash: Hash of the input image
            model_version: Model version identifier

        Returns:
            Cached prediction dict or None
        """
        key = f"prediction:{model_version}:{image_hash}"
        result = await redis_client.get_json(key)
        return result

    @staticmethod
    async def set_cached_prediction(
        image_hash: str,
        prediction: dict,
        model_version: str = "v1",
        ttl: Optional[int] = None
    ) -> bool:
        """
        Cache a prediction result

        Args:
            image_hash: Hash of the input image
            prediction: Prediction result dictionary
            model_version: Model version identifier
            ttl: Time to live in seconds (default: PREDICTION_TTL)

        Returns:
            True if successful
        """
        key = f"prediction:{model_version}:{image_hash}"
        ttl = ttl or CacheService.PREDICTION_TTL
        return await redis_client.set_json(key, prediction, expire=ttl)

    @staticmethod
    async def get_model_metadata() -> Optional[dict]:
        """Get cached model metadata"""
        key = "metadata:model:current"
        return await redis_client.get_json(key)

    @staticmethod
    async def set_model_metadata(
        metadata: dict,
        ttl: Optional[int] = None
    ) -> bool:
        """Cache model metadata"""
        key = "metadata:model:current"
        ttl = ttl or CacheService.METADATA_TTL
        return await redis_client.set_json(key, metadata, expire=ttl)

    @staticmethod
    async def get_user_stats(user_id: str) -> Optional[dict]:
        """Get cached user statistics"""
        key = f"stats:user:{user_id}"
        return await redis_client.get_json(key)

    @staticmethod
    async def set_user_stats(
        user_id: str,
        stats: dict,
        ttl: Optional[int] = None
    ) -> bool:
        """Cache user statistics"""
        key = f"stats:user:{user_id}"
        ttl = ttl or CacheService.STATS_TTL
        return await redis_client.set_json(key, stats, expire=ttl)

    @staticmethod
    async def invalidate_user_cache(user_id: str):
        """Invalidate all cache entries for a user"""
        patterns = [
            f"stats:user:{user_id}",
            f"prediction:*:user:{user_id}",
        ]
        for pattern in patterns:
            await redis_client.delete(pattern)

    @staticmethod
    async def invalidate_prediction_cache(
        image_hash: Optional[str] = None,
        model_version: Optional[str] = None
    ):
        """
        Invalidate prediction cache

        Args:
            image_hash: Specific image hash to invalidate (None = all)
            model_version: Specific model version (None = all versions)
        """
        if image_hash and model_version:
            key = f"prediction:{model_version}:{image_hash}"
            await redis_client.delete(key)
        elif model_version:
            # Would need SCAN to delete all predictions for a version
            # For now, just document that full invalidation requires admin access
            pass
        # Full cache clear would be done via redis FLUSHDB (admin only)


def cached(
    prefix: str,
    ttl: Optional[int] = None,
    skip_cache_on_error: bool = True
):
    """
    Decorator for caching function results in Redis

    Args:
        prefix: Cache key prefix
        ttl: Time to live in seconds
        skip_cache_on_error: If True, call function on cache error

    Example:
        @cached(prefix="expensive_computation", ttl=3600)
        async def expensive_function(arg1, arg2):
            # ... expensive computation
            return result
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = CacheService._generate_cache_key(
                prefix,
                *args,
                **kwargs
            )

            # Try to get from cache
            try:
                cached_result = await redis_client.get_json(cache_key)
                if cached_result is not None:
                    return cached_result
            except Exception as e:
                if not skip_cache_on_error:
                    raise
                print(f"Cache GET error for {cache_key}: {e}")

            # Cache miss - call function
            result = await func(*args, **kwargs)

            # Store in cache
            try:
                await redis_client.set_json(cache_key, result, expire=ttl)
            except Exception as e:
                if not skip_cache_on_error:
                    raise
                print(f"Cache SET error for {cache_key}: {e}")

            return result

        return wrapper
    return decorator


class ImageHasher:
    """Utility for generating deterministic image hashes"""

    @staticmethod
    def hash_image_bytes(image_bytes: bytes) -> str:
        """
        Generate MD5 hash of image bytes

        Args:
            image_bytes: Raw image bytes

        Returns:
            Hex digest string
        """
        return hashlib.md5(image_bytes).hexdigest()

    @staticmethod
    def hash_image_file(file_path: str) -> str:
        """
        Generate MD5 hash of image file

        Args:
            file_path: Path to image file

        Returns:
            Hex digest string
        """
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

    @staticmethod
    async def hash_upload_file(upload_file) -> tuple[str, bytes]:
        """
        Generate hash from FastAPI UploadFile

        Args:
            upload_file: FastAPI UploadFile object

        Returns:
            Tuple of (hash_string, file_bytes)
        """
        file_bytes = await upload_file.read()
        file_hash = hashlib.md5(file_bytes).hexdigest()
        # Reset file pointer for further reading
        await upload_file.seek(0)
        return file_hash, file_bytes


class CacheWarmer:
    """Background cache warming service"""

    @staticmethod
    async def warm_model_metadata(detector):
        """Warm cache with model metadata"""
        try:
            if detector is None:
                return

            metadata = {
                "model_type": str(type(detector).__name__),
                "loaded_at": datetime.now().isoformat(),
                "version": "1.0.0",
            }

            await CacheService.set_model_metadata(metadata)
            print("✓ Model metadata cached")
        except Exception as e:
            print(f"⚠ Cache warming failed: {e}")

    @staticmethod
    async def warm_frequently_accessed_data():
        """Warm cache with frequently accessed data"""
        # This would pre-load common queries, statistics, etc.
        # Implementation depends on usage patterns
        pass


# Async cache decorator with timeout
def cached_with_timeout(
    prefix: str,
    ttl: Optional[int] = None,
    timeout: float = 5.0
):
    """
    Cached decorator with timeout for cache operations

    Args:
        prefix: Cache key prefix
        ttl: Time to live in seconds
        timeout: Max seconds to wait for cache operations
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = CacheService._generate_cache_key(
                prefix,
                *args,
                **kwargs
            )

            # Try cache with timeout
            try:
                cached_result = await asyncio.wait_for(
                    redis_client.get_json(cache_key),
                    timeout=timeout
                )
                if cached_result is not None:
                    return cached_result
            except asyncio.TimeoutError:
                print(f"Cache GET timeout for {cache_key}")
            except Exception as e:
                print(f"Cache GET error for {cache_key}: {e}")

            # Execute function
            result = await func(*args, **kwargs)

            # Cache result (fire and forget - don't wait)
            asyncio.create_task(
                redis_client.set_json(cache_key, result, expire=ttl)
            )

            return result

        return wrapper
    return decorator


# Import datetime for metadata
from datetime import datetime
