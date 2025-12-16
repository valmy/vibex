"""
Custom exceptions for the Technical Analysis Service.

Provides specific exception types for different error scenarios.
"""


class TechnicalAnalysisException(Exception):
    """Base exception for technical analysis service."""

    pass


class InsufficientDataError(TechnicalAnalysisException):
    """Raised when insufficient candle data is provided."""

    def __init__(self, provided: int, required: int = 50):
        """
        Initialize InsufficientDataError.

        Args:
            provided: Number of candles provided
            required: Minimum number of candles required (default: 50)
        """
        self.provided = provided
        self.required = required
        super().__init__(f"Insufficient candle data: {provided} provided, {required} required")


class InvalidCandleDataError(TechnicalAnalysisException):
    """Raised when candle data is invalid or incomplete."""

    def __init__(self, message: str, candle_index: Optional[int] = None):
        """
        Initialize InvalidCandleDataError.

        Args:
            message: Description of the invalid data
            candle_index: Index of the invalid candle (optional)
        """
        self.candle_index = candle_index
        if candle_index is not None:
            full_message = f"Invalid candle data at index {candle_index}: {message}"
        else:
            full_message = f"Invalid candle data: {message}"
        super().__init__(full_message)


class CalculationError(TechnicalAnalysisException):
    """Raised when indicator calculation fails."""

    def __init__(self, indicator_name: str, original_error: Exception):
        """
        Initialize CalculationError.

        Args:
            indicator_name: Name of the indicator that failed
            original_error: The original exception that caused the failure
        """
        self.indicator_name = indicator_name
        self.original_error = original_error
        super().__init__(f"Failed to calculate {indicator_name}: {str(original_error)}")
