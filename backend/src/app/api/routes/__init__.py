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
               llm_decisions,
               market_data,
               monitoring,
               orders,
               performance,
               positions,
               strategies,
               trades,
)

__all__ = [
    "accounts",
    "analysis",
    "auth",
    "decision_engine",
    "diary",
    "llm_decisions",
    "market_data",
    "monitoring",
    "orders",
    "performance",
    "positions",
    "strategies",
    "trades",
]
