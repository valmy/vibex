from typing import Any, Dict, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.trade import Trade
from app.models.position import Position
from app.models.order import Order
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
        quantity: float,
        tp_price: Optional[float] = None,
        sl_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """Simulate a market order execution with optional TP/SL."""
        
        # 1. Fetch current price
        klines = await self.client.fetch_klines(symbol, interval="1m", limit=1)
        if not klines:
            raise ValueError(f"Could not fetch price for {symbol}")
        price = float(klines[0][4])
        
        # 2. Create Primary Order (Filled immediately)
        primary_order = Order(
            account_id=account_id,
            symbol=symbol,
            side=action,
            order_type="market",
            quantity=quantity,
            price=price,
            filled_quantity=quantity,
            average_price=price,
            status="filled",
            total_cost=price * quantity,
            exchange_order_id=f"paper_ord_{symbol}_{int(klines[0][0])}"
        )
        db.add(primary_order)
        
        # 3. Create Trade record
        total_cost = price * quantity
        trade = Trade(
            account_id=account_id,
            symbol=symbol,
            side=action,
            quantity=quantity,
            price=price,
            total_cost=total_cost,
            commission=0.0,
            exchange_trade_id=f"paper_trd_{symbol}_{int(klines[0][0])}",
            order=primary_order
        )
        db.add(trade)
        
        # 4. Update Position
        position = await self._update_position(db, account_id, symbol, trade)
        
        # Link primary order to position
        if position:
            primary_order.position = position
            # Update Position TP/SL fields if provided (Paper specific tracking)
            if tp_price:
                position.take_profit = tp_price
            if sl_price:
                position.stop_loss = sl_price

        # 5. Create TP/SL Orders (Pending)
        # Determine opposite side
        exit_side = "sell" if action == "buy" else "buy"
        
        if tp_price:
            tp_order = Order(
                account_id=account_id,
                symbol=symbol,
                side=exit_side,
                order_type="take_profit",
                quantity=quantity,
                price=tp_price, # Limit price for TP
                stop_price=None, # Usually TP is limit, but can be Trigger. Assume Limit for paper simplicity.
                status="pending",
                position=position
            )
            db.add(tp_order)
            
        if sl_price:
            sl_order = Order(
                account_id=account_id,
                symbol=symbol,
                side=exit_side,
                order_type="stop_loss",
                quantity=quantity,
                price=None, # Market stop
                stop_price=sl_price,
                status="pending",
                position=position
            )
            db.add(sl_order)
        
        return {
            "order_id": primary_order.exchange_order_id,
            "status": "filled",
            "price": price,
            "is_paper": True,
            "trade_obj": trade,
            "position_obj": position
        }

    async def _update_position(
        self, 
        db: AsyncSession, 
        account_id: int, 
        symbol: str, 
        trade: Trade
    ) -> Optional[Position]:
        """Update or create position based on trade."""
        
        # Fetch existing open position
        # Note: We must await execute()
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
            trade.position = position
            return position
            
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
                position.current_value = new_quantity * trade.price
                
                trade.position = position
                return position
                
            # Case 2: Closing or reducing position (Opposite side)
            else:
                if trade.quantity <= position.quantity:
                    # Reducing
                    position.quantity -= trade.quantity
                    # Entry price stays same for remaining portion
                    position.entry_value = position.quantity * position.entry_price
                    
                    if position.quantity == 0:
                        position.status = "closed"
                    
                    position.current_price = trade.price
                    position.current_value = position.quantity * trade.price
                    
                    trade.position = position
                    
                    if position.quantity == 0:
                        # If closed, we might want to return None or closed position
                        # Returning closed position so orders can be linked (historical)
                        return position
                    return position
                    
                else:
                    # Close current
                    remaining_qty = trade.quantity - position.quantity
                    position.quantity = 0
                    position.status = "closed"
                    position.current_price = trade.price
                    position.current_value = 0
                    
                    trade.position = position
                    
                    # Open new for remainder
                    if remaining_qty > 0:
                        new_pos = Position(
                            account_id=account_id,
                            symbol=symbol,
                            side=trade_side, # New side
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
                        # We can't easily link trade to TWO positions.
                        # For now, link to the closed one as primary impact.
                        return new_pos
                    return position