"""
Audit trail system for tracking all operations
"""
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
import json

from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from api.database.session import get_db
from api.utils.logging_config import logger, get_correlation_id

Base = declarative_base()


class AuditAction(str, Enum):
    """Audit action types"""
    # Authentication
    LOGIN = "auth.login"
    LOGOUT = "auth.logout"
    LOGIN_FAILED = "auth.login_failed"
    TOKEN_REFRESH = "auth.token_refresh"

    # User Management
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    PASSWORD_CHANGED = "user.password_changed"

    # Predictions
    PREDICTION_CREATED = "prediction.created"
    PREDICTION_VIEWED = "prediction.viewed"
    PREDICTION_DELETED = "prediction.deleted"
    BATCH_PREDICTION = "prediction.batch"

    # Cache Operations
    CACHE_HIT = "cache.hit"
    CACHE_MISS = "cache.miss"
    CACHE_INVALIDATED = "cache.invalidated"

    # Rate Limiting
    RATE_LIMIT_EXCEEDED = "rate_limit.exceeded"

    # Model Operations
    MODEL_LOADED = "model.loaded"
    MODEL_UPDATED = "model.updated"

    # Data Access
    DATA_EXPORTED = "data.exported"
    DATA_IMPORTED = "data.imported"

    # System
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_ERROR = "system.error"

    # Tenant Operations
    TENANT_CREATED = "tenant.created"
    TENANT_UPDATED = "tenant.updated"
    TENANT_DELETED = "tenant.deleted"


class AuditLog(Base):
    """
    Audit log database model
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    # Who
    user_id = Column(String, nullable=True, index=True)
    tenant_id = Column(String, nullable=True, index=True)

    # What
    action = Column(String, nullable=False, index=True)
    resource_type = Column(String, nullable=True)
    resource_id = Column(String, nullable=True, index=True)

    # When
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Where
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)

    # How
    correlation_id = Column(String, nullable=True, index=True)

    # Details
    details = Column(JSON, nullable=True)
    changes = Column(JSON, nullable=True)  # Before/after for updates

    # Result
    success = Column(String, nullable=False, default="true")  # "true", "false"
    error_message = Column(Text, nullable=True)

    # Metadata
    metadata = Column(JSON, nullable=True)

    # Indexes for common queries
    __table_args__ = (
        Index('idx_user_action_timestamp', 'user_id', 'action', 'timestamp'),
        Index('idx_tenant_timestamp', 'tenant_id', 'timestamp'),
        Index('idx_correlation_id', 'correlation_id'),
    )


class AuditService:
    """
    Service for creating and querying audit logs
    """

    @staticmethod
    async def log(
        action: AuditAction,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        changes: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Create an audit log entry

        Args:
            action: The action that was performed
            user_id: ID of the user who performed the action
            tenant_id: ID of the tenant
            resource_type: Type of resource affected (e.g., 'prediction', 'user')
            resource_id: ID of the affected resource
            ip_address: IP address of the client
            user_agent: User agent string
            details: Additional details about the action
            changes: Before/after values for update operations
            success: Whether the action succeeded
            error_message: Error message if action failed
            metadata: Additional metadata
        """
        try:
            # Get correlation ID from context
            correlation_id = get_correlation_id()

            # Create audit log entry
            audit_entry = AuditLog(
                user_id=user_id,
                tenant_id=tenant_id,
                action=action.value,
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=ip_address,
                user_agent=user_agent,
                correlation_id=correlation_id,
                details=details,
                changes=changes,
                success="true" if success else "false",
                error_message=error_message,
                metadata=metadata,
                timestamp=datetime.utcnow()
            )

            # Save to database (async)
            async for db in get_db():
                db.add(audit_entry)
                await db.commit()
                await db.refresh(audit_entry)

            # Also log to structured logger
            logger.info(
                f"Audit: {action.value}",
                action=action.value,
                user_id=user_id,
                tenant_id=tenant_id,
                resource_type=resource_type,
                resource_id=resource_id,
                success=success,
                correlation_id=correlation_id
            )

            return audit_entry

        except Exception as e:
            # Log error but don't fail the request
            logger.error(
                f"Failed to create audit log: {str(e)}",
                action=action.value,
                exc_info=True
            )

    @staticmethod
    def log_prediction(
        user_id: Optional[str],
        tenant_id: Optional[str],
        image_hash: str,
        result: str,
        confidence: float,
        risk_level: str,
        ip_address: Optional[str] = None,
        cached: bool = False
    ):
        """Log a prediction event"""
        return AuditService.log(
            action=AuditAction.PREDICTION_CREATED,
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type="prediction",
            resource_id=image_hash,
            ip_address=ip_address,
            details={
                "result": result,
                "confidence": confidence,
                "risk_level": risk_level,
                "cached": cached
            }
        )

    @staticmethod
    def log_authentication(
        action: AuditAction,
        user_id: Optional[str],
        ip_address: Optional[str],
        user_agent: Optional[str],
        success: bool,
        error_message: Optional[str] = None
    ):
        """Log authentication events"""
        return AuditService.log(
            action=action,
            user_id=user_id,
            resource_type="auth",
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message
        )

    @staticmethod
    def log_data_access(
        action: AuditAction,
        user_id: str,
        tenant_id: str,
        resource_type: str,
        resource_id: str,
        operation: str,
        ip_address: Optional[str] = None
    ):
        """Log data access events"""
        return AuditService.log(
            action=action,
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details={"operation": operation},
            ip_address=ip_address
        )

    @staticmethod
    async def get_user_audit_trail(
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ):
        """Get audit trail for a specific user"""
        async for db in get_db():
            logs = await db.query(AuditLog)\
                .filter(AuditLog.user_id == user_id)\
                .order_by(AuditLog.timestamp.desc())\
                .limit(limit)\
                .offset(offset)\
                .all()
            return logs

    @staticmethod
    async def get_resource_audit_trail(
        resource_type: str,
        resource_id: str,
        limit: int = 100
    ):
        """Get audit trail for a specific resource"""
        async for db in get_db():
            logs = await db.query(AuditLog)\
                .filter(
                    AuditLog.resource_type == resource_type,
                    AuditLog.resource_id == resource_id
                )\
                .order_by(AuditLog.timestamp.desc())\
                .limit(limit)\
                .all()
            return logs

    @staticmethod
    async def get_tenant_audit_trail(
        tenant_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000
    ):
        """Get audit trail for a tenant"""
        async for db in get_db():
            query = db.query(AuditLog).filter(AuditLog.tenant_id == tenant_id)

            if start_date:
                query = query.filter(AuditLog.timestamp >= start_date)
            if end_date:
                query = query.filter(AuditLog.timestamp <= end_date)

            logs = await query.order_by(AuditLog.timestamp.desc())\
                .limit(limit)\
                .all()
            return logs

    @staticmethod
    async def search_audit_logs(
        action: Optional[AuditAction] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        success_only: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ):
        """Search audit logs with filters"""
        async for db in get_db():
            query = db.query(AuditLog)

            if action:
                query = query.filter(AuditLog.action == action.value)
            if user_id:
                query = query.filter(AuditLog.user_id == user_id)
            if tenant_id:
                query = query.filter(AuditLog.tenant_id == tenant_id)
            if resource_type:
                query = query.filter(AuditLog.resource_type == resource_type)
            if start_date:
                query = query.filter(AuditLog.timestamp >= start_date)
            if end_date:
                query = query.filter(AuditLog.timestamp <= end_date)
            if success_only is not None:
                query = query.filter(
                    AuditLog.success == ("true" if success_only else "false")
                )

            logs = await query.order_by(AuditLog.timestamp.desc())\
                .limit(limit)\
                .offset(offset)\
                .all()
            return logs


# Audit decorator for automatic audit logging
def audit(
    action: AuditAction,
    resource_type: Optional[str] = None,
    get_resource_id: Optional[callable] = None
):
    """
    Decorator to automatically audit function calls

    Args:
        action: The audit action to log
        resource_type: Type of resource being accessed
        get_resource_id: Function to extract resource ID from function args
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract user context
            user_id = None
            tenant_id = None

            # Try to get from request if available
            if 'request' in kwargs:
                request = kwargs['request']
                if hasattr(request.state, 'user'):
                    user_id = str(request.state.user.id)
                if hasattr(request.state, 'tenant_id'):
                    tenant_id = str(request.state.tenant_id)

            # Get resource ID if extractor provided
            resource_id = None
            if get_resource_id:
                resource_id = get_resource_id(*args, **kwargs)

            try:
                # Execute function
                result = await func(*args, **kwargs)

                # Log successful action
                await AuditService.log(
                    action=action,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    success=True
                )

                return result

            except Exception as e:
                # Log failed action
                await AuditService.log(
                    action=action,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    success=False,
                    error_message=str(e)
                )
                raise

        return wrapper
    return decorator
