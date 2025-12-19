"""
Exception classes for LLM Decision Engine.

Provides structured exception hierarchy for error handling.
"""


class DecisionEngineError(Exception):
    """Base exception for decision engine errors."""

    pass


class LLMAPIError(DecisionEngineError):
    """LLM API communication errors."""

    pass


class ValidationError(DecisionEngineError):
    """Decision validation errors."""

    pass


class ContextBuildingError(DecisionEngineError):
    """Context building errors."""

    pass


class InsufficientDataError(DecisionEngineError):
    """Insufficient data for decision making."""

    pass


class ModelSwitchError(DecisionEngineError):
    """Model switching errors."""

    pass


class CircuitBreakerError(DecisionEngineError):
    """Circuit breaker activation errors."""

    pass


class AuthenticationError(DecisionEngineError):
    """Authentication failures with LLM server."""

    pass
