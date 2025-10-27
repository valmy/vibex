"""
Configuration-specific exception classes for the AI Trading Agent application.

Provides domain-specific exceptions for configuration validation, reloading, and caching.
"""

from typing import Any, List, Optional

from .exceptions import ConfigurationError


class ConfigValidationError(ConfigurationError):
    """Raised when configuration validation fails."""

    def __init__(self, message: str, errors: Optional[List[str]] = None):
        """
        Initialize ConfigValidationError.

        Args:
            message: Error message
            errors: List of validation error messages
        """
        self.errors = errors or []
        super().__init__(message)
        self.code = "CONFIG_VALIDATION_ERROR"


class MissingRequiredFieldError(ConfigValidationError):
    """Raised when a required configuration field is missing."""

    def __init__(self, field_name: str):
        """
        Initialize MissingRequiredFieldError.

        Args:
            field_name: Name of the missing field
        """
        self.field_name = field_name
        message = f"Required configuration field '{field_name}' is missing"
        super().__init__(message, [message])
        self.code = "MISSING_REQUIRED_FIELD"


class InvalidFieldTypeError(ConfigValidationError):
    """Raised when a configuration field has an invalid type."""

    def __init__(self, field_name: str, expected_type: str, actual_type: str):
        """
        Initialize InvalidFieldTypeError.

        Args:
            field_name: Name of the field
            expected_type: Expected type name
            actual_type: Actual type name
        """
        self.field_name = field_name
        self.expected_type = expected_type
        self.actual_type = actual_type
        message = (
            f"Configuration field '{field_name}' has invalid type. "
            f"Expected {expected_type}, got {actual_type}"
        )
        super().__init__(message, [message])
        self.code = "INVALID_FIELD_TYPE"


class InvalidFieldValueError(ConfigValidationError):
    """Raised when a configuration field has an invalid value."""

    def __init__(self, field_name: str, value: Any, reason: str):
        """
        Initialize InvalidFieldValueError.

        Args:
            field_name: Name of the field
            value: Invalid value
            reason: Reason why the value is invalid
        """
        self.field_name = field_name
        self.value = value
        self.reason = reason
        message = f"Configuration field '{field_name}' has invalid value: {reason}"
        super().__init__(message, [message])
        self.code = "INVALID_FIELD_VALUE"


class ConfigReloadError(ConfigurationError):
    """Raised when configuration reload fails."""

    def __init__(self, message: str, reason: Optional[str] = None):
        """
        Initialize ConfigReloadError.

        Args:
            message: Error message
            reason: Detailed reason for the failure
        """
        self.reason = reason
        super().__init__(message)
        self.code = "CONFIG_RELOAD_ERROR"


class FileWatchError(ConfigReloadError):
    """Raised when file watching fails."""

    def __init__(self, file_path: str, reason: Optional[str] = None):
        """
        Initialize FileWatchError.

        Args:
            file_path: Path to the file being watched
            reason: Detailed reason for the failure
        """
        self.file_path = file_path
        message = f"Failed to watch configuration file '{file_path}'"
        if reason:
            message += f": {reason}"
        super().__init__(message, reason)
        self.code = "FILE_WATCH_ERROR"


class CacheOperationError(ConfigurationError):
    """Raised when a cache operation fails."""

    def __init__(self, operation: str, message: str):
        """
        Initialize CacheOperationError.

        Args:
            operation: Name of the cache operation (get, set, invalidate, etc.)
            message: Error message
        """
        self.operation = operation
        full_message = f"Cache operation '{operation}' failed: {message}"
        super().__init__(full_message)
        self.code = "CACHE_OPERATION_ERROR"

