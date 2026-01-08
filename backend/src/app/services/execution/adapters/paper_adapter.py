from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.trade import Trade
from app.services.market_data.client import AsterClient
from app.core.config import config
from .base import ExecutionAdapter

class PaperExecutionAdapter(ExecutionAdapter):
    """Execution adapter for paper trading (simulation)."""

    def __init__(self, client: Optional[AsterClient] = None):
        self.client = client or AsterClient(
            api_key=config.ASTERDEX_API_KEY,
            api_secret=config.ASTERDEX_API_SECRET,
            base_url=config.ASTERDEX_BASE_URL
        )

    async def execute_market_order(
        self, 
        db: AsyncSession, 
        account_id: int, 
        symbol: str, 
        action: str, 
        quantity: float
    ) -> Dict[str, Any]:
        """Simulate a market order execution."""
        
        # 1. Fetch current price
        # Using 1m candles to get latest price. Limit 1 gives the latest candle.
        klines = await self.client.fetch_klines(symbol, interval="1m", limit=1)
        if not klines:
            raise ValueError(f"Could not fetch price for {symbol}")
        
        # Candle format: [time, open, high, low, close, volume, ...]
        # We use 'close' price of the latest candle as the execution price
        price = float(klines[0][4])
        
        # 2. Create Trade record
        total_cost = price * quantity
        
        trade = Trade(
            account_id=account_id,
            symbol=symbol,
            side=action,
            quantity=quantity,
            price=price,
            total_cost=total_cost,
            commission=0.0, # Zero commission for paper trading initially? Or simulate it.
            # commission=total_cost * 0.0005, # Example 0.05%
            exchange_trade_id=f"paper_{symbol}_{int(klines[0][0])}" # Mock ID
        )
        
        db.add(trade)
        # Note: We don't commit here, allowing the caller (Service) to manage transaction/commit
        # or we commit if this is atomic. The test expects 'add' to be called.
        
        return {
            "order_id": trade.exchange_trade_id,
            "status": "filled",
            "price": price,
            "is_paper": True,
            "trade_obj": trade # For testing verification if needed
        }