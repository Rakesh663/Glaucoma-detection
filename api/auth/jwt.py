"""
JWT token creation and verification
Handles access tokens and refresh tokens
"""
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from ..database.session import get_db
from ..database.models import User

# ============================================================================
# JWT Configuration
# ============================================================================

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change_this_super_secret_key_in_production")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

# ============================================================================
# Token Creation
# ============================================================================

def create_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
    token_type: str = "access"
) -> str:
    """
    Create a JWT token

    Args:
        data: Data to encode in the token
        expires_delta: Token expiration time
        token_type: Type of token (access or refresh)

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()

    # Set expiration
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        # Default expiration based on token type
        if token_type == "refresh":
            expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": token_type
    })

    # Encode token
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_access_token(
    user_id: int,
    tenant_id: int,
    email: str,
    role: Optional[str] = None,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create an access token for a user

    Args:
        user_id: User ID
        tenant_id: Tenant ID for multi-tenancy
        email: User email
        role: User role
        expires_delta: Custom expiration time

    Returns:
        JWT access token
    """
    data = {
        "sub": str(user_id),
        "tenant_id": tenant_id,
        "email": email,
        "role": role
    }

    return create_token(data, expires_delta, token_type="access")

def create_refresh_token(
    user_id: int,
    tenant_id: int,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a refresh token for a user

    Args:
        user_id: User ID
        tenant_id: Tenant ID
        expires_delta: Custom expiration time

    Returns:
        JWT refresh token
    """
    data = {
        "sub": str(user_id),
        "tenant_id": tenant_id
    }

    return create_token(data, expires_delta, token_type="refresh")

# ============================================================================
# Token Verification
# ============================================================================

def verify_token(
    token: str,
    token_type: str = "access"
) -> Dict[str, Any]:
    """
    Verify and decode a JWT token

    Args:
        token: JWT token to verify
        token_type: Expected token type (access or refresh)

    Returns:
        Decoded token payload

    Raises:
        HTTPException: If token is invalid
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decode token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Verify token type
        if payload.get("type") != token_type:
            raise credentials_exception

        # Extract user ID
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        # Check expiration
        exp = payload.get("exp")
        if exp is None or datetime.fromtimestamp(exp) < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return payload

    except JWTError:
        raise credentials_exception

# ============================================================================
# User Dependencies
# ============================================================================

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Get the current authenticated user from JWT token

    Args:
        token: JWT access token
        db: Database session

    Returns:
        User object

    Raises:
        HTTPException: If user not found or invalid token
    """
    # Verify token
    payload = verify_token(token, token_type="access")

    # Get user ID from payload
    user_id = int(payload.get("sub"))

    # Query database for user
    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get the current active user
    Ensures user account is active

    Args:
        current_user: Current authenticated user

    Returns:
        Active user object

    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account"
        )

    return current_user

async def get_current_verified_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Get the current verified user
    Ensures user email is verified

    Args:
        current_user: Current active user

    Returns:
        Verified user object

    Raises:
        HTTPException: If user is not verified
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email address"
        )

    return current_user

async def get_current_superuser(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Get the current superuser
    Ensures user has superuser privileges

    Args:
        current_user: Current active user

    Returns:
        Superuser object

    Raises:
        HTTPException: If user is not a superuser
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Superuser access required."
        )

    return current_user

# ============================================================================
# Token Refresh
# ============================================================================

def refresh_access_token(refresh_token: str, db: Session) -> Dict[str, str]:
    """
    Generate a new access token from a refresh token

    Args:
        refresh_token: Valid refresh token
        db: Database session

    Returns:
        Dictionary with new access token and refresh token

    Raises:
        HTTPException: If refresh token is invalid
    """
    # Verify refresh token
    payload = verify_token(refresh_token, token_type="refresh")

    # Get user ID and tenant ID
    user_id = int(payload.get("sub"))
    tenant_id = payload.get("tenant_id")

    # Query database for user
    user = db.query(User).filter(User.id == user_id).first()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # Create new tokens
    new_access_token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        role=user.role.name if user.role else None
    )

    new_refresh_token = create_refresh_token(
        user_id=user.id,
        tenant_id=user.tenant_id
    )

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }
