"""
Pydantic schemas for Technical Analysis Service.
"""

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field


class TATechnicalIndicators(BaseModel):
    """Container for all calculated technical indicators."""

    ema_20: List[Optional[float]] = Field([], description="EMA 20 value series")
    ema_50: List[Optional[float]] = Field([], description="EMA 50 value series")
    macd: List[Optional[float]] = Field([], description="MACD line value series")
    macd_signal: List[Optional[float]] = Field([], description="Signal line value series")
    rsi: List[Optional[float]] = Field([], description="RSI value series (0-100)")
    bb_upper: List[Optional[float]] = Field([], description="Upper band value series")
    bb_middle: List[Optional[float]] = Field([], description="Middle band (SMA) value series")
    bb_lower: List[Optional[float]] = Field([], description="Lower band value series")
    atr: List[Optional[float]] = Field([], description="ATR value series")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Calculation timestamp"
    )
    candle_count: int = Field(description="Number of candles used for calculation")
    series_length: int = Field(description="Number of data points in the indicator series")
