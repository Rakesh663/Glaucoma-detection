"""
OAuth 2.0 integration for third-party authentication
Supports Google, GitHub, Azure, and other providers
"""
import os
from typing import Optional, Dict, Any
from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
import httpx

from ..database.models import User, Tenant
from .password import hash_password
from .jwt import create_access_token, create_refresh_token

# ============================================================================
# OAuth Configuration
# ============================================================================

oauth = OAuth()

# Google OAuth
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/v1/auth/google/callback")

if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    oauth.register(
        name='google',
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile'
        }
    )

# GitHub OAuth
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", "http://localhost:8000/api/v1/auth/github/callback")

if GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET:
    oauth.register(
        name='github',
        client_id=GITHUB_CLIENT_ID,
        client_secret=GITHUB_CLIENT_SECRET,
        access_token_url='https://github.com/login/oauth/access_token',
        authorize_url='https://github.com/login/oauth/authorize',
        api_base_url='https://api.github.com/',
        client_kwargs={'scope': 'user:email'},
    )

# Azure AD OAuth
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID", "common")
AZURE_REDIRECT_URI = os.getenv("AZURE_REDIRECT_URI", "http://localhost:8000/api/v1/auth/azure/callback")

if AZURE_CLIENT_ID and AZURE_CLIENT_SECRET:
    oauth.register(
        name='azure',
        client_id=AZURE_CLIENT_ID,
        client_secret=AZURE_CLIENT_SECRET,
        server_metadata_url=f'https://login.microsoftonline.com/{AZURE_TENANT_ID}/v2.0/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile'
        }
    )

# ============================================================================
# Provider-specific User Info Fetchers
# ============================================================================

async def get_google_user_info(token: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch user information from Google

    Args:
        token: OAuth token response

    Returns:
        User information dictionary
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {token["access_token"]}'}
        )
        response.raise_for_status()
        user_data = response.json()

        return {
            'oauth_id': user_data['id'],
            'email': user_data['email'],
            'first_name': user_data.get('given_name'),
            'last_name': user_data.get('family_name'),
            'is_verified': user_data.get('verified_email', False)
        }

async def get_github_user_info(token: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch user information from GitHub

    Args:
        token: OAuth token response

    Returns:
        User information dictionary
    """
    async with httpx.AsyncClient() as client:
        # Get user profile
        user_response = await client.get(
            'https://api.github.com/user',
            headers={
                'Authorization': f'token {token["access_token"]}',
                'Accept': 'application/vnd.github.v3+json'
            }
        )
        user_response.raise_for_status()
        user_data = user_response.json()

        # Get primary email
        email_response = await client.get(
            'https://api.github.com/user/emails',
            headers={
                'Authorization': f'token {token["access_token"]}',
                'Accept': 'application/vnd.github.v3+json'
            }
        )
        email_response.raise_for_status()
        emails = email_response.json()

        primary_email = next(
            (e['email'] for e in emails if e['primary'] and e['verified']),
            user_data.get('email')
        )

        # Parse name
        name_parts = user_data.get('name', '').split(' ', 1)
        first_name = name_parts[0] if name_parts else None
        last_name = name_parts[1] if len(name_parts) > 1 else None

        return {
            'oauth_id': str(user_data['id']),
            'email': primary_email,
            'first_name': first_name,
            'last_name': last_name,
            'is_verified': True  # GitHub emails are verified
        }

async def get_azure_user_info(token: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch user information from Azure AD

    Args:
        token: OAuth token response

    Returns:
        User information dictionary
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            'https://graph.microsoft.com/v1.0/me',
            headers={'Authorization': f'Bearer {token["access_token"]}'}
        )
        response.raise_for_status()
        user_data = response.json()

        return {
            'oauth_id': user_data['id'],
            'email': user_data['userPrincipalName'],
            'first_name': user_data.get('givenName'),
            'last_name': user_data.get('surname'),
            'is_verified': True  # Azure AD emails are verified
        }

# ============================================================================
# OAuth User Management
# ============================================================================

async def get_or_create_oauth_user(
    provider: str,
    user_info: Dict[str, Any],
    db: Session,
    default_tenant_id: Optional[int] = None
) -> User:
    """
    Get existing OAuth user or create a new one

    Args:
        provider: OAuth provider name (google, github, azure)
        user_info: User information from OAuth provider
        db: Database session
        default_tenant_id: Default tenant ID for new users

    Returns:
        User object

    Raises:
        HTTPException: If user creation fails
    """
    # Check if user exists with this OAuth provider
    existing_user = db.query(User).filter(
        User.oauth_provider == provider,
        User.oauth_id == user_info['oauth_id']
    ).first()

    if existing_user:
        # Update last login
        existing_user.last_login_at = db.func.now()
        db.commit()
        db.refresh(existing_user)
        return existing_user

    # Check if user exists with this email
    email_user = db.query(User).filter(User.email == user_info['email']).first()

    if email_user:
        # Link OAuth provider to existing user
        if not email_user.oauth_provider:
            email_user.oauth_provider = provider
            email_user.oauth_id = user_info['oauth_id']
            email_user.is_verified = user_info.get('is_verified', True)
            email_user.last_login_at = db.func.now()
            db.commit()
            db.refresh(email_user)
            return email_user
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Email already registered with {email_user.oauth_provider}"
            )

    # Create new user
    # Get or create default tenant
    if not default_tenant_id:
        default_tenant = db.query(Tenant).filter(Tenant.tenant_id == "default").first()
        if not default_tenant:
            default_tenant = Tenant(
                tenant_id="default",
                name="Default Organization",
                is_active=True
            )
            db.add(default_tenant)
            db.commit()
            db.refresh(default_tenant)
        default_tenant_id = default_tenant.id

    # Generate username from email
    username = user_info['email'].split('@')[0]

    # Check if username exists, append number if needed
    base_username = username
    counter = 1
    while db.query(User).filter(User.username == username).first():
        username = f"{base_username}{counter}"
        counter += 1

    # Create user
    new_user = User(
        tenant_id=default_tenant_id,
        email=user_info['email'],
        username=username,
        hashed_password=hash_password(os.urandom(32).hex()),  # Random password for OAuth users
        oauth_provider=provider,
        oauth_id=user_info['oauth_id'],
        first_name=user_info.get('first_name'),
        last_name=user_info.get('last_name'),
        is_active=True,
        is_verified=user_info.get('is_verified', True),
        last_login_at=db.func.now()
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user

# ============================================================================
# OAuth Flow Handlers
# ============================================================================

async def handle_oauth_callback(
    provider: str,
    token: Dict[str, Any],
    db: Session
) -> Dict[str, str]:
    """
    Handle OAuth callback and create JWT tokens

    Args:
        provider: OAuth provider name
        token: OAuth token response
        db: Database session

    Returns:
        Dictionary with access token and refresh token

    Raises:
        HTTPException: If OAuth flow fails
    """
    try:
        # Get user info based on provider
        if provider == 'google':
            user_info = await get_google_user_info(token)
        elif provider == 'github':
            user_info = await get_github_user_info(token)
        elif provider == 'azure':
            user_info = await get_azure_user_info(token)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported OAuth provider: {provider}"
            )

        # Get or create user
        user = await get_or_create_oauth_user(provider, user_info, db)

        # Create JWT tokens
        access_token = create_access_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            role=user.role.name if user.role else None
        )

        refresh_token = create_refresh_token(
            user_id=user.id,
            tenant_id=user.tenant_id
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

    except OAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth authentication failed: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication error: {str(e)}"
        )
