"""
Authentication routes
Handles login, registration, token refresh, and OAuth
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from datetime import datetime
from typing import Optional

from ..database.session import get_db
from ..database.models import User, Tenant, Role
from ..auth.jwt import create_access_token, create_refresh_token, refresh_access_token, get_current_active_user
from ..utils.logging_config import logger

# OAuth2 scheme for logout endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

# Account lockout settings
MAX_FAILED_LOGIN_ATTEMPTS = 5
ACCOUNT_LOCKOUT_MESSAGE = "Account locked due to too many failed login attempts. Please contact administrator."

# ============================================================================
# Router Setup
# ============================================================================

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])

# ============================================================================
# Password Hashing
# ============================================================================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)

# ============================================================================
# Request/Response Models
# ============================================================================

class LoginRequest(BaseModel):
    username: str
    password: str
    tenant_id: str = "default"

class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    first_name: str
    last_name: str
    tenant_id: str = "default"
    role: str = "viewer"  # Default role if not specified

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: int
    tenant_id: int
    email: str
    role: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

# ============================================================================
# Authentication Endpoints
# ============================================================================

@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Login endpoint for obtaining access and refresh tokens

    Args:
        form_data: OAuth2 password request form (username, password)
        db: Database session

    Returns:
        Access token, refresh token, and user information
    """
    # Find user by username or email
    user = db.query(User).filter(
        (User.username == form_data.username) | (User.email == form_data.username)
    ).first()

    if not user:
        logger.warning(f"Login attempt failed: user not found - {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if account is locked (too many failed attempts)
    if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
        logger.warning(f"Login attempt failed: account locked - {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ACCOUNT_LOCKOUT_MESSAGE
        )

    # Verify password
    if not verify_password(form_data.password, user.hashed_password):
        user.failed_login_attempts += 1
        db.commit()
        logger.warning(f"Login attempt failed: incorrect password - {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        logger.warning(f"Login attempt failed: inactive user - {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account"
        )

    # Update last login
    user.last_login_at = datetime.utcnow()
    user.failed_login_attempts = 0
    db.commit()

    # Create tokens
    access_token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        role=user.role.name if user.role else None
    )

    refresh_token_str = create_refresh_token(
        user_id=user.id,
        tenant_id=user.tenant_id
    )

    logger.info(f"User logged in successfully: {user.email}")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_str,
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        role=user.role.name if user.role else "viewer"
    )

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new user

    Args:
        request: Registration request data
        db: Database session

    Returns:
        Access token, refresh token, and user information
    """
    # Check if user already exists
    existing_user = db.query(User).filter(
        (User.email == request.email) | (User.username == request.username)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or username already exists"
        )

    # Get or create tenant
    tenant = db.query(Tenant).filter(Tenant.tenant_id == request.tenant_id).first()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{request.tenant_id}' not found"
        )

    # Check if tenant is active
    if not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant is inactive"
        )

    # Look up role by name
    role = db.query(Role).filter(Role.name == request.role).first()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role '{request.role}' not found"
        )

    # Create new user
    hashed_password = get_password_hash(request.password)

    new_user = User(
        email=request.email,
        username=request.username,
        hashed_password=hashed_password,
        first_name=request.first_name,
        last_name=request.last_name,
        tenant_id=tenant.id,
        role_id=role.id,  # Assign role_id
        is_active=True,
        is_verified=False,  # Require email verification
        is_superuser=False
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Create tokens (use the role object we already queried)
    access_token = create_access_token(
        user_id=new_user.id,
        tenant_id=new_user.tenant_id,
        email=new_user.email,
        role=role.name  # Use the role object we queried earlier
    )

    refresh_token_str = create_refresh_token(
        user_id=new_user.id,
        tenant_id=new_user.tenant_id
    )

    logger.info(f"New user registered: {new_user.email} with role: {role.name}")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_str,
        user_id=new_user.id,
        tenant_id=new_user.tenant_id,
        email=new_user.email,
        role=role.name  # Use the role object we queried earlier
    )

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token

    Args:
        request: Refresh token request
        db: Database session

    Returns:
        New access token and refresh token
    """
    try:
        tokens = refresh_access_token(request.refresh_token, db)

        # Get user info for response
        from ..auth.jwt import verify_token
        payload = verify_token(tokens["access_token"], token_type="access")

        return TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            user_id=int(payload.get("sub")),
            tenant_id=payload.get("tenant_id"),
            email=payload.get("email"),
            role=payload.get("role", "no_role")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get current user information

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        User information
    """
    return {
        "id": current_user.id,
        "user_id": current_user.user_id,
        "email": current_user.email,
        "username": current_user.username,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "tenant_id": current_user.tenant_id,
        "role": current_user.role.name if current_user.role else None,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
        "is_superuser": current_user.is_superuser
    }


# ============================================================================
# New Security Endpoints
# ============================================================================

class LogoutRequest(BaseModel):
    """Logout request - optionally include refresh token to revoke"""
    refresh_token: Optional[str] = None

class PasswordChangeRequest(BaseModel):
    """Password change request"""
    current_password: str
    new_password: str

class LogoutResponse(BaseModel):
    status: str
    message: str

class PasswordChangeResponse(BaseModel):
    status: str
    message: str


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: LogoutRequest = None,
    authorization: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Logout user and invalidate tokens.
    
    This endpoint:
    1. Blacklists the current access token
    2. Optionally blacklists the refresh token
    3. Tokens are invalid until they expire
    
    Args:
        request: Optional logout request with refresh token
        authorization: Current access token
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Logout confirmation
    """
    from ..utils.token_blacklist import token_blacklist
    from ..auth.jwt import verify_token
    
    try:
        # Decode current access token to get JTI and expiry
        payload = verify_token(authorization, token_type="access")
        jti = payload.get("jti")
        exp = payload.get("exp")
        
        if jti and exp:
            # Add access token to blacklist
            await token_blacklist.add_token(jti, exp)
            logger.info(f"User {current_user.email} logged out, token revoked")
        
        # If refresh token provided, blacklist it too
        if request and request.refresh_token:
            try:
                refresh_payload = verify_token(request.refresh_token, token_type="refresh")
                refresh_jti = refresh_payload.get("jti")
                refresh_exp = refresh_payload.get("exp")
                if refresh_jti and refresh_exp:
                    await token_blacklist.add_token(refresh_jti, refresh_exp)
            except Exception:
                pass  # Ignore invalid refresh token
        
        return LogoutResponse(
            status="success",
            message="Successfully logged out. Token has been revoked."
        )
        
    except Exception as e:
        logger.error(f"Logout error: {e}")
        # Even on error, return success (logout should always "succeed")
        return LogoutResponse(
            status="success",
            message="Logged out"
        )


@router.post("/change-password", response_model=PasswordChangeResponse)
async def change_password(
    request: PasswordChangeRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Change user password and invalidate all existing tokens.
    
    This endpoint:
    1. Verifies the current password
    2. Updates to the new password
    3. Revokes ALL tokens issued before this change
    
    Args:
        request: Password change request
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Password change confirmation
    """
    from ..utils.token_blacklist import token_blacklist
    
    # Validate password requirements
    if len(request.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters"
        )
    
    # Verify current password
    if not verify_password(request.current_password, current_user.hashed_password):
        logger.warning(f"Password change failed: incorrect current password for {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )
    
    # Check new password is different
    if request.current_password == request.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password"
        )
    
    # Update password
    current_user.hashed_password = get_password_hash(request.new_password)
    current_user.updated_at = datetime.utcnow()
    db.commit()
    
    # Revoke all existing tokens for this user
    await token_blacklist.revoke_all_user_tokens(
        user_id=current_user.id,
        issued_before=datetime.utcnow()
    )
    
    logger.info(f"Password changed for user {current_user.email}, all tokens revoked")
    
    return PasswordChangeResponse(
        status="success",
        message="Password changed successfully. Please login again with your new password."
    )
