"""
SQLAlchemy ORM models for the AI Trading Agent application.

Exports all models for easy importing.
"""

from .account import Account
from .base import Base, BaseModel
from .diary_entry import DiaryEntry
from .market_data import MarketData
from .order import Order
from .performance_metric import PerformanceMetric
from .position import Position
from .trade import Trade

# Import new models if they exist
try:
    from .decision import Decision, DecisionResult
    from .strategy import Strategy, StrategyAssignment, StrategyPerformance

    __all__ = [
        "Base",
        "BaseModel",
        "Account",
        "Decision",
        "DecisionResult",
        "MarketData",
        "Position",
        "Order",
        "Strategy",
        "StrategyAssignment",
        "StrategyPerformance",
        "Trade",
        "DiaryEntry",
        "PerformanceMetric",
    ]
except ImportError:
    __all__ = [
        "Base",
        "BaseModel",
        "Account",
        "MarketData",
        "Position",
        "Order",
        "Trade",
        "DiaryEntry",
        "PerformanceMetric",
    ]