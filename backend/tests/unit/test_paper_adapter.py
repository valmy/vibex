import pytest
from unittest.mock import MagicMock, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.execution.adapters.paper_adapter import PaperExecutionAdapter
from app.services.market_data.client import AsterClient
from app.models.trade import Trade

@pytest.mark.unit
class TestPaperExecutionAdapter:
    @pytest.mark.asyncio
    async def test_execute_market_order_simulation(self):
        """Test that paper adapter simulates a trade using fetched price."""
        # 1. Setup mocks
        mock_client = MagicMock(spec=AsterClient)
        # Mocking fetch_klines to return a candle [timestamp, open, high, low, close, volume, ...]
        # Close price is index 4.
        mock_client.fetch_klines = AsyncMock(return_value=[
            [1600000000000, 50000.0, 51000.0, 49000.0, 50500.0, 100.0]
        ])
        
        mock_db = MagicMock(spec=AsyncSession)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        adapter = PaperExecutionAdapter(client=mock_client)
        
        # 2. Execute
        account_id = 1
        symbol = "BTCUSDT"
        action = "buy"
        quantity = 0.1
        
        result = await adapter.execute_market_order(
            db=mock_db, 
            account_id=account_id, 
            symbol=symbol, 
            action=action, 
            quantity=quantity
        )
        
        # 3. Verify
        # Check price fetch called
        mock_client.fetch_klines.assert_called_once()
        
        # Check trade creation
        mock_db.add.assert_called_once()
        # Get the Trade object passed to add
        trade_arg = mock_db.add.call_args[0][0]
        assert isinstance(trade_arg, Trade)
        assert trade_arg.account_id == account_id
        assert trade_arg.symbol == symbol
        assert trade_arg.side == action
        assert trade_arg.quantity == quantity
        assert trade_arg.price == 50500.0 # From mock candle close
        assert trade_arg.total_cost == 50500.0 * quantity
        
        # Check result
        assert result["status"] == "filled"
        assert result["price"] == 50500.0
        assert result["is_paper"] is True
