"""
Pydantic schemas for Technical Analysis Service.

Defines data contracts for indicator outputs and aggregated results.
"""

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class EMAOutput(BaseModel):
    """Exponential Moving Average (EMA) indicator output."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ema": [45000.5, 45001.2, 45002.8, 45003.4, 45004.1, 45005.0, 45005.3, 45005.5],
                "period": 12,
            }
        }
    )

    ema: List[Optional[float]] = Field([], description="EMA value series")
    period: int = Field(default=12, description="EMA period")


class MACDOutput(BaseModel):
    """Moving Average Convergence Divergence (MACD) indicator output."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "macd": [100.5, 101.1, 101.5, 101.0, 100.8, 100.9, 100.7, 100.6],
                "signal": [95.2, 96.0, 96.8, 97.5, 98.1, 98.6, 99.0, 99.3],
                "histogram": [5.3, 5.1, 4.7, 3.5, 2.7, 2.3, 1.7, 1.3],
            }
        }
    )

    macd: List[Optional[float]] = Field([], description="MACD line value series")
    signal: List[Optional[float]] = Field([], description="Signal line value series")
    histogram: List[Optional[float]] = Field([], description="MACD histogram value series")


class RSIOutput(BaseModel):
    """Relative Strength Index (RSI) indicator output."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"rsi": [65.5, 66.2, 66.8, 65.9, 65.2, 64.8, 64.5, 64.2], "period": 14}
        }
    )

    rsi: List[Optional[float]] = Field([], description="RSI value series (0-100)")
    period: int = Field(default=14, description="RSI period")


class BollingerBandsOutput(BaseModel):
    """Bollinger Bands indicator output."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "upper": [46000.0, 46050.0, 46100.0, 46150.0, 46200.0, 46250.0, 46300.0, 46350.0],
                "middle": [45000.0, 45050.0, 45100.0, 45150.0, 45200.0, 45250.0, 45300.0, 45350.0],
                "lower": [44000.0, 44050.0, 44100.0, 44150.0, 44200.0, 44250.0, 44300.0, 44350.0],
                "period": 20,
                "std_dev": 2.0,
            }
        }
    )

    upper: List[Optional[float]] = Field([], description="Upper band value series")
    middle: List[Optional[float]] = Field([], description="Middle band (SMA) value series")
    lower: List[Optional[float]] = Field([], description="Lower band value series")
    period: int = Field(default=20, description="Bollinger Bands period")
    std_dev: float = Field(default=2.0, description="Standard deviations")


class ATROutput(BaseModel):
    """Average True Range (ATR) indicator output."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "atr": [500.0, 501.2, 503.4, 505.1, 504.8, 506.3, 507.0, 508.1],
                "period": 14,
            }
        }
    )

    atr: List[Optional[float]] = Field([], description="ATR value series")
    period: int = Field(default=14, description="ATR period")


class TechnicalIndicators(BaseModel):
    """Container for all calculated technical indicators."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ema": {"ema": [45000.5, 45001.2], "period": 12},
                "macd": {"macd": [100.5, 101.1], "signal": [95.2, 96.0], "histogram": [5.3, 5.1]},
                "rsi": {"rsi": [65.5, 66.2], "period": 14},
                "bollinger_bands": {
                    "upper": [46000.0, 46050.0],
                    "middle": [45000.0, 45050.0],
                    "lower": [44000.0, 44050.0],
                    "period": 20,
                    "std_dev": 2.0,
                },
                "atr": {"atr": [500.0, 501.2], "period": 14},
                "timestamp": "2024-01-01T12:00:00",
                "candle_count": 100,
                "series_length": 10,
            }
        }
    )

    ema: EMAOutput = Field(description="EMA indicator")
    macd: MACDOutput = Field(description="MACD indicator")
    rsi: RSIOutput = Field(description="RSI indicator")
    bollinger_bands: BollingerBandsOutput = Field(description="Bollinger Bands indicator")
    atr: ATROutput = Field(description="ATR indicator")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Calculation timestamp"
    )
    candle_count: int = Field(description="Number of candles used for calculation")
    series_length: int = Field(description="Number of data points in the indicator series")
