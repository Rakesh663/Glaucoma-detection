"""
Script to create Apollo tenant and users for multi-tenancy testing
"""
import sys
import os
from passlib.context import CryptContext

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from api.database.session import SessionLocal
from api.database.models import User, Role, Tenant

# Password hasher
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
DEFAULT_PASSWORD = "iscs"

def create_apollo_tenant():
    """Create Apollo tenant and users"""
    db = SessionLocal()

    try:
        print("\n" + "="*80)
        print("CREATING APOLLO TENANT AND USERS")
        print("="*80)

        # Step 1: Create Apollo tenant
        print("\n[STEP 1] Creating Apollo tenant...")
        existing_tenant = db.query(Tenant).filter(Tenant.tenant_id == "apollo").first()

        if existing_tenant:
            print(f"[INFO] Apollo tenant already exists (ID: {existing_tenant.id})")
            apollo_tenant = existing_tenant
        else:
            apollo_tenant = Tenant(
                tenant_id="apollo",
                name="Apollo Medical Center",
                domain="apollo.example.com",
                subscription_tier="enterprise",
                is_active=True,
                max_users=100,
                max_predictions_per_month=10000,
                settings={}
            )
            db.add(apollo_tenant)
            db.flush()
            print(f"[PASS] Created Apollo tenant (ID: {apollo_tenant.id})")

        # Step 2: Get roles
        print("\n[STEP 2] Getting roles...")
        roles = {
            "admin": db.query(Role).filter(Role.name == "admin").first(),
            "doctor": db.query(Role).filter(Role.name == "doctor").first(),
            "radiologist": db.query(Role).filter(Role.name == "radiologist").first(),
            "technician": db.query(Role).filter(Role.name == "technician").first(),
            "viewer": db.query(Role).filter(Role.name == "viewer").first()
        }

        print(f"[PASS] Found {len(roles)} roles")

        # Step 3: Create users for Apollo tenant
        print("\n[STEP 3] Creating users for Apollo tenant...")

        hashed_password = pwd_context.hash(DEFAULT_PASSWORD)

        apollo_users = [
            {
                "username": "apollo_admin",
                "email": "admin@apollo.com",
                "first_name": "Apollo",
                "last_name": "Administrator",
                "role": "admin",
                "is_superuser": True,
                "is_verified": True
            },
            {
                "username": "apollo_doctor",
                "email": "doctor@apollo.com",
                "first_name": "Apollo",
                "last_name": "Doctor",
                "role": "doctor",
                "is_superuser": False,
                "is_verified": True
            },
            {
                "username": "apollo_radiologist",
                "email": "radiologist@apollo.com",
                "first_name": "Apollo",
                "last_name": "Radiologist",
                "role": "radiologist",
                "is_superuser": False,
                "is_verified": True
            },
            {
                "username": "apollo_tech",
                "email": "tech@apollo.com",
                "first_name": "Apollo",
                "last_name": "Technician",
                "role": "technician",
                "is_superuser": False,
                "is_verified": True
            }
        ]

        created_count = 0

        for user_data in apollo_users:
            # Check if user exists
            existing_user = db.query(User).filter(
                (User.username == user_data["username"]) |
                (User.email == user_data["email"])
            ).first()

            if not existing_user:
                role_name = user_data.pop("role")
                role = roles.get(role_name)

                if not role:
                    print(f"[WARN] Role '{role_name}' not found, skipping {user_data['username']}")
                    continue

                new_user = User(
                    tenant_id=apollo_tenant.id,
                    hashed_password=hashed_password,
                    is_active=True,
                    role_id=role.id,
                    **user_data
                )

                db.add(new_user)
                db.flush()
                created_count += 1

                print(f"[PASS] Created user: {new_user.username} (email: {new_user.email}, role: {role_name})")
            else:
                print(f"[INFO] User already exists: {user_data['username']}")

        db.commit()

        print("\n" + "="*80)
        print("APOLLO TENANT SETUP COMPLETE")
        print("="*80)
        print(f"\nTenant: Apollo Medical Center (ID: apollo, DB ID: {apollo_tenant.id})")
        print(f"Users Created: {created_count}")
        print(f"Password: {DEFAULT_PASSWORD}")
        print("\nApollo Tenant Users:")
        print("-" * 60)
        print("Username: apollo_admin      | Role: admin        | Email: admin@apollo.com")
        print("Username: apollo_doctor     | Role: doctor       | Email: doctor@apollo.com")
        print("Username: apollo_radiologist| Role: radiologist  | Email: radiologist@apollo.com")
        print("Username: apollo_tech       | Role: technician   | Email: tech@apollo.com")
        print("-" * 60)
        print("\nDefault Tenant Users (for comparison):")
        print("-" * 60)
        print("Username: admin             | Role: admin        | Email: admin@iscs.com")
        print("Username: doctor1           | Role: doctor       | Email: doctor@iscs.com")
        print("Username: radiologist1      | Role: radiologist  | Email: radiologist@iscs.com")
        print("Username: technician1       | Role: technician   | Email: technician@iscs.com")
        print("-" * 60)
        print("\n[SUCCESS] Ready for multi-tenancy testing!")
        print("="*80 + "\n")

        return True

    except Exception as e:
        print(f"\n[ERROR] Failed to create Apollo tenant: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = create_apollo_tenant()
    sys.exit(0 if success else 1)
