"""
Database initialization script
Creates tables and seeds initial data with test users
"""
import os
import sys
import logging
from passlib.context import CryptContext

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy.orm import Session
from api.database.session import SessionLocal, engine, Base
from api.database.models import User, Role, Permission, Tenant, RolePermission
from api.database.seed import (
    seed_permissions,
    seed_roles,
    seed_default_tenant
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Password hasher
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DEFAULT_PASSWORD = "iscs"  # Standard password for all test users

def create_tables():
    """Create all database tables"""
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")

def seed_test_users(db: Session, tenant: Tenant, roles_map: dict):
    """
    Seed test users for each role with password 'iscs'

    Args:
        db: Database session
        tenant: Default tenant
        roles_map: Dictionary of role_name -> Role object
    """
    logger.info("Seeding test users...")

    # Hash the default password
    hashed_password = pwd_context.hash(DEFAULT_PASSWORD)

    # Define test users for each role
    test_users = [
        {
            "username": "admin",
            "email": "admin@iscs.com",
            "first_name": "System",
            "last_name": "Administrator",
            "role": "admin",
            "is_superuser": True,
            "is_verified": True
        },
        {
            "username": "doctor1",
            "email": "doctor@iscs.com",
            "first_name": "John",
            "last_name": "Doctor",
            "role": "doctor",
            "is_superuser": False,
            "is_verified": True
        },
        {
            "username": "radiologist1",
            "email": "radiologist@iscs.com",
            "first_name": "Sarah",
            "last_name": "Radiologist",
            "role": "radiologist",
            "is_superuser": False,
            "is_verified": True
        },
        {
            "username": "technician1",
            "email": "technician@iscs.com",
            "first_name": "Mike",
            "last_name": "Technician",
            "role": "technician",
            "is_superuser": False,
            "is_verified": True
        },
        {
            "username": "viewer1",
            "email": "viewer@iscs.com",
            "first_name": "Jane",
            "last_name": "Viewer",
            "role": "viewer",
            "is_superuser": False,
            "is_verified": True
        }
    ]

    created_count = 0

    for user_data in test_users:
        # Check if user already exists
        existing_user = db.query(User).filter(
            (User.username == user_data["username"]) |
            (User.email == user_data["email"])
        ).first()

        if not existing_user:
            # Get role
            role_name = user_data.pop("role")
            role = roles_map.get(role_name)

            if not role:
                logger.warning(f"Role '{role_name}' not found, skipping user {user_data['username']}")
                continue

            # Create user
            new_user = User(
                tenant_id=tenant.id,
                hashed_password=hashed_password,
                is_active=True,
                role_id=role.id,
                **user_data
            )

            db.add(new_user)
            db.flush()
            created_count += 1

            logger.info(
                f"Created user: {new_user.username} "
                f"(email: {new_user.email}, role: {role_name}, password: {DEFAULT_PASSWORD})"
            )
        else:
            logger.info(f"User already exists: {user_data['username']}")

    db.commit()
    logger.info(f"Seeded {created_count} test users with password '{DEFAULT_PASSWORD}'")

def create_additional_tenants(db: Session):
    """
    Create additional test tenants for multi-tenancy testing

    Args:
        db: Database session
    """
    logger.info("Creating additional test tenants...")

    tenants = [
        {
            "tenant_id": "hospital1",
            "name": "General Hospital",
            "domain": "hospital1.example.com",
            "subscription_tier": "enterprise",
            "is_active": True,
            "max_users": 100,
            "max_predictions_per_month": 10000
        },
        {
            "tenant_id": "clinic1",
            "name": "Eye Clinic",
            "domain": "clinic1.example.com",
            "subscription_tier": "premium",
            "is_active": True,
            "max_users": 50,
            "max_predictions_per_month": 5000
        },
        {
            "tenant_id": "research1",
            "name": "Medical Research Institute",
            "domain": "research1.example.com",
            "subscription_tier": "enterprise",
            "is_active": True,
            "max_users": 200,
            "max_predictions_per_month": 50000
        }
    ]

    created_count = 0

    for tenant_data in tenants:
        existing = db.query(Tenant).filter(
            Tenant.tenant_id == tenant_data["tenant_id"]
        ).first()

        if not existing:
            tenant = Tenant(**tenant_data)
            db.add(tenant)
            db.flush()
            created_count += 1
            logger.info(f"Created tenant: {tenant.name} (ID: {tenant.tenant_id})")
        else:
            logger.info(f"Tenant already exists: {tenant_data['tenant_id']}")

    db.commit()
    logger.info(f"Created {created_count} additional tenants")

def init_database():
    """
    Main initialization function
    Creates tables and seeds initial data
    """
    try:
        logger.info("=" * 60)
        logger.info("Starting database initialization...")
        logger.info("=" * 60)

        # Create tables
        create_tables()

        # Get database session
        db = SessionLocal()

        try:
            # Seed permissions
            permissions_map = seed_permissions(db)

            # Seed roles
            roles_map = seed_roles(db, permissions_map)

            # Seed default tenant
            default_tenant = seed_default_tenant(db)

            # Seed test users with password 'iscs'
            seed_test_users(db, default_tenant, roles_map)

            # Create additional tenants
            create_additional_tenants(db)

            logger.info("=" * 60)
            logger.info("Database initialization completed successfully!")
            logger.info("=" * 60)
            logger.info("")
            logger.info("Test Users Created (all with password 'iscs'):")
            logger.info("-" * 60)
            logger.info("Username: admin        | Role: admin        | Email: admin@iscs.com")
            logger.info("Username: doctor1      | Role: doctor       | Email: doctor@iscs.com")
            logger.info("Username: radiologist1 | Role: radiologist  | Email: radiologist@iscs.com")
            logger.info("Username: technician1  | Role: technician   | Email: technician@iscs.com")
            logger.info("Username: viewer1      | Role: viewer       | Email: viewer@iscs.com")
            logger.info("-" * 60)
            logger.info("")
            logger.info("Tenants Created:")
            logger.info("-" * 60)
            logger.info("Tenant ID: default    | Name: Default Organization")
            logger.info("Tenant ID: hospital1  | Name: General Hospital")
            logger.info("Tenant ID: clinic1    | Name: Eye Clinic")
            logger.info("Tenant ID: research1  | Name: Medical Research Institute")
            logger.info("-" * 60)
            logger.info("")
            logger.info("Login Example:")
            logger.info("  Username: admin")
            logger.info("  Password: iscs")
            logger.info("  Tenant:   default")
            logger.info("=" * 60)

            return True

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)
