"""
Market data model for OHLCV data.

Represents candlestick data for trading pairs.
"""

from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Index
from .base import BaseModel


class MarketData(BaseModel):
    """Market data (OHLCV) model."""

    __tablename__ = "market_data"
    __table_args__ = (
        Index("idx_market_data_symbol_time", "symbol", "time"),
        Index("idx_market_data_symbol", "symbol"),
        Index("idx_market_data_time", "time"),
        Index("idx_market_data_interval", "interval"),
    )

    # Market identification
    symbol = Column(String(50), nullable=False, index=True)  # e.g., BTC/USDT
    interval = Column(String(20), nullable=False)  # e.g., 1h, 4h, 1d

    # Candlestick data
    time = Column(DateTime, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)

    # Additional data
    quote_asset_volume = Column(Float, nullable=True)
    number_of_trades = Column(Float, nullable=True)
    taker_buy_base_asset_volume = Column(Float, nullable=True)
    taker_buy_quote_asset_volume = Column(Float, nullable=True)

    def __repr__(self):
        """String representation."""
        return f"<MarketData(symbol={self.symbol}, time={self.time}, close={self.close})>"

