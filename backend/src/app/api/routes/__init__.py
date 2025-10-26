"""
API routes for the AI Trading Agent application.

Exports all route modules for easy importing.
"""

from . import accounts, analysis, diary, market_data, orders, performance, positions, trades

__all__ = [
    "accounts",
    "positions",
    "orders",
    "trades",
    "diary",
    "performance",
    "market_data",
    "analysis",
]
