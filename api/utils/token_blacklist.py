"""
Token Blacklist Service
=======================
Manages token revocation using Redis or in-memory fallback.
Used for logout, password change, and session invalidation.
"""

import os
import time
from datetime import datetime
from typing import Optional, Set
from api.utils.logging_config import logger

# In-memory fallback when Redis not available
_memory_blacklist: Set[str] = set()
_memory_blacklist_expiry: dict = {}


class TokenBlacklist:
    """
    Token blacklist service for revoking JWT tokens.
    Uses Redis if available, falls back to in-memory storage.
    """
    
    _redis_client = None
    _initialized = False
    
    @classmethod
    async def init(cls):
        """Initialize Redis connection for token blacklist"""
        if cls._initialized:
            return
            
        try:
            import redis.asyncio as aioredis
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            cls._redis_client = await aioredis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            # Test connection
            await cls._redis_client.ping()
            cls._initialized = True
            logger.info("Token blacklist initialized with Redis")
        except Exception as e:
            logger.warning(f"Redis not available for token blacklist, using in-memory: {e}")
            cls._redis_client = None
            cls._initialized = True
    
    @classmethod
    async def add_token(cls, jti: str, expires_at: int) -> bool:
        """
        Add a token to the blacklist.
        
        Args:
            jti: JWT token ID (unique identifier)
            expires_at: Unix timestamp when token expires
            
        Returns:
            True if successfully added
        """
        if not cls._initialized:
            await cls.init()
        
        try:
            ttl = max(0, expires_at - int(time.time()))
            
            if cls._redis_client:
                # Redis: set with TTL
                await cls._redis_client.setex(
                    f"token_blacklist:{jti}",
                    ttl,
                    "revoked"
                )
            else:
                # In-memory fallback
                _memory_blacklist.add(jti)
                _memory_blacklist_expiry[jti] = expires_at
                # Cleanup expired tokens
                cls._cleanup_memory_blacklist()
            
            logger.info(f"Token revoked: {jti[:8]}...")
            return True
            
        except Exception as e:
            logger.error(f"Failed to blacklist token: {e}")
            return False
    
    @classmethod
    async def is_blacklisted(cls, jti: str) -> bool:
        """
        Check if a token is blacklisted.
        
        Args:
            jti: JWT token ID
            
        Returns:
            True if token is blacklisted/revoked
        """
        if not cls._initialized:
            await cls.init()
        
        try:
            if cls._redis_client:
                result = await cls._redis_client.exists(f"token_blacklist:{jti}")
                return result > 0
            else:
                # In-memory check
                if jti in _memory_blacklist:
                    # Check if expired
                    if _memory_blacklist_expiry.get(jti, 0) < time.time():
                        _memory_blacklist.discard(jti)
                        _memory_blacklist_expiry.pop(jti, None)
                        return False
                    return True
                return False
                
        except Exception as e:
            logger.error(f"Failed to check token blacklist: {e}")
            return False
    
    @classmethod
    async def revoke_all_user_tokens(cls, user_id: int, issued_before: datetime) -> bool:
        """
        Revoke all tokens for a user issued before a certain time.
        Used when password is changed.
        
        Args:
            user_id: User ID
            issued_before: Revoke tokens issued before this time
            
        Returns:
            True if successfully recorded
        """
        if not cls._initialized:
            await cls.init()
        
        try:
            timestamp = int(issued_before.timestamp())
            
            if cls._redis_client:
                # Store the revocation timestamp
                await cls._redis_client.set(
                    f"user_token_revoked:{user_id}",
                    str(timestamp),
                    ex=86400 * 7  # Keep for 7 days
                )
            else:
                # In-memory: store user revocation time
                _memory_blacklist.add(f"user:{user_id}:{timestamp}")
            
            logger.info(f"All tokens revoked for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to revoke user tokens: {e}")
            return False
    
    @classmethod
    async def is_user_token_revoked(cls, user_id: int, issued_at: datetime) -> bool:
        """
        Check if user's token should be considered revoked based on issue time.
        
        Args:
            user_id: User ID
            issued_at: When the token was issued
            
        Returns:
            True if token was issued before user's token revocation time
        """
        if not cls._initialized:
            await cls.init()
        
        try:
            if cls._redis_client:
                revoked_before = await cls._redis_client.get(f"user_token_revoked:{user_id}")
                if revoked_before:
                    return issued_at.timestamp() < float(revoked_before)
            else:
                # Check in-memory
                for key in _memory_blacklist:
                    if key.startswith(f"user:{user_id}:"):
                        revoked_time = int(key.split(":")[-1])
                        if issued_at.timestamp() < revoked_time:
                            return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to check user token revocation: {e}")
            return False
    
    @classmethod
    def _cleanup_memory_blacklist(cls):
        """Remove expired tokens from memory blacklist"""
        current_time = time.time()
        expired = [jti for jti, exp in _memory_blacklist_expiry.items() if exp < current_time]
        for jti in expired:
            _memory_blacklist.discard(jti)
            _memory_blacklist_expiry.pop(jti, None)


# Singleton instance
token_blacklist = TokenBlacklist()
