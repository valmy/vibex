"""
Market Data Service Module.

Provides market data fetching, storage, and candle-close scheduling.
"""

from .events import BaseEvent, CandleCloseEvent, EventType, event_handler
from .service import MarketDataService, get_market_data_service

__all__ = [
    "MarketDataService",
    "get_market_data_service",
    "CandleCloseEvent",
    "BaseEvent",
    "EventType",
    "event_handler",
]

