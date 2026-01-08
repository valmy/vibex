from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trade import Trade
from app.services.execution.adapters.paper_adapter import PaperExecutionAdapter
from app.services.market_data.client import AsterClient


@pytest.mark.unit
class TestPaperExecutionAdapter:
    @pytest.mark.asyncio
    async def test_execute_market_order_simulation(self):
        """Test that paper adapter simulates a trade using fetched price."""
        # 1. Setup mocks
        mock_client = MagicMock(spec=AsterClient)
        # Mocking fetch_klines to return a candle [timestamp, open, high, low, close, volume, ...]
        # Close price is index 4.
        mock_client.fetch_klines = AsyncMock(
            return_value=[[1600000000000, 50000.0, 51000.0, 49000.0, 50500.0, 100.0]]
        )

        mock_db = MagicMock(spec=AsyncSession)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        # Mock execute for position check
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # No existing position
        mock_db.execute = AsyncMock(return_value=mock_result)

        adapter = PaperExecutionAdapter(client=mock_client)

        # 2. Execute
        account_id = 1
        symbol = "BTCUSDT"
        action = "buy"
        quantity = 0.1

        result = await adapter.execute_market_order(
            db=mock_db, account_id=account_id, symbol=symbol, action=action, quantity=quantity
        )

        # 3. Verify
        # Check price fetch called
        mock_client.fetch_klines.assert_called_once()

        # Check trade creation
        # db.add called for Trade AND Position
        assert mock_db.add.call_count >= 1

        # Verify Trade object
        # We need to find the Trade object in the calls
        trade_arg = None
        for call in mock_db.add.call_args_list:
            arg = call[0][0]
            if isinstance(arg, Trade):
                trade_arg = arg
                break

        assert trade_arg is not None
        assert trade_arg.account_id == account_id
        assert trade_arg.symbol == symbol
        assert trade_arg.side == action
        assert trade_arg.quantity == quantity
        assert trade_arg.price == 50500.0  # From mock candle close
        assert trade_arg.total_cost == 50500.0 * quantity

        # Check result
        assert result["status"] == "filled"
        assert result["price"] == 50500.0
        assert result["is_paper"] is True
