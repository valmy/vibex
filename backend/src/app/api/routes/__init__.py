"""
API routes for the AI Trading Agent application.

Exports all route modules for easy importing.
"""

from . import accounts, positions, orders, trades, diary, performance, market_data, analysis

__all__ = ["accounts", "positions", "orders", "trades", "diary", "performance", "market_data", "analysis"]
