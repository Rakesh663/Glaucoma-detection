"""
Structured JSON logging with correlation IDs
"""
import logging
import json
import sys
import time
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from contextvars import ContextVar
from pythonjsonlogger import jsonlogger


# Context variable for correlation ID (thread-safe)
correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
tenant_id_var: ContextVar[Optional[str]] = ContextVar('tenant_id', default=None)


class CorrelationIdFilter(logging.Filter):
    """
    Logging filter that adds correlation ID to log records
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Add correlation ID from context
        record.correlation_id = correlation_id_var.get() or "no-correlation-id"
        record.user_id = user_id_var.get() or "anonymous"
        record.tenant_id = tenant_id_var.get() or "no-tenant"
        return True


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """
    Custom JSON formatter with additional fields
    """

    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: dict):
        super().add_fields(log_record, record, message_dict)

        # Add timestamp
        log_record['timestamp'] = datetime.utcnow().isoformat() + 'Z'

        # Add log level
        log_record['level'] = record.levelname

        # Add logger name
        log_record['logger'] = record.name

        # Add correlation ID
        log_record['correlation_id'] = getattr(record, 'correlation_id', 'no-correlation-id')

        # Add user context
        log_record['user_id'] = getattr(record, 'user_id', 'anonymous')
        log_record['tenant_id'] = getattr(record, 'tenant_id', 'no-tenant')

        # Add source location
        log_record['source'] = {
            'file': record.pathname,
            'line': record.lineno,
            'function': record.funcName
        }

        # Add process/thread info
        log_record['process'] = {
            'pid': record.process,
            'thread': record.thread,
            'thread_name': record.threadName
        }


def setup_logging(
    log_level: str = "INFO",
    json_logs: bool = True,
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Setup structured logging configuration

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: Whether to output logs in JSON format
        log_file: Optional file path for log output

    Returns:
        Configured logger
    """
    # Create logger
    logger = logging.getLogger("glaucoma_api")
    logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    logger.handlers.clear()

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))

    # Add correlation ID filter
    correlation_filter = CorrelationIdFilter()
    console_handler.addFilter(correlation_filter)

    # Set formatter
    if json_logs:
        formatter = CustomJsonFormatter(
            fmt='%(timestamp)s %(level)s %(message)s %(correlation_id)s %(user_id)s %(tenant_id)s',
            rename_fields={
                'levelname': 'level',
                'asctime': 'timestamp',
                'name': 'logger'
            }
        )
    else:
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] [%(user_id)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_handler.addFilter(correlation_filter)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


class StructuredLogger:
    """
    Wrapper for structured logging with additional context
    """

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def _log(
        self,
        level: str,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
        exc_info: bool = False
    ):
        """Internal logging method with structured extras"""
        log_extra = extra or {}

        # Add correlation context
        log_extra['correlation_id'] = correlation_id_var.get()
        log_extra['user_id'] = user_id_var.get()
        log_extra['tenant_id'] = tenant_id_var.get()

        # Get the logging method
        log_method = getattr(self.logger, level.lower())

        # Log with extras
        log_method(message, extra=log_extra, exc_info=exc_info)

    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self._log('DEBUG', message, extra=kwargs)

    def info(self, message: str, **kwargs):
        """Log info message"""
        self._log('INFO', message, extra=kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self._log('WARNING', message, extra=kwargs)

    def error(self, message: str, exc_info: bool = False, **kwargs):
        """Log error message"""
        self._log('ERROR', message, extra=kwargs, exc_info=exc_info)

    def critical(self, message: str, exc_info: bool = False, **kwargs):
        """Log critical message"""
        self._log('CRITICAL', message, extra=kwargs, exc_info=exc_info)

    def log_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        **kwargs
    ):
        """Log HTTP request"""
        self.info(
            f"{method} {path} - {status_code}",
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
            **kwargs
        )

    def log_prediction(
        self,
        image_hash: str,
        result: str,
        confidence: float,
        duration_ms: float,
        cached: bool = False,
        **kwargs
    ):
        """Log prediction event"""
        self.info(
            f"Prediction: {result} (confidence: {confidence:.2f})",
            image_hash=image_hash,
            result=result,
            confidence=confidence,
            duration_ms=duration_ms,
            cached=cached,
            **kwargs
        )

    def log_cache_operation(
        self,
        operation: str,
        key: str,
        hit: Optional[bool] = None,
        **kwargs
    ):
        """Log cache operation"""
        message = f"Cache {operation}: {key}"
        if hit is not None:
            message += f" - {'HIT' if hit else 'MISS'}"

        self.debug(
            message,
            cache_operation=operation,
            cache_key=key,
            cache_hit=hit,
            **kwargs
        )

    def log_error_with_context(
        self,
        error: Exception,
        context: Dict[str, Any],
        **kwargs
    ):
        """Log error with full context"""
        self.error(
            f"Error occurred: {str(error)}",
            error_type=type(error).__name__,
            error_message=str(error),
            context=context,
            exc_info=True,
            **kwargs
        )


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """
    Set correlation ID in context

    Args:
        correlation_id: Optional correlation ID (generates UUID if not provided)

    Returns:
        The correlation ID that was set
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())

    correlation_id_var.set(correlation_id)
    return correlation_id


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID from context"""
    return correlation_id_var.get()


def set_user_context(user_id: Optional[str] = None, tenant_id: Optional[str] = None):
    """
    Set user context for logging

    Args:
        user_id: User ID
        tenant_id: Tenant ID
    """
    if user_id:
        user_id_var.set(user_id)
    if tenant_id:
        tenant_id_var.set(tenant_id)


def clear_context():
    """Clear all context variables"""
    correlation_id_var.set(None)
    user_id_var.set(None)
    tenant_id_var.set(None)


# Create default logger instance
default_logger = setup_logging()
logger = StructuredLogger(default_logger)
