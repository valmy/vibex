from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.position import Position
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
        sl_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Execute a trading order after performing risk checks.
        """

        # 1. Leverage Check
        if account.leverage > self.MAX_LEVERAGE:
            raise RiskCheckError(
                f"Leverage {account.leverage} exceeds maximum allowed {self.MAX_LEVERAGE}x"
            )

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
            sl_price=sl_price,
        )

    async def _check_cooldown(self, db: AsyncSession, account_id: int, symbol: str) -> None:
        """Check if trading is allowed based on cooldown period."""
        stmt = (
            select(Trade)
            .where(Trade.account_id == account_id, Trade.symbol == symbol)
            .order_by(desc(Trade.created_at))
            .limit(1)
        )
        result = await db.execute(stmt)
        last_trade = result.scalar_one_or_none()

        if last_trade:
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

    async def reconcile_positions(self, db: AsyncSession, account: Account) -> Dict[str, Any]:
        """
        Reconcile local position state with the exchange.
        """
        if account.is_paper_trading:
            return {"status": "skipped", "reason": "paper_trading"}

        adapter = ExecutionAdapterFactory.get_adapter(account)
        if not hasattr(adapter, "client"):
            return {"status": "error", "reason": "adapter_no_client"}

        remote_positions = await adapter.client.fetch_positions()
        remote_map = {p["symbol"]: p for p in remote_positions if float(p.get("size", 0)) != 0}

        stmt = select(Position).where(Position.account_id == account.id, Position.status == "open")
        result = await db.execute(stmt)
        local_positions = result.scalars().all()

        actions = []

        for local_pos in local_positions:
            if local_pos.symbol not in remote_map:
                local_pos.status = "closed"
                local_pos.quantity = 0.0
                actions.append(f"Closed local position for {local_pos.symbol}")
            else:
                remote_pos = remote_map.pop(local_pos.symbol)
                local_pos.quantity = abs(float(remote_pos["size"]))
                local_pos.entry_price = float(remote_pos["entryPrice"])
                actions.append(f"Updated local position for {local_pos.symbol}")

        for symbol, remote_pos in remote_map.items():
            new_pos = Position(
                account_id=account.id,
                symbol=symbol,
                side="long" if float(remote_pos["size"]) > 0 else "short",
                quantity=abs(float(remote_pos["size"])),
                entry_price=float(remote_pos["entryPrice"]),
                entry_value=abs(float(remote_pos["size"])) * float(remote_pos["entryPrice"]),
                current_price=float(remote_pos["entryPrice"]),
                current_value=abs(float(remote_pos["size"])) * float(remote_pos["entryPrice"]),
                unrealized_pnl=0.0,
                unrealized_pnl_percent=0.0,
                status="open",
            )
            db.add(new_pos)
            actions.append(f"Created local position for {symbol} (external)")

        await db.commit()
        return {"status": "success", "actions": actions}


# Global instance
_execution_service: Optional[ExecutionService] = None


def get_execution_service() -> ExecutionService:
    """Get or create the execution service instance."""
    global _execution_service
    if _execution_service is None:
        _execution_service = ExecutionService()
    return _execution_service
