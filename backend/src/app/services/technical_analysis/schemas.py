"""
Pydantic schemas for Technical Analysis Service.

Defines data contracts for indicator outputs and aggregated results.
"""

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class EMAOutput(BaseModel):
    """Exponential Moving Average (EMA) indicator output."""

    model_config = ConfigDict(json_schema_extra={"example": {"ema": 45000.5, "period": 12}})

    ema: Optional[float] = Field(None, description="EMA value")
    period: int = Field(default=12, description="EMA period")


class MACDOutput(BaseModel):
    """Moving Average Convergence Divergence (MACD) indicator output."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"macd": 100.5, "signal": 95.2, "histogram": 5.3}}
    )

    macd: Optional[float] = Field(None, description="MACD line value")
    signal: Optional[float] = Field(None, description="Signal line value")
    histogram: Optional[float] = Field(None, description="MACD histogram value")


class RSIOutput(BaseModel):
    """Relative Strength Index (RSI) indicator output."""

    model_config = ConfigDict(json_schema_extra={"example": {"rsi": 65.5, "period": 14}})

    rsi: Optional[float] = Field(None, description="RSI value (0-100)")
    period: int = Field(default=14, description="RSI period")


class BollingerBandsOutput(BaseModel):
    """Bollinger Bands indicator output."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "upper": 46000.0,
                "middle": 45000.0,
                "lower": 44000.0,
                "period": 20,
                "std_dev": 2.0,
            }
        }
    )

    upper: Optional[float] = Field(None, description="Upper band value")
    middle: Optional[float] = Field(None, description="Middle band (SMA) value")
    lower: Optional[float] = Field(None, description="Lower band value")
    period: int = Field(default=20, description="Bollinger Bands period")
    std_dev: float = Field(default=2.0, description="Standard deviations")


class ATROutput(BaseModel):
    """Average True Range (ATR) indicator output."""

    model_config = ConfigDict(json_schema_extra={"example": {"atr": 500.0, "period": 14}})

    atr: Optional[float] = Field(None, description="ATR value")
    period: int = Field(default=14, description="ATR period")


class TechnicalIndicators(BaseModel):
    """Container for all calculated technical indicators."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ema": {"ema": 45000.5, "period": 12},
                "macd": {"macd": 100.5, "signal": 95.2, "histogram": 5.3},
                "rsi": {"rsi": 65.5, "period": 14},
                "bollinger_bands": {
                    "upper": 46000.0,
                    "middle": 45000.0,
                    "lower": 44000.0,
                    "period": 20,
                    "std_dev": 2.0,
                },
                "atr": {"atr": 500.0, "period": 14},
                "timestamp": "2024-01-01T12:00:00",
                "candle_count": 100,
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
