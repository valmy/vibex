"""
Technical Analysis Service for calculating technical indicators.

Main service class that orchestrates indicator calculations.
"""

import logging
from typing import List, Tuple

import numpy as np

from ...models.market_data import MarketData
from . import indicators
from .exceptions import InvalidCandleDataError, InsufficientDataError
from .schemas import TechnicalIndicators

logger = logging.getLogger(__name__)


class TechnicalAnalysisService:
    """Service for calculating technical analysis indicators."""

    MIN_CANDLES = 50

    def __init__(self):
        """Initialize the Technical Analysis Service."""
        logger.info("TechnicalAnalysisService initialized")

    def calculate_all_indicators(
        self, candles: List[MarketData]
    ) -> TechnicalIndicators:
        """
        Calculate all technical indicators from a list of candles.

        Args:
            candles: List of MarketData objects ordered from oldest to newest.
                    Requires at least 50 candles for accurate calculations.

        Returns:
            TechnicalIndicators object containing all calculated indicator values.

        Raises:
            InsufficientDataError: If fewer than 50 candles provided.
            InvalidCandleDataError: If candle data is invalid or incomplete.
            CalculationError: If indicator calculation fails.
        """
        # Validate input
        self._validate_candles(candles)

        # Prepare numpy arrays
        close_prices, high_prices, low_prices, volume = self._prepare_arrays(candles)

        logger.debug(f"Calculating indicators for {len(candles)} candles")

        # Calculate all indicators
        ema = indicators.calculate_ema(close_prices)
        macd = indicators.calculate_macd(close_prices)
        rsi = indicators.calculate_rsi(close_prices)
        bollinger_bands = indicators.calculate_bollinger_bands(close_prices)
        atr = indicators.calculate_atr(high_prices, low_prices, close_prices)

        # Assemble and return structured response
        result = TechnicalIndicators(
            ema=ema,
            macd=macd,
            rsi=rsi,
            bollinger_bands=bollinger_bands,
            atr=atr,
            candle_count=len(candles),
        )

        logger.info(f"Indicators calculated successfully for {len(candles)} candles")
        return result

    def _validate_candles(self, candles: List[MarketData]) -> None:
        """
        Validate candle data.

        Args:
            candles: List of MarketData objects to validate

        Raises:
            InsufficientDataError: If fewer than MIN_CANDLES provided
            InvalidCandleDataError: If any candle has invalid data
        """
        if len(candles) < self.MIN_CANDLES:
            raise InsufficientDataError(len(candles), self.MIN_CANDLES)

        for i, candle in enumerate(candles):
            # Check all OHLC fields are present
            if not all([candle.open, candle.high, candle.low, candle.close]):
                raise InvalidCandleDataError("Missing OHLC data", candle_index=i)

            # Check high >= low
            if candle.high < candle.low:
                raise InvalidCandleDataError(
                    f"High ({candle.high}) < Low ({candle.low})", candle_index=i
                )

            # Check for negative prices
            if any(p < 0 for p in [candle.open, candle.high, candle.low, candle.close]):
                raise InvalidCandleDataError("Negative price values", candle_index=i)

            # Check for negative volume
            if candle.volume < 0:
                raise InvalidCandleDataError("Negative volume", candle_index=i)

    def _prepare_arrays(
        self, candles: List[MarketData]
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Convert candles to numpy arrays for calculations.

        Args:
            candles: List of MarketData objects

        Returns:
            Tuple of (close_prices, high_prices, low_prices, volume) as numpy arrays
        """
        close_prices = np.array([c.close for c in candles], dtype=np.float64)
        high_prices = np.array([c.high for c in candles], dtype=np.float64)
        low_prices = np.array([c.low for c in candles], dtype=np.float64)
        volume = np.array([c.volume for c in candles], dtype=np.float64)

        logger.debug(
            f"Arrays prepared: close={len(close_prices)}, high={len(high_prices)}, "
            f"low={len(low_prices)}, volume={len(volume)}"
        )

        return close_prices, high_prices, low_prices, volume

