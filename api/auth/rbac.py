"""
Role-Based Access Control (RBAC) system
Permission checking and authorization
"""
from typing import List, Optional
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database.session import get_db
from ..database.models import User, Permission, RolePermission
from .jwt import get_current_active_user

# ============================================================================
# Permission Checking
# ============================================================================

def user_has_permission(
    user: User,
    permission_name: str,
    db: Session
) -> bool:
    """
    Check if a user has a specific permission

    Args:
        user: User object
        permission_name: Permission name (e.g., "patient:create")
        db: Database session

    Returns:
        True if user has permission, False otherwise
    """
    # Superusers have all permissions
    if user.is_superuser:
        return True

    # Check if user has a role
    if not user.role:
        return False

    # Query for permission through role
    has_perm = db.query(Permission).join(
        RolePermission, RolePermission.permission_id == Permission.id
    ).filter(
        RolePermission.role_id == user.role_id,
        Permission.name == permission_name
    ).first()

    return has_perm is not None

def user_has_any_permission(
    user: User,
    permission_names: List[str],
    db: Session
) -> bool:
    """
    Check if user has ANY of the specified permissions

    Args:
        user: User object
        permission_names: List of permission names
        db: Database session

    Returns:
        True if user has at least one permission
    """
    if user.is_superuser:
        return True

    for perm_name in permission_names:
        if user_has_permission(user, perm_name, db):
            return True

    return False

def user_has_all_permissions(
    user: User,
    permission_names: List[str],
    db: Session
) -> bool:
    """
    Check if user has ALL of the specified permissions

    Args:
        user: User object
        permission_names: List of permission names
        db: Database session

    Returns:
        True if user has all permissions
    """
    if user.is_superuser:
        return True

    for perm_name in permission_names:
        if not user_has_permission(user, perm_name, db):
            return False

    return True

# ============================================================================
# Permission Dependencies
# ============================================================================

class RequirePermission:
    """
    Dependency class for requiring specific permissions
    Usage: Depends(RequirePermission("patient:create"))
    """

    def __init__(
        self,
        permission: str,
        require_all: bool = True
    ):
        """
        Initialize permission requirement

        Args:
            permission: Single permission name or list of permissions
            require_all: If True, user must have ALL permissions.
                        If False, user must have ANY permission.
        """
        if isinstance(permission, str):
            self.permissions = [permission]
        else:
            self.permissions = permission

        self.require_all = require_all

    async def __call__(
        self,
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ) -> User:
        """
        Check if user has required permissions

        Args:
            current_user: Current authenticated user
            db: Database session

        Returns:
            User object if authorized

        Raises:
            HTTPException: If user lacks required permissions
        """
        # Superusers always pass
        if current_user.is_superuser:
            return current_user

        # Check permissions
        if self.require_all:
            has_permission = user_has_all_permissions(
                current_user, self.permissions, db
            )
        else:
            has_permission = user_has_any_permission(
                current_user, self.permissions, db
            )

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {', '.join(self.permissions)}"
            )

        return current_user

# ============================================================================
# Role Dependencies
# ============================================================================

class RequireRole:
    """
    Dependency class for requiring specific roles
    Usage: Depends(RequireRole(["admin", "doctor"]))
    """

    def __init__(self, roles: List[str]):
        """
        Initialize role requirement

        Args:
            roles: List of allowed role names
        """
        if isinstance(roles, str):
            self.roles = [roles]
        else:
            self.roles = roles

    async def __call__(
        self,
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ) -> User:
        """
        Check if user has required role

        Args:
            current_user: Current authenticated user
            db: Database session

        Returns:
            User object if authorized

        Raises:
            HTTPException: If user lacks required role
        """
        # Superusers always pass
        if current_user.is_superuser:
            return current_user

        # Check role
        if not current_user.role or current_user.role.name not in self.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {', '.join(self.roles)}"
            )

        return current_user

# ============================================================================
# Resource-specific permission checking
# ============================================================================

async def check_resource_access(
    user: User,
    resource: str,
    action: str,
    resource_tenant_id: Optional[int] = None,
    db: Session = None
) -> bool:
    """
    Check if user has access to a specific resource

    Args:
        user: User object
        resource: Resource type (patient, prediction, etc.)
        action: Action (create, read, update, delete)
        resource_tenant_id: Tenant ID of the resource (for multi-tenancy check)
        db: Database session

    Returns:
        True if user has access, False otherwise

    Raises:
        HTTPException: If access is denied
    """
    # Multi-tenancy check
    if resource_tenant_id is not None and user.tenant_id != resource_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Resource belongs to different tenant"
        )

    # Permission check
    permission_name = f"{resource}:{action}"

    if db:
        has_perm = user_has_permission(user, permission_name, db)
    else:
        # Superusers always have access
        has_perm = user.is_superuser

    if not has_perm:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions. Required: {permission_name}"
        )

    return True

# ============================================================================
# Helper Functions
# ============================================================================

def get_user_permissions(user: User, db: Session) -> List[str]:
    """
    Get all permissions for a user

    Args:
        user: User object
        db: Database session

    Returns:
        List of permission names
    """
    if user.is_superuser:
        # Superusers have all permissions
        all_permissions = db.query(Permission).all()
        return [perm.name for perm in all_permissions]

    if not user.role:
        return []

    # Query permissions through role
    permissions = db.query(Permission).join(
        RolePermission, RolePermission.permission_id == Permission.id
    ).filter(
        RolePermission.role_id == user.role_id
    ).all()

    return [perm.name for perm in permissions]
