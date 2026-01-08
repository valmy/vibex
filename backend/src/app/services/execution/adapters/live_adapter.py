from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.market_data.client import AsterClient
from app.core.config import config
from .base import ExecutionAdapter

class LiveExecutionAdapter(ExecutionAdapter):
    """Execution adapter for live trading on AsterDEX."""

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
        """Execute a real market order on AsterDEX."""
        
        # 1. Place order via API
        response = await self.client.place_order(
            symbol=symbol,
            side=action.upper(), # 'BUY' or 'SELL'
            type="MARKET",
            quantity=quantity
        )
        
        # 2. Parse response
        # Assuming standard Binance-like response
        order_id = str(response.get("orderId", response.get("id", "")))
        status = response.get("status", "NEW")
        
        # Note: Market orders might not return fill price immediately if asynchronous.
        # We might need to fetch trade details separately or use 'avgPrice' if available.
        # For MVP, we return what we have.
        price = float(response.get("avgPrice", response.get("price", 0.0)))
        
        # We don't create Trade/Position records here for Live trading?
        # The plan says "Fetch remote positions and compare with local DB" in Phase 3.
        # However, it's good practice to log the order locally immediately.
        # But `spec.md` says "Source of Truth (Live): AsterDEX".
        # So we trust the exchange and sync later.
        
        return {
            "order_id": order_id,
            "status": status,
            "price": price,
            "is_paper": False,
            "raw_response": response
        }
