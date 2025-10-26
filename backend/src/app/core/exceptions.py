"""
Custom exception classes for the AI Trading Agent application.

Provides domain-specific exceptions for error handling.
"""

from fastapi import HTTPException, status


class TradingAgentException(Exception):
    """Base exception for the trading agent."""

    def __init__(self, message: str, code: str = "INTERNAL_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class ResourceNotFoundError(TradingAgentException):
    """Raised when a resource is not found."""

    def __init__(self, resource: str, resource_id: int | str):
        message = f"{resource} with id {resource_id} not found"
        super().__init__(message, "RESOURCE_NOT_FOUND")


class ValidationError(TradingAgentException):
    """Raised when validation fails."""

    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR")


class InsufficientFundsError(TradingAgentException):
    """Raised when there are insufficient funds."""

    def __init__(self, available: float, required: float):
        message = f"Insufficient funds. Available: {available}, Required: {required}"
        super().__init__(message, "INSUFFICIENT_FUNDS")


class PositionError(TradingAgentException):
    """Raised when there's an issue with a position."""

    def __init__(self, message: str):
        super().__init__(message, "POSITION_ERROR")


class OrderError(TradingAgentException):
    """Raised when there's an issue with an order."""

    def __init__(self, message: str):
        super().__init__(message, "ORDER_ERROR")


class DatabaseError(TradingAgentException):
    """Raised when there's a database error."""

    def __init__(self, message: str):
        super().__init__(message, "DATABASE_ERROR")


class APIError(TradingAgentException):
    """Raised when there's an API error."""

    def __init__(self, message: str, status_code: int = 500):
        self.status_code = status_code
        super().__init__(message, "API_ERROR")


class ConfigurationError(TradingAgentException):
    """Raised when there's a configuration error."""

    def __init__(self, message: str):
        super().__init__(message, "CONFIGURATION_ERROR")


# HTTP Exception converters
def to_http_exception(exc: TradingAgentException) -> HTTPException:
    """Convert TradingAgentException to HTTPException."""
    status_code_map = {
        "RESOURCE_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "VALIDATION_ERROR": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "INSUFFICIENT_FUNDS": status.HTTP_400_BAD_REQUEST,
        "POSITION_ERROR": status.HTTP_400_BAD_REQUEST,
        "ORDER_ERROR": status.HTTP_400_BAD_REQUEST,
        "DATABASE_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
        "API_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
        "CONFIGURATION_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
        "INTERNAL_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
    }

    status_code = status_code_map.get(exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    return HTTPException(
        status_code=status_code,
        detail={
            "error": exc.code,
            "message": exc.message,
        },
    )
