"""
Technical indicator calculation functions.

Provides pure functions for calculating technical indicators using TA-Lib and NumPy.
"""

import logging
from typing import Tuple

import numpy as np
import talib

from .exceptions import CalculationError, InsufficientDataError
from .schemas import (
    ATROutput,
    BollingerBandsOutput,
    EMAOutput,
    MACDOutput,
    RSIOutput,
)

logger = logging.getLogger(__name__)


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


def _handle_calculation_error(
    indicator_name: str, error: Exception
) -> CalculationError:
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
        EMAOutput with calculated EMA value

    Raises:
        InsufficientDataError: If insufficient data
        CalculationError: If calculation fails
    """
    try:
        _validate_array_length(close_prices)
        ema_values = talib.EMA(close_prices, timeperiod=12)
        ema = float(ema_values[-1]) if not np.isnan(ema_values[-1]) else None
        logger.debug(f"EMA calculated: {ema}")
        return EMAOutput(ema=ema, period=12)
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
        MACDOutput with MACD, signal, and histogram values

    Raises:
        InsufficientDataError: If insufficient data
        CalculationError: If calculation fails
    """
    try:
        _validate_array_length(close_prices)
        macd_values, signal_values, histogram_values = talib.MACD(close_prices)
        
        macd = float(macd_values[-1]) if not np.isnan(macd_values[-1]) else None
        signal = float(signal_values[-1]) if not np.isnan(signal_values[-1]) else None
        histogram = float(histogram_values[-1]) if not np.isnan(histogram_values[-1]) else None
        
        logger.debug(f"MACD calculated: macd={macd}, signal={signal}, histogram={histogram}")
        return MACDOutput(macd=macd, signal=signal, histogram=histogram)
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
        RSIOutput with RSI value (0-100)

    Raises:
        InsufficientDataError: If insufficient data
        CalculationError: If calculation fails
    """
    try:
        _validate_array_length(close_prices)
        rsi_values = talib.RSI(close_prices, timeperiod=14)
        rsi = float(rsi_values[-1]) if not np.isnan(rsi_values[-1]) else None
        logger.debug(f"RSI calculated: {rsi}")
        return RSIOutput(rsi=rsi, period=14)
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
        BollingerBandsOutput with upper, middle, lower band values

    Raises:
        InsufficientDataError: If insufficient data
        CalculationError: If calculation fails
    """
    try:
        _validate_array_length(close_prices)
        upper_values, middle_values, lower_values = talib.BBANDS(
            close_prices, timeperiod=20, nbdevup=2, nbdevdn=2
        )
        
        upper = float(upper_values[-1]) if not np.isnan(upper_values[-1]) else None
        middle = float(middle_values[-1]) if not np.isnan(middle_values[-1]) else None
        lower = float(lower_values[-1]) if not np.isnan(lower_values[-1]) else None
        
        logger.debug(f"Bollinger Bands calculated: upper={upper}, middle={middle}, lower={lower}")
        return BollingerBandsOutput(upper=upper, middle=middle, lower=lower, period=20, std_dev=2.0)
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
        ATROutput with ATR value

    Raises:
        InsufficientDataError: If insufficient data
        CalculationError: If calculation fails
    """
    try:
        _validate_array_length(high_prices)
        atr_values = talib.ATR(high_prices, low_prices, close_prices, timeperiod=14)
        atr = float(atr_values[-1]) if not np.isnan(atr_values[-1]) else None
        logger.debug(f"ATR calculated: {atr}")
        return ATROutput(atr=atr, period=14)
    except InsufficientDataError:
        raise
    except Exception as e:
        logger.error(f"ATR calculation failed: {e}")
        raise _handle_calculation_error("ATR", e)

