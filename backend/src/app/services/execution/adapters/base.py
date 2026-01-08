from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
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
        quantity: float,
        tp_price: Optional[float] = None,
        sl_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Execute a market order with optional TP/SL.
        
        Args:
            db: Database session
            account_id: The trading account ID
            symbol: The asset symbol (e.g., 'BTC-USD')
            action: 'buy' or 'sell'
            quantity: The amount to trade
            tp_price: Take-profit price (optional)
            sl_price: Stop-loss price (optional)
            
        Returns:
            Dict containing execution details
        """
        pass
