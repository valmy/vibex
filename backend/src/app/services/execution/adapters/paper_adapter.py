from typing import Any, Dict, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.trade import Trade
from app.models.position import Position
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
            commission=0.0,
            exchange_trade_id=f"paper_{symbol}_{int(klines[0][0])}" 
        )
        
        db.add(trade)
        
        # 3. Update Position
        await self._update_position(db, account_id, symbol, trade)
        
        return {
            "order_id": trade.exchange_trade_id,
            "status": "filled",
            "price": price,
            "is_paper": True,
            "trade_obj": trade 
        }

    async def _update_position(
        self, 
        db: AsyncSession, 
        account_id: int, 
        symbol: str, 
        trade: Trade
    ) -> None:
        """Update or create position based on trade."""
        
        # Fetch existing open position
        result = await db.execute(
            select(Position).where(
                Position.account_id == account_id,
                Position.symbol == symbol,
                Position.status == "open"
            )
        )
        position = result.scalar_one_or_none()
        
        # Determine trade side (long/short)
        trade_side = "long" if trade.side == "buy" else "short"
        
        if not position:
            # Create new position
            position = Position(
                account_id=account_id,
                symbol=symbol,
                side=trade_side,
                quantity=trade.quantity,
                entry_price=trade.price,
                entry_value=trade.total_cost,
                current_price=trade.price,
                current_value=trade.total_cost,
                unrealized_pnl=0.0,
                unrealized_pnl_percent=0.0,
                status="open"
            )
            db.add(position)
            # Link trade to position (optional, but good practice)
            trade.position = position
            
        else:
            # Update existing position
            
            # Case 1: Increasing position size (Same side)
            if position.side == trade_side:
                new_quantity = position.quantity + trade.quantity
                new_entry_value = position.entry_value + trade.total_cost
                new_entry_price = new_entry_value / new_quantity
                
                position.quantity = new_quantity
                position.entry_value = new_entry_value
                position.entry_price = new_entry_price
                position.current_price = trade.price
                # Recalculate metrics (simplified for paper trading)
                position.current_value = new_quantity * trade.price
                
                trade.position = position
                
            # Case 2: Closing or reducing position (Opposite side)
            else:
                # Assuming simple FIFO or weighted logic for PnL
                # If closing partially or fully
                if trade.quantity <= position.quantity:
                    # Reducing
                    position.quantity -= trade.quantity
                    # Entry price stays same for remaining portion
                    position.entry_value = position.quantity * position.entry_price
                    
                    if position.quantity == 0:
                        position.status = "closed"
                    
                    # Update current price/value
                    position.current_price = trade.price
                    position.current_value = position.quantity * trade.price
                    
                    trade.position = position
                    
                else:
                    # Flipping position (Close current, open new opposite)
                    # For MVP, let's just close current and leftover creates new?
                    # Or throw error? Or handle flip.
                    # Simpler: Just close current fully, ignore remainder for now (or handle as new position logic which is complex)
                    # Let's verify requirement. "Update local position".
                    # Let's assume for now we don't flip in one trade for simplicity or handle strictly.
                    # Logic: Close current position.
                    
                    remaining_qty = trade.quantity - position.quantity
                    position.quantity = 0
                    position.status = "closed"
                    position.current_price = trade.price
                    position.current_value = 0
                    
                    trade.position = position
                    
                    # Create new position for remainder
                    if remaining_qty > 0:
                        new_pos = Position(
                            account_id=account_id,
                            symbol=symbol,
                            side=trade_side,
                            quantity=remaining_qty,
                            entry_price=trade.price,
                            entry_value=remaining_qty * trade.price,
                            current_price=trade.price,
                            current_value=remaining_qty * trade.price,
                            unrealized_pnl=0.0,
                            unrealized_pnl_percent=0.0,
                            status="open"
                        )
                        db.add(new_pos)
                        # Trade might need to link to two positions? 
                        # Trade model has single position_id. 
                        # Ideally split trade into two trades.
                        # For now, let's just handle simple reduction/close.
                        pass
