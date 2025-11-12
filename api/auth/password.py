"""
Password hashing and verification utilities
Uses bcrypt for secure password hashing
"""
from passlib.context import CryptContext

# Configure password hashing context
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # Higher rounds = more secure but slower
)

def hash_password(password: str) -> str:
    """
    Hash a plain text password using bcrypt

    Args:
        password: Plain text password

    Returns:
        Hashed password string
    """
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hashed password

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to check against

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)

def needs_rehash(hashed_password: str) -> bool:
    """
    Check if a hashed password needs to be rehashed
    (e.g., if bcrypt rounds have been increased)

    Args:
        hashed_password: Hashed password to check

    Returns:
        True if password needs rehashing
    """
    return pwd_context.needs_update(hashed_password)
