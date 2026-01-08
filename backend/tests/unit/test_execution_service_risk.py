from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.trade import Trade
from app.services.execution.service import ExecutionService, RiskCheckError


@pytest.mark.unit
class TestExecutionServiceRisk:
    @pytest.fixture
    def mock_db(self):
        db = MagicMock(spec=AsyncSession)
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def mock_account(self):
        account = MagicMock(spec=Account)
        account.id = 1
        account.leverage = 10.0
        account.is_paper_trading = True
        return account

    @pytest.fixture
    def service(self):
        return ExecutionService()

    @pytest.mark.asyncio
    async def test_leverage_limit_exceeded(self, service, mock_db, mock_account):
        """Test that execution fails if account leverage > 25x."""
        mock_account.leverage = 30.0

        # Match '25.0x' or '25x'
        with pytest.raises(RiskCheckError, match="Leverage 30.0 exceeds maximum allowed 25.0x"):
            await service.execute_order(
                db=mock_db, account=mock_account, symbol="BTCUSDT", action="buy", quantity=1.0
            )

    @pytest.mark.asyncio
    async def test_cooldown_active(self, service, mock_db, mock_account):
        """Test that execution fails if within cooldown period."""
        last_trade = MagicMock(spec=Trade)
        last_trade.created_at = datetime.now(timezone.utc) - timedelta(minutes=1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = last_trade
        mock_db.execute.return_value = mock_result

        with pytest.raises(RiskCheckError, match="Cooldown active"):
            await service.execute_order(
                db=mock_db, account=mock_account, symbol="BTCUSDT", action="buy", quantity=1.0
            )

    @pytest.mark.asyncio
    async def test_risk_checks_pass(self, service, mock_db, mock_account):
        """Test that execution proceeds if risk checks pass."""
        last_trade = MagicMock(spec=Trade)
        last_trade.created_at = datetime.now(timezone.utc) - timedelta(minutes=10)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = last_trade
        mock_db.execute.return_value = mock_result

        with patch(
            "app.services.execution.service.ExecutionAdapterFactory.get_adapter"
        ) as mock_factory:
            mock_adapter = AsyncMock()
            mock_adapter.execute_market_order = AsyncMock(return_value={"status": "filled"})
            mock_factory.return_value = mock_adapter

            result = await service.execute_order(
                db=mock_db, account=mock_account, symbol="BTCUSDT", action="buy", quantity=1.0
            )

            assert result["status"] == "filled"
            mock_adapter.execute_market_order.assert_called_once()
