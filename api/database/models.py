"""
SQLAlchemy database models for Glaucoma Detection System
Includes: Multi-tenancy, RBAC, Patient records, Predictions, Audit logs
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Float, Text,
    ForeignKey, Index, UniqueConstraint, CheckConstraint, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from .session import Base

# ============================================================================
# Utility Functions
# ============================================================================

def generate_uuid() -> str:
    """Generate a UUID string"""
    return str(uuid.uuid4())

# ============================================================================
# Tenant Model (Multi-tenancy)
# ============================================================================

class Tenant(Base):
    """
    Tenant model for multi-tenancy isolation
    Each tenant represents a hospital, clinic, or organization
    """
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(50), unique=True, nullable=False, index=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    domain = Column(String(255), unique=True, nullable=True)

    # Subscription details
    subscription_tier = Column(String(50), default="free")  # free, basic, premium, enterprise
    is_active = Column(Boolean, default=True, nullable=False)
    max_users = Column(Integer, default=5)
    max_predictions_per_month = Column(Integer, default=100)

    # Metadata
    settings = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    patients = relationship("Patient", back_populates="tenant", cascade="all, delete-orphan")
    predictions = relationship("Prediction", back_populates="tenant", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="tenant", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Tenant(id={self.id}, name={self.name}, tenant_id={self.tenant_id})>"

# ============================================================================
# User Model (Authentication)
# ============================================================================

class User(Base):
    """
    User model for authentication and authorization
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(50), unique=True, nullable=False, index=True, default=generate_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Authentication
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)

    # OAuth
    oauth_provider = Column(String(50), nullable=True)  # google, github, azure, etc.
    oauth_id = Column(String(255), nullable=True)

    # Profile
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)

    # Security
    failed_login_attempts = Column(Integer, default=0)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    password_changed_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    settings = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", back_populates="users")
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="SET NULL"), nullable=True)
    role = relationship("Role", back_populates="users")
    predictions = relationship("Prediction", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_user_tenant_email', 'tenant_id', 'email'),
        Index('idx_user_oauth', 'oauth_provider', 'oauth_id'),
    )

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, tenant_id={self.tenant_id})>"

# ============================================================================
# Role Model (RBAC)
# ============================================================================

class Role(Base):
    """
    Role model for Role-Based Access Control (RBAC)
    """
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Built-in roles: admin, doctor, radiologist, technician, viewer
    is_system_role = Column(Boolean, default=False, nullable=False)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    users = relationship("User", back_populates="role")
    role_permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Role(id={self.id}, name={self.name})>"

# ============================================================================
# Permission Model (RBAC)
# ============================================================================

class Permission(Base):
    """
    Permission model for fine-grained access control
    """
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    resource = Column(String(100), nullable=False)  # patient, prediction, user, etc.
    action = Column(String(50), nullable=False)  # create, read, update, delete
    description = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    role_permissions = relationship("RolePermission", back_populates="permission", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_permission_resource_action', 'resource', 'action'),
    )

    def __repr__(self):
        return f"<Permission(id={self.id}, name={self.name})>"

# ============================================================================
# RolePermission Model (Many-to-Many)
# ============================================================================

class RolePermission(Base):
    """
    Junction table for Role-Permission many-to-many relationship
    """
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    permission_id = Column(Integer, ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    role = relationship("Role", back_populates="role_permissions")
    permission = relationship("Permission", back_populates="role_permissions")

    __table_args__ = (
        UniqueConstraint('role_id', 'permission_id', name='uq_role_permission'),
        Index('idx_role_permission', 'role_id', 'permission_id'),
    )

    def __repr__(self):
        return f"<RolePermission(role_id={self.role_id}, permission_id={self.permission_id})>"

# ============================================================================
# Patient Model
# ============================================================================

class Patient(Base):
    """
    Patient model for storing patient information
    """
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String(50), unique=True, nullable=False, index=True, default=generate_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Demographics
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(DateTime, nullable=True)
    gender = Column(String(20), nullable=True)  # male, female, other

    # Contact
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)

    # Medical Record Number (unique per tenant)
    mrn = Column(String(50), nullable=False, index=True)

    # Clinical information
    medical_history = Column(JSON, default=dict)
    risk_factors = Column(JSON, default=dict)

    # Metadata
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", back_populates="patients")
    predictions = relationship("Prediction", back_populates="patient", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('tenant_id', 'mrn', name='uq_tenant_mrn'),
        Index('idx_patient_tenant_mrn', 'tenant_id', 'mrn'),
        Index('idx_patient_name', 'first_name', 'last_name'),
    )

    def __repr__(self):
        return f"<Patient(id={self.id}, patient_id={self.patient_id}, mrn={self.mrn})>"

# ============================================================================
# Prediction Model
# ============================================================================

class Prediction(Base):
    """
    Prediction model for storing glaucoma detection results
    """
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    prediction_id = Column(String(50), unique=True, nullable=False, index=True, default=generate_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Prediction results
    prediction = Column(Integer, nullable=False)  # 0 = normal, 1 = glaucoma
    label = Column(String(50), nullable=False)  # "normal" or "glaucoma"
    probability = Column(Float, nullable=False)  # Probability of glaucoma
    confidence = Column(Float, nullable=False)  # Model confidence score
    risk_level = Column(String(50), nullable=False)  # low, medium, high, critical

    # Image metadata
    image_filename = Column(String(255), nullable=True)
    image_size = Column(Integer, nullable=True)  # Size in bytes
    image_width = Column(Integer, nullable=True)
    image_height = Column(Integer, nullable=True)
    image_hash = Column(String(64), nullable=True, index=True)  # SHA-256 hash for deduplication

    # Processing metadata
    model_version = Column(String(50), nullable=True)
    processing_time_ms = Column(Float, nullable=True)

    # Clinical review
    is_reviewed = Column(Boolean, default=False, nullable=False)
    reviewed_by_user_id = Column(Integer, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    clinical_notes = Column(Text, nullable=True)

    # Recommendations
    recommendations = Column(JSON, default=list)

    # A/B Testing
    ab_test_variant = Column(String(50), nullable=True, index=True)  # A, B, C, etc.

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="predictions")
    patient = relationship("Patient", back_populates="predictions")
    user = relationship("User", back_populates="predictions")

    __table_args__ = (
        Index('idx_prediction_tenant_patient', 'tenant_id', 'patient_id'),
        Index('idx_prediction_created', 'created_at'),
        Index('idx_prediction_risk', 'risk_level'),
        CheckConstraint('prediction IN (0, 1)', name='check_prediction_value'),
        CheckConstraint('probability >= 0 AND probability <= 1', name='check_probability_range'),
    )

    def __repr__(self):
        return f"<Prediction(id={self.id}, prediction_id={self.prediction_id}, label={self.label})>"

# ============================================================================
# AuditLog Model
# ============================================================================

class AuditLog(Base):
    """
    Audit log model for tracking all system operations
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    log_id = Column(String(50), unique=True, nullable=False, index=True, default=generate_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Audit details
    action = Column(String(100), nullable=False, index=True)  # login, create_prediction, update_patient, etc.
    resource = Column(String(100), nullable=False, index=True)  # user, patient, prediction, etc.
    resource_id = Column(String(50), nullable=True, index=True)

    # Request details
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    request_id = Column(String(50), nullable=True, index=True)  # Correlation ID

    # Result
    status = Column(String(50), nullable=False)  # success, failure, error
    status_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    # Additional data
    audit_metadata = Column(JSON, default=dict)

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="audit_logs")
    user = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index('idx_audit_tenant_user', 'tenant_id', 'user_id'),
        Index('idx_audit_action', 'action'),
        Index('idx_audit_resource', 'resource', 'resource_id'),
        Index('idx_audit_created', 'created_at'),
    )

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action}, resource={self.resource})>"
