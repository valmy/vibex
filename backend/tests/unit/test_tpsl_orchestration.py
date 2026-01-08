from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.services.execution.adapters.live_adapter import LiveExecutionAdapter
from app.services.execution.adapters.paper_adapter import PaperExecutionAdapter
from app.services.market_data.client import AsterClient


@pytest.mark.unit
class TestTPSLOrchestration:
    @pytest.fixture
    def mock_client(self):
        client = MagicMock(spec=AsterClient)
        # Mock klines for Paper
        client.fetch_klines = AsyncMock(
            return_value=[[1600000000000, 50000.0, 51000.0, 49000.0, 50000.0, 100.0]]
        )
        # Mock place_order for Live
        client.place_order = AsyncMock(
            side_effect=[
                {"orderId": "1", "status": "FILLED", "avgPrice": "50000"},  # Primary
                {"orderId": "2", "status": "NEW"},  # TP
                {"orderId": "3", "status": "NEW"},  # SL
            ]
        )
        return client

    @pytest.fixture
    def mock_db(self):
        db = MagicMock(spec=AsyncSession)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)
        return db

    @pytest.mark.asyncio
    async def test_paper_tpsl_creation(self, mock_client, mock_db):
        """Test that paper adapter creates pending orders for TP/SL."""
        adapter = PaperExecutionAdapter(client=mock_client)

        await adapter.execute_market_order(
            db=mock_db,
            account_id=1,
            symbol="BTCUSDT",
            action="buy",
            quantity=1.0,
            tp_price=55000.0,
            sl_price=45000.0,
        )

        # Verify db.add called for Order records
        # Expected: 1 filled Order (Primary) - Wait, previous impl didn't create Order, only Trade.
        # Now we should probably create Order record for Primary too for consistency.
        # But specifically checking for TP and SL orders.

        orders = []
        for call in mock_db.add.call_args_list:
            arg = call[0][0]
            if isinstance(arg, Order):
                orders.append(arg)

        # We expect at least TP and SL orders
        tp_order = next((o for o in orders if o.order_type == "take_profit"), None)
        sl_order = next((o for o in orders if o.order_type == "stop_loss"), None)

        assert tp_order is not None
        assert tp_order.price == 55000.0
        assert tp_order.status == "pending"

        assert sl_order is not None
        assert sl_order.stop_price == 45000.0
        assert sl_order.status == "pending"

    @pytest.mark.asyncio
    async def test_live_tpsl_calls(self, mock_client, mock_db):
        """Test that live adapter calls API for TP/SL."""
        adapter = LiveExecutionAdapter(client=mock_client)

        await adapter.execute_market_order(
            db=mock_db,
            account_id=1,
            symbol="BTCUSDT",
            action="buy",
            quantity=1.0,
            tp_price=55000.0,
            sl_price=45000.0,
        )

        assert mock_client.place_order.call_count == 3

        # Check TP call
        # Expected: SELL, LIMIT/TAKE_PROFIT, Price 55000, ReduceOnly
        mock_client.place_order.assert_any_call(
            symbol="BTCUSDT",
            side="SELL",
            type="TAKE_PROFIT",  # or LIMIT depending on implementation
            quantity=1.0,
            price=55000.0,
            reduce_only=True,
        )

        # Check SL call
        # Expected: SELL, STOP_MARKET, StopPrice 45000, ReduceOnly
        # Since place_order signature needs adjustment for stop_price/trigger_price
        # For now assuming 'price' handles it or we update signature.
        # Let's assume we pass trigger_price as 'price' for STOP_MARKET or update Client.
        # Standard AsterDEX/Binance usually has 'stopPrice'.
        # I'll update Client.place_order to accept stop_price.

        mock_client.place_order.assert_any_call(
            symbol="BTCUSDT",
            side="SELL",
            type="STOP_MARKET",
            quantity=1.0,
            stop_price=45000.0,
            reduce_only=True,
        )
