"""
User Management Routes (Admin)
==============================
Handles user management operations including role assignment and account unlock.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from ..database.session import get_db
from ..database.models import User, Role
from ..auth.jwt import get_current_active_user
from ..auth.rbac import RequirePermission
from ..utils.logging_config import logger


# ============================================================================
# Router Setup
# ============================================================================

router = APIRouter(prefix="/api/v1/admin/users", tags=["Admin - User Management"])


# ============================================================================
# Request/Response Models
# ============================================================================

class UserResponse(BaseModel):
    id: int
    user_id: str
    email: str
    username: str
    first_name: str
    last_name: str
    role: Optional[str]
    is_active: bool
    is_verified: bool
    is_superuser: bool
    failed_login_attempts: int
    is_locked: bool
    created_at: datetime
    last_login_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    users: List[UserResponse]


class RoleChangeRequest(BaseModel):
    role_name: str


class RoleChangeResponse(BaseModel):
    status: str
    message: str
    user_id: str
    new_role: str


class UnlockAccountResponse(BaseModel):
    status: str
    message: str
    user_id: str
    failed_login_attempts: int


# ============================================================================
# User Management Endpoints
# ============================================================================

@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by name or email"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_locked: Optional[bool] = Query(None, description="Filter by locked status"),
    current_user: User = Depends(RequirePermission("user:read")),
    db: Session = Depends(get_db)
):
    """
    List all users with pagination and filters.
    
    Requires: user:read permission
    Available to: admin, superuser
    Multi-tenant: Only shows users from same tenant
    """
    from sqlalchemy import or_
    
    # Base query - filter by tenant
    query = db.query(User).filter(User.tenant_id == current_user.tenant_id)
    
    # Apply search filter
    if search:
        search_filter = or_(
            User.first_name.ilike(f"%{search}%"),
            User.last_name.ilike(f"%{search}%"),
            User.email.ilike(f"%{search}%"),
            User.username.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
    
    # Apply active filter
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    # Apply locked filter (5+ failed attempts)
    if is_locked is not None:
        if is_locked:
            query = query.filter(User.failed_login_attempts >= 5)
        else:
            query = query.filter(User.failed_login_attempts < 5)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * page_size
    users = query.order_by(User.created_at.desc()).offset(offset).limit(page_size).all()
    
    # Format response
    user_list = []
    for user in users:
        user_list.append(UserResponse(
            id=user.id,
            user_id=user.user_id,
            email=user.email,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role.name if user.role else None,
            is_active=user.is_active,
            is_verified=user.is_verified,
            is_superuser=user.is_superuser,
            failed_login_attempts=user.failed_login_attempts,
            is_locked=user.failed_login_attempts >= 5,
            created_at=user.created_at,
            last_login_at=user.last_login_at
        ))
    
    logger.info(
        f"User list accessed by {current_user.email}",
        extra={"user_id": current_user.id, "tenant_id": current_user.tenant_id, "total_users": total}
    )
    
    return UserListResponse(
        total=total,
        page=page,
        page_size=page_size,
        users=user_list
    )


@router.get("/{user_id}")
async def get_user(
    user_id: str,
    current_user: User = Depends(RequirePermission("user:read")),
    db: Session = Depends(get_db)
):
    """
    Get a specific user's details.
    
    Requires: user:read permission
    """
    user = db.query(User).filter(
        User.user_id == user_id,
        User.tenant_id == current_user.tenant_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{user_id}' not found"
        )
    
    return UserResponse(
        id=user.id,
        user_id=user.user_id,
        email=user.email,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role.name if user.role else None,
        is_active=user.is_active,
        is_verified=user.is_verified,
        is_superuser=user.is_superuser,
        failed_login_attempts=user.failed_login_attempts,
        is_locked=user.failed_login_attempts >= 5,
        created_at=user.created_at,
        last_login_at=user.last_login_at
    )


@router.put("/{user_id}/role", response_model=RoleChangeResponse)
async def change_user_role(
    user_id: str,
    request: RoleChangeRequest,
    current_user: User = Depends(RequirePermission("role:assign")),
    db: Session = Depends(get_db)
):
    """
    Change a user's role.
    
    Requires: role:assign permission
    Available to: admin, superuser
    
    Args:
        user_id: User ID to modify
        request: New role name
        
    Returns:
        Confirmation with new role
    """
    # Find user
    user = db.query(User).filter(
        User.user_id == user_id,
        User.tenant_id == current_user.tenant_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{user_id}' not found"
        )
    
    # Prevent changing own role (safety)
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role"
        )
    
    # Find role
    role = db.query(Role).filter(
        Role.name == request.role_name,
        Role.tenant_id == current_user.tenant_id
    ).first()
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role '{request.role_name}' not found"
        )
    
    # Update user's role
    old_role = user.role.name if user.role else "none"
    user.role_id = role.id
    user.updated_at = datetime.utcnow()
    db.commit()
    
    logger.info(
        f"User role changed: {user_id} from {old_role} to {role.name} by {current_user.email}",
        extra={
            "target_user_id": user.id,
            "old_role": old_role,
            "new_role": role.name,
            "changed_by": current_user.id
        }
    )
    
    return RoleChangeResponse(
        status="success",
        message=f"User role changed from '{old_role}' to '{role.name}'",
        user_id=user_id,
        new_role=role.name
    )


@router.post("/{user_id}/unlock", response_model=UnlockAccountResponse)
async def unlock_user_account(
    user_id: str,
    current_user: User = Depends(RequirePermission("user:update")),
    db: Session = Depends(get_db)
):
    """
    Unlock a user's account by resetting failed login attempts.
    
    Requires: user:update permission
    Available to: admin, superuser
    
    Args:
        user_id: User ID to unlock
        
    Returns:
        Confirmation
    """
    # Find user
    user = db.query(User).filter(
        User.user_id == user_id,
        User.tenant_id == current_user.tenant_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{user_id}' not found"
        )
    
    # Check if actually locked
    if user.failed_login_attempts < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is not locked"
        )
    
    # Reset failed attempts
    old_attempts = user.failed_login_attempts
    user.failed_login_attempts = 0
    user.updated_at = datetime.utcnow()
    db.commit()
    
    logger.info(
        f"Account unlocked: {user_id} by {current_user.email} (was {old_attempts} failed attempts)",
        extra={
            "target_user_id": user.id,
            "unlocked_by": current_user.id,
            "previous_failed_attempts": old_attempts
        }
    )
    
    return UnlockAccountResponse(
        status="success",
        message=f"Account unlocked successfully. Previous failed attempts: {old_attempts}",
        user_id=user_id,
        failed_login_attempts=0
    )


@router.post("/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    current_user: User = Depends(RequirePermission("user:delete")),
    db: Session = Depends(get_db)
):
    """
    Deactivate a user account.
    
    Requires: user:delete permission
    """
    user = db.query(User).filter(
        User.user_id == user_id,
        User.tenant_id == current_user.tenant_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{user_id}' not found"
        )
    
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )
    
    user.is_active = False
    user.updated_at = datetime.utcnow()
    db.commit()
    
    logger.warning(f"User deactivated: {user_id} by {current_user.email}")
    
    return {"status": "success", "message": f"User {user_id} has been deactivated"}


@router.post("/{user_id}/activate")
async def activate_user(
    user_id: str,
    current_user: User = Depends(RequirePermission("user:update")),
    db: Session = Depends(get_db)
):
    """
    Activate a user account.
    
    Requires: user:update permission
    """
    user = db.query(User).filter(
        User.user_id == user_id,
        User.tenant_id == current_user.tenant_id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{user_id}' not found"
        )
    
    user.is_active = True
    user.updated_at = datetime.utcnow()
    db.commit()
    
    logger.info(f"User activated: {user_id} by {current_user.email}")
    
    return {"status": "success", "message": f"User {user_id} has been activated"}
