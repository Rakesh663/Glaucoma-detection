"""
Authentication routes
Handles login, registration, token refresh, and OAuth
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from datetime import datetime

from ..database.session import get_db
from ..database.models import User, Tenant
from ..auth.jwt import create_access_token, create_refresh_token, refresh_access_token, get_current_active_user
from ..utils.logging_config import logger

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
        role=user.role.name if user.role else "no_role"
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

    # Create new user
    hashed_password = get_password_hash(request.password)

    new_user = User(
        email=request.email,
        username=request.username,
        hashed_password=hashed_password,
        first_name=request.first_name,
        last_name=request.last_name,
        tenant_id=tenant.id,
        is_active=True,
        is_verified=False,  # Require email verification
        is_superuser=False
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Create tokens
    access_token = create_access_token(
        user_id=new_user.id,
        tenant_id=new_user.tenant_id,
        email=new_user.email,
        role=new_user.role.name if new_user.role else None
    )

    refresh_token_str = create_refresh_token(
        user_id=new_user.id,
        tenant_id=new_user.tenant_id
    )

    logger.info(f"New user registered: {new_user.email}")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_str,
        user_id=new_user.id,
        tenant_id=new_user.tenant_id,
        email=new_user.email,
        role=new_user.role.name if new_user.role else "no_role"
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
