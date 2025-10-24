"""
Market data model for OHLCV data.

Represents candlestick data for trading pairs.
"""

from sqlalchemy import Column, String, Float, DateTime, Integer, Index
from sqlalchemy.schema import PrimaryKeyConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property


# Create a separate base for TimescaleDB models since they have different requirements
TimescaleBase = declarative_base()


class MarketData(TimescaleBase):
    """Market data (OHLCV) model for TimescaleDB hypertable."""
    
    __tablename__ = "market_data"
    __table_args__ = (
        PrimaryKeyConstraint("time", "id"),
        Index("idx_market_data_symbol", "symbol"),
        Index("idx_market_data_id", "id"),
        {"schema": "trading"}
    )

    # Note: Using composite primary key as required by TimescaleDB
    time = Column(DateTime, nullable=False, primary_key=True)
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Market identification
    symbol = Column(String(50), nullable=False, index=True)  # e.g., BTC/USDT
    interval = Column(String(20), nullable=False)  # e.g., 1h, 4h, 1d

    # Candlestick data
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

    # Properties to match the expected schema field names
    @hybrid_property
    def timeframe(self):
        return self.interval
        
    @hybrid_property
    def open_price(self):
        return self.open
        
    @hybrid_property
    def high_price(self):
        return self.high
        
    @hybrid_property
    def low_price(self):
        return self.low
        
    @hybrid_property
    def close_price(self):
        return self.close

    def __repr__(self):
        """String representation."""
        return f"<MarketData(symbol={self.symbol}, time={self.time}, close={self.close})>"

