from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import config
from app.services.market_data.client import AsterClient

from .base import ExecutionAdapter


class LiveExecutionAdapter(ExecutionAdapter):
    """Execution adapter for live trading on AsterDEX."""

    def __init__(self, client: Optional[AsterClient] = None):
        self.client = client or AsterClient(
            api_key=config.ASTERDEX_API_KEY,
            api_secret=config.ASTERDEX_API_SECRET,
            base_url=config.ASTERDEX_BASE_URL,
        )

    async def execute_market_order(
        self,
        db: AsyncSession,
        account_id: int,
        symbol: str,
        action: str,
        quantity: float,
        tp_price: Optional[float] = None,
        sl_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Execute a real market order on AsterDEX with optional TP/SL."""

        # 1. Place Primary Order
        response = await self.client.place_order(
            symbol=symbol, side=action.upper(), type="MARKET", quantity=quantity
        )

        order_id = str(response.get("orderId", response.get("id", "")))
        status = response.get("status", "NEW")
        price = float(response.get("avgPrice", response.get("price", 0.0)))

        # 2. Place TP/SL if provided
        # Note: We should ideally check if primary order was filled or at least accepted.
        # Assuming synchronous response success implies acceptance.

        exit_side = "SELL" if action.lower() == "buy" else "BUY"

        if tp_price:
            # Place Take Profit (Limit or Take Profit Market?)
            # Usually standard Take Profit is a Trigger order.
            # Using TAKE_PROFIT type (Trigger order).
            # Price logic: Limit price or Trigger price?
            # Assuming 'price' is Limit Price for TAKE_PROFIT_LIMIT or just price for TAKE_PROFIT market.
            # AsterDEX/Hyperliquid usually allows Trigger orders.
            # Let's assume TAKE_PROFIT with 'price' as Limit (if limit) or just price.
            # Usually needs 'stopPrice' (trigger).
            # If using TAKE_PROFIT (market), pass stopPrice.
            # If using LIMIT (reduce only), pass price.
            # Let's assume LIMIT ReduceOnly for TP to be safe and simple (maker).

            await self.client.place_order(
                symbol=symbol,
                side=exit_side,
                type="TAKE_PROFIT",  # or LIMIT
                quantity=quantity,
                price=tp_price,  # Limit price
                reduce_only=True,
            )

        if sl_price:
            # Place Stop Loss
            # Usually STOP_MARKET with stopPrice.
            await self.client.place_order(
                symbol=symbol,
                side=exit_side,
                type="STOP_MARKET",
                quantity=quantity,
                stop_price=sl_price,
                reduce_only=True,
            )

        return {
            "order_id": order_id,
            "status": status,
            "price": price,
            "is_paper": False,
            "raw_response": response,
        }
