from abc import ABC, abstractmethod
from typing import Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession

class ExecutionAdapter(ABC):
    """Abstract base class for execution adapters."""

    @abstractmethod
    async def execute_market_order(
        self, 
        db: AsyncSession, 
        account_id: int, 
        symbol: str, 
        action: str, 
        quantity: float
    ) -> Dict[str, Any]:
        """
        Execute a market order.
        
        Args:
            db: Database session
            account_id: The trading account ID
            symbol: The asset symbol (e.g., 'BTC-USD')
            action: 'buy' or 'sell'
            quantity: The amount to trade
            
        Returns:
            Dict containing execution details (order_id, price, status, etc.)
        """
        pass