"""
Database seeding utilities
Creates initial roles, permissions, and default data
"""
import logging
from sqlalchemy.orm import Session
from .models import Role, Permission, RolePermission, Tenant
from .session import SessionLocal

logger = logging.getLogger(__name__)

# ============================================================================
# Default Permissions
# ============================================================================

DEFAULT_PERMISSIONS = [
    # Patient permissions
    {"name": "patient:create", "resource": "patient", "action": "create", "description": "Create new patients"},
    {"name": "patient:read", "resource": "patient", "action": "read", "description": "View patient information"},
    {"name": "patient:update", "resource": "patient", "action": "update", "description": "Update patient information"},
    {"name": "patient:delete", "resource": "patient", "action": "delete", "description": "Delete patients"},

    # Prediction permissions
    {"name": "prediction:create", "resource": "prediction", "action": "create", "description": "Create predictions"},
    {"name": "prediction:read", "resource": "prediction", "action": "read", "description": "View predictions"},
    {"name": "prediction:update", "resource": "prediction", "action": "update", "description": "Update predictions"},
    {"name": "prediction:delete", "resource": "prediction", "action": "delete", "description": "Delete predictions"},
    {"name": "prediction:review", "resource": "prediction", "action": "review", "description": "Review and approve predictions"},

    # User permissions
    {"name": "user:create", "resource": "user", "action": "create", "description": "Create new users"},
    {"name": "user:read", "resource": "user", "action": "read", "description": "View user information"},
    {"name": "user:update", "resource": "user", "action": "update", "description": "Update user information"},
    {"name": "user:delete", "resource": "user", "action": "delete", "description": "Delete users"},

    # Role permissions
    {"name": "role:create", "resource": "role", "action": "create", "description": "Create roles"},
    {"name": "role:read", "resource": "role", "action": "read", "description": "View roles"},
    {"name": "role:update", "resource": "role", "action": "update", "description": "Update roles"},
    {"name": "role:delete", "resource": "role", "action": "delete", "description": "Delete roles"},

    # Audit log permissions
    {"name": "audit:read", "resource": "audit", "action": "read", "description": "View audit logs"},

    # Admin verification permissions (HITL workflow)
    {"name": "admin:verify", "resource": "admin", "action": "verify", "description": "Verify and label AI predictions for retraining"},

    # System permissions
    {"name": "system:admin", "resource": "system", "action": "admin", "description": "Full system administration"},
]

# ============================================================================
# Default Roles with their permissions
# ============================================================================

DEFAULT_ROLES = {
    "admin": {
        "description": "Full system administrator with all permissions",
        "is_system_role": True,
        "permissions": [
            "patient:create", "patient:read", "patient:update", "patient:delete",
            "prediction:create", "prediction:read", "prediction:update", "prediction:delete", "prediction:review",
            "user:create", "user:read", "user:update", "user:delete",
            "role:create", "role:read", "role:update", "role:delete",
            "audit:read",
            "admin:verify",
            "system:admin"
        ]
    },
    "doctor": {
        "description": "Medical doctor with full clinical access",
        "is_system_role": True,
        "permissions": [
            "patient:create", "patient:read", "patient:update", "patient:delete",
            "prediction:create", "prediction:read", "prediction:update", "prediction:delete", "prediction:review",
            "user:read",
            "audit:read",
            "admin:verify"
        ]
    },
    "radiologist": {
        "description": "Radiologist specializing in image analysis",
        "is_system_role": True,
        "permissions": [
            "patient:read",
            "prediction:create", "prediction:read", "prediction:update", "prediction:review",
            "admin:verify"
        ]
    },
    "technician": {
        "description": "Medical technician for data entry and imaging",
        "is_system_role": True,
        "permissions": [
            "patient:create", "patient:read", "patient:update",
            "prediction:create", "prediction:read"
        ]
    },
    "viewer": {
        "description": "Read-only access to predictions and patients",
        "is_system_role": True,
        "permissions": [
            "patient:read",
            "prediction:read"
        ]
    }
}

# ============================================================================
# Seeding Functions
# ============================================================================

def seed_permissions(db: Session) -> dict:
    """
    Seed default permissions
    Returns: dict of permission_name -> Permission object
    """
    logger.info("Seeding permissions...")
    permissions_map = {}

    for perm_data in DEFAULT_PERMISSIONS:
        # Check if permission already exists
        existing = db.query(Permission).filter(Permission.name == perm_data["name"]).first()

        if not existing:
            permission = Permission(**perm_data)
            db.add(permission)
            db.flush()
            permissions_map[perm_data["name"]] = permission
            logger.info(f"Created permission: {perm_data['name']}")
        else:
            permissions_map[perm_data["name"]] = existing
            logger.info(f"Permission already exists: {perm_data['name']}")

    db.commit()
    logger.info(f"Seeded {len(permissions_map)} permissions")
    return permissions_map

def seed_roles(db: Session, permissions_map: dict) -> dict:
    """
    Seed default roles and assign permissions
    Returns: dict of role_name -> Role object
    """
    logger.info("Seeding roles...")
    roles_map = {}

    for role_name, role_data in DEFAULT_ROLES.items():
        # Check if role already exists
        existing = db.query(Role).filter(Role.name == role_name).first()

        if not existing:
            role = Role(
                name=role_name,
                description=role_data["description"],
                is_system_role=role_data["is_system_role"]
            )
            db.add(role)
            db.flush()

            # Assign permissions to role
            for perm_name in role_data["permissions"]:
                if perm_name in permissions_map:
                    role_perm = RolePermission(
                        role_id=role.id,
                        permission_id=permissions_map[perm_name].id
                    )
                    db.add(role_perm)

            roles_map[role_name] = role
            logger.info(f"Created role: {role_name} with {len(role_data['permissions'])} permissions")
        else:
            roles_map[role_name] = existing
            logger.info(f"Role already exists: {role_name}")

    db.commit()
    logger.info(f"Seeded {len(roles_map)} roles")
    return roles_map

def seed_default_tenant(db: Session) -> Tenant:
    """
    Seed default tenant for initial setup
    Returns: Default Tenant object
    """
    logger.info("Seeding default tenant...")

    # Check if default tenant already exists
    existing = db.query(Tenant).filter(Tenant.tenant_id == "default").first()

    if not existing:
        tenant = Tenant(
            tenant_id="default",
            name="Default Organization",
            subscription_tier="enterprise",
            is_active=True,
            max_users=1000,
            max_predictions_per_month=100000,
            settings={}
        )
        db.add(tenant)
        db.commit()
        logger.info("Created default tenant")
        return tenant
    else:
        logger.info("Default tenant already exists")
        return existing

def seed_database():
    """
    Main seeding function - seeds all default data
    """
    try:
        logger.info("Starting database seeding...")
        db = SessionLocal()

        # Seed in order
        permissions_map = seed_permissions(db)
        roles_map = seed_roles(db, permissions_map)
        default_tenant = seed_default_tenant(db)

        db.close()

        logger.info("Database seeding completed successfully!")
        return True

    except Exception as e:
        logger.error(f"Error seeding database: {e}")
        if db:
            db.rollback()
            db.close()
        return False
