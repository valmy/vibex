from typing import Any, Dict, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.account import Account
from app.models.trade import Trade
from app.services.execution.factory import ExecutionAdapterFactory

class RiskCheckError(Exception):
    """Raised when a risk check fails."""
    pass

class ExecutionService:
    """Service for handling trade execution orchestration and safety checks."""

    # Default cooldown in minutes
    DEFAULT_COOLDOWN_MINUTES = 5
    MAX_LEVERAGE = 25.0

    async def execute_order(
        self,
        db: AsyncSession,
        account: Account,
        symbol: str,
        action: str,
        quantity: float,
        tp_price: Optional[float] = None,
        sl_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Execute a trading order after performing risk checks.
        
        Args:
            db: Database session
            account: Trading account
            symbol: Asset symbol
            action: 'buy' or 'sell'
            quantity: Order quantity
            tp_price: Take profit price (optional)
            sl_price: Stop loss price (optional)
            
        Returns:
            Execution result dictionary
            
        Raises:
            RiskCheckError: If safety checks fail
        """
        
        # 1. Leverage Check
        if account.leverage > self.MAX_LEVERAGE:
            raise RiskCheckError(f"Leverage {account.leverage} exceeds maximum allowed {self.MAX_LEVERAGE}x")
            
        # 2. Cooldown Check
        await self._check_cooldown(db, account.id, symbol)
        
        # 3. Get Adapter
        adapter = ExecutionAdapterFactory.get_adapter(account)
        
        # 4. Execute
        return await adapter.execute_market_order(
            db=db,
            account_id=account.id,
            symbol=symbol,
            action=action,
            quantity=quantity,
            tp_price=tp_price,
            sl_price=sl_price
        )

    async def _check_cooldown(self, db: AsyncSession, account_id: int, symbol: str) -> None:
        """Check if trading is allowed based on cooldown period."""
        # Get last trade for this account and symbol
        stmt = (
            select(Trade)
            .where(Trade.account_id == account_id, Trade.symbol == symbol)
            .order_by(desc(Trade.created_at))
            .limit(1)
        )
        result = await db.execute(stmt)
        last_trade = result.scalar_one_or_none()
        
        if last_trade:
            # Check time difference
            # Ensure last_trade.created_at is timezone aware or handle naive
            last_time = last_trade.created_at
            if last_time.tzinfo is None:
                last_time = last_time.replace(tzinfo=timezone.utc)
                
            now = datetime.now(timezone.utc)
            diff = now - last_time
            
            if diff < timedelta(minutes=self.DEFAULT_COOLDOWN_MINUTES):
                raise RiskCheckError(
                    f"Cooldown active. Last trade was {diff.total_seconds():.0f}s ago. "
                    f"Wait {self.DEFAULT_COOLDOWN_MINUTES} minutes."
                )
