"""
Technical indicator calculation functions.

Provides pure functions for calculating technical indicators using TA-Lib and NumPy.
"""

import logging
from typing import List, Optional

import numpy as np
import talib

from .exceptions import CalculationError, InsufficientDataError
from .schemas import ATROutput, BollingerBandsOutput, EMAOutput, MACDOutput, RSIOutput

logger = logging.getLogger(__name__)


def _get_last_n_values(arr: np.ndarray, n: int = 10) -> List[Optional[float]]:
    """Get the last N values from a numpy array, converting nan to None."""
    values = arr[-n:]
    return [float(v) if not np.isnan(v) else None for v in values]


def _validate_array_length(arr: np.ndarray, min_length: int = 50) -> None:
    """
    Validate that array has minimum required length.

    Args:
        arr: NumPy array to validate
        min_length: Minimum required length (default: 50)

    Raises:
        InsufficientDataError: If array length is less than minimum
    """
    if len(arr) < min_length:
        raise InsufficientDataError(len(arr), min_length)


def _handle_calculation_error(indicator_name: str, error: Exception) -> CalculationError:
    """
    Convert calculation errors to service exceptions.

    Args:
        indicator_name: Name of the indicator that failed
        error: The original exception

    Returns:
        CalculationError with context
    """
    return CalculationError(indicator_name, error)


def calculate_ema(close_prices: np.ndarray) -> EMAOutput:
    """
    Calculate Exponential Moving Average (EMA).

    Args:
        close_prices: NumPy array of close prices

    Returns:
        EMAOutput with calculated EMA value series

    Raises:
        InsufficientDataError: If insufficient data
        CalculationError: If calculation fails
    """
    try:
        _validate_array_length(close_prices)
        ema_values = talib.EMA(close_prices, timeperiod=12)
        ema_series = _get_last_n_values(ema_values)
        logger.debug(f"EMA series calculated. Last value: {ema_series[-1]}")
        return EMAOutput(ema=ema_series, period=12)
    except InsufficientDataError:
        raise
    except Exception as e:
        logger.error(f"EMA calculation failed: {e}")
        raise _handle_calculation_error("EMA", e)


def calculate_macd(close_prices: np.ndarray) -> MACDOutput:
    """
    Calculate Moving Average Convergence Divergence (MACD).

    Args:
        close_prices: NumPy array of close prices

    Returns:
        MACDOutput with MACD, signal, and histogram value series

    Raises:
        InsufficientDataError: If insufficient data
        CalculationError: If calculation fails
    """
    try:
        _validate_array_length(close_prices)
        macd_values, signal_values, histogram_values = talib.MACD(close_prices)

        macd_series = _get_last_n_values(macd_values)
        signal_series = _get_last_n_values(signal_values)
        histogram_series = _get_last_n_values(histogram_values)

        logger.debug(f"MACD series calculated. Last macd: {macd_series[-1]}")
        return MACDOutput(macd=macd_series, signal=signal_series, histogram=histogram_series)
    except InsufficientDataError:
        raise
    except Exception as e:
        logger.error(f"MACD calculation failed: {e}")
        raise _handle_calculation_error("MACD", e)


def calculate_rsi(close_prices: np.ndarray) -> RSIOutput:
    """
    Calculate Relative Strength Index (RSI).

    Args:
        close_prices: NumPy array of close prices

    Returns:
        RSIOutput with RSI value series (0-100)

    Raises:
        InsufficientDataError: If insufficient data
        CalculationError: If calculation fails
    """
    try:
        _validate_array_length(close_prices)
        rsi_values = talib.RSI(close_prices, timeperiod=14)
        rsi_series = _get_last_n_values(rsi_values)
        logger.debug(f"RSI series calculated. Last value: {rsi_series[-1]}")
        return RSIOutput(rsi=rsi_series, period=14)
    except InsufficientDataError:
        raise
    except Exception as e:
        logger.error(f"RSI calculation failed: {e}")
        raise _handle_calculation_error("RSI", e)


def calculate_bollinger_bands(close_prices: np.ndarray) -> BollingerBandsOutput:
    """
    Calculate Bollinger Bands.

    Args:
        close_prices: NumPy array of close prices

    Returns:
        BollingerBandsOutput with upper, middle, lower band value series

    Raises:
        InsufficientDataError: If insufficient data
        CalculationError: If calculation fails
    """
    try:
        _validate_array_length(close_prices)
        upper_values, middle_values, lower_values = talib.BBANDS(
            close_prices, timeperiod=20, nbdevup=2, nbdevdn=2
        )

        upper_series = _get_last_n_values(upper_values)
        middle_series = _get_last_n_values(middle_values)
        lower_series = _get_last_n_values(lower_values)

        logger.debug(f"Bollinger Bands series calculated. Last middle: {middle_series[-1]}")
        return BollingerBandsOutput(
            upper=upper_series, middle=middle_series, lower=lower_series, period=20, std_dev=2.0
        )
    except InsufficientDataError:
        raise
    except Exception as e:
        logger.error(f"Bollinger Bands calculation failed: {e}")
        raise _handle_calculation_error("Bollinger Bands", e)


def calculate_atr(
    high_prices: np.ndarray, low_prices: np.ndarray, close_prices: np.ndarray
) -> ATROutput:
    """
    Calculate Average True Range (ATR).

    Args:
        high_prices: NumPy array of high prices
        low_prices: NumPy array of low prices
        close_prices: NumPy array of close prices

    Returns:
        ATROutput with ATR value series

    Raises:
        InsufficientDataError: If insufficient data
        CalculationError: If calculation fails
    """
    try:
        _validate_array_length(high_prices)
        atr_values = talib.ATR(high_prices, low_prices, close_prices, timeperiod=14)
        atr_series = _get_last_n_values(atr_values)
        logger.debug(f"ATR series calculated. Last value: {atr_series[-1]}")
        return ATROutput(atr=atr_series, period=14)
    except InsufficientDataError:
        raise
    except Exception as e:
        logger.error(f"ATR calculation failed: {e}")
        raise _handle_calculation_error("ATR", e)
