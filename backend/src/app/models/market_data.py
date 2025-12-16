"""
Market data model for OHLCV data.

Represents candlestick data for trading pairs.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Float, Index, Integer, String
from sqlalchemy.util import hybridproperty  # Import hybridproperty from sqlalchemy.util
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy.schema import PrimaryKeyConstraint

# Create a separate base for TimescaleDB models since they have different requirements
TimescaleBase = declarative_base()


class MarketData(TimescaleBase):
    """Market data (OHLCV) model for TimescaleDB hypertable."""

    __tablename__ = "market_data"
    __table_args__ = (
        PrimaryKeyConstraint("time", "id"),
        Index("idx_market_data_symbol", "symbol"),
        Index("idx_market_data_id", "id"),
        {"schema": "trading"},
    )

    # Note: Using composite primary key as required by TimescaleDB
    time: Mapped[datetime] = mapped_column(DateTime, nullable=False, primary_key=True)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)

    # Market identification
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # e.g., BTCUSDT
    interval: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g., 1h, 4h, 1d

    # Candlestick data
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)

    # Additional data
    quote_asset_volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    number_of_trades: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    taker_buy_base_asset_volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    taker_buy_quote_asset_volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Funding rate data
    funding_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Properties to match the expected schema field names
    @hybridproperty
    def timeframe(self) -> str:
        return self.interval

    @hybridproperty
    def open_price(self) -> float:
        return self.open

    @hybridproperty
    def high_price(self) -> float:
        return self.high

    @hybridproperty
    def low_price(self) -> float:
        return self.low

    @hybridproperty
    def close_price(self) -> float:
        return self.close

    def __repr__(self) -> str:
        """String representation."""
        return f"<MarketData(symbol={self.symbol}, time={self.time}, close={self.close})>"
