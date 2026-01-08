from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.execution.adapters.live_adapter import LiveExecutionAdapter
from app.services.market_data.client import AsterClient


@pytest.mark.unit
class TestLiveExecutionAdapter:
    @pytest.mark.asyncio
    async def test_execute_market_order_live(self):
        """Test that live adapter places a real order via AsterClient."""
        # 1. Setup mocks
        mock_client = MagicMock(spec=AsterClient)
        mock_client.place_order = AsyncMock(
            return_value={
                "orderId": "12345",
                "symbol": "BTCUSDT",
                "status": "NEW",
                "price": "50000",
                "origQty": "0.1",
                "executedQty": "0",
                "type": "MARKET",
                "side": "BUY",
            }
        )

        mock_db = MagicMock(spec=AsyncSession)

        adapter = LiveExecutionAdapter(client=mock_client)

        # 2. Execute
        account_id = 1
        symbol = "BTCUSDT"
        action = "buy"
        quantity = 0.1

        result = await adapter.execute_market_order(
            db=mock_db, account_id=account_id, symbol=symbol, action=action, quantity=quantity
        )

        # 3. Verify
        mock_client.place_order.assert_called_once_with(
            symbol=symbol,
            side="BUY",  # Should be uppercase? Usually APIs prefer uppercase
            type="MARKET",
            quantity=quantity,
        )

        assert result["order_id"] == "12345"
        assert result["status"] == "NEW"
        assert result["is_paper"] is False
