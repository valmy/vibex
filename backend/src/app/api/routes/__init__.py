"""
API routes for the AI Trading Agent application.

Exports all route modules for easy importing.
"""

from . import (
    accounts,
    analysis,
    auth,
    decision_engine,
    diary,
    market_data,
    monitoring,
    orders,
    performance,
    positions,
    strategies,
    trades,
    users,
)

__all__ = [
    "accounts",
    "analysis",
    "auth",
    "decision_engine",
    "diary",
    "market_data",
    "monitoring",
    "orders",
    "performance",
    "positions",
    "strategies",
    "trades",
    "users",
]
