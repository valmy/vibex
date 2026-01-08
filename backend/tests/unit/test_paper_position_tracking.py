import pytest
from unittest.mock import MagicMock, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.execution.adapters.paper_adapter import PaperExecutionAdapter
from app.services.market_data.client import AsterClient
from app.models.position import Position
from app.models.trade import Trade

@pytest.mark.unit
class TestPaperPositionTracking:
    
    @pytest.fixture
    def mock_client(self):
        client = MagicMock(spec=AsterClient)
        client.fetch_klines = AsyncMock(return_value=[
            [1600000000000, 50000.0, 51000.0, 49000.0, 50000.0, 100.0]
        ])
        return client

    @pytest.fixture
    def mock_db(self):
        db = MagicMock(spec=AsyncSession)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_open_new_position(self, mock_client, mock_db):
        """Test creating a new position when none exists."""
        adapter = PaperExecutionAdapter(client=mock_client)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        await adapter.execute_market_order(
            db=mock_db, 
            account_id=1, 
            symbol="BTCUSDT", 
            action="buy", 
            quantity=1.0
        )
        
        calls = mock_db.add.call_args_list
        position_arg = None
        for call in calls:
            arg = call[0][0]
            if isinstance(arg, Position):
                position_arg = arg
                break
        
        assert position_arg is not None
        assert position_arg.symbol == "BTCUSDT"
        assert position_arg.quantity == 1.0
        assert position_arg.entry_price == 50000.0
        assert position_arg.side == "long"

    @pytest.mark.asyncio
    async def test_update_existing_position(self, mock_client, mock_db):
        """Test adding to an existing position."""
        adapter = PaperExecutionAdapter(client=mock_client)
        
        existing_pos = Position(
            id=1,
            account_id=1,
            symbol="BTCUSDT",
            side="long",
            quantity=1.0,
            entry_price=40000.0,
            entry_value=40000.0,
            current_price=50000.0,
            current_value=50000.0,
            unrealized_pnl=10000.0,
            unrealized_pnl_percent=25.0,
            status="open"
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_pos
        mock_db.execute.return_value = mock_result
        
        await adapter.execute_market_order(
            db=mock_db, 
            account_id=1, 
            symbol="BTCUSDT", 
            action="buy", 
            quantity=1.0
        )
        
        assert existing_pos.quantity == 2.0
        assert existing_pos.entry_price == 45000.0

    @pytest.mark.asyncio
    async def test_close_existing_position(self, mock_client, mock_db):
        """Test closing an existing position."""
        adapter = PaperExecutionAdapter(client=mock_client)
        
        # Existing Long position of 1.0 BTC
        existing_pos = Position(
            id=1,
            account_id=1,
            symbol="BTCUSDT",
            side="long",
            quantity=1.0,
            entry_price=40000.0,
            entry_value=40000.0,
            current_price=50000.0,
            current_value=50000.0,
            unrealized_pnl=10000.0,
            unrealized_pnl_percent=25.0,
            status="open"
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_pos
        mock_db.execute.return_value = mock_result
        
        # Sell 1.0 BTC (Close full)
        await adapter.execute_market_order(
            db=mock_db, 
            account_id=1, 
            symbol="BTCUSDT", 
            action="sell", 
            quantity=1.0
        )
        
        assert existing_pos.quantity == 0.0
        assert existing_pos.status == "closed"
        
    @pytest.mark.asyncio
    async def test_reduce_existing_position(self, mock_client, mock_db):
        """Test reducing an existing position."""
        adapter = PaperExecutionAdapter(client=mock_client)
        
        # Existing Long position of 1.0 BTC
        existing_pos = Position(
            id=1,
            account_id=1,
            symbol="BTCUSDT",
            side="long",
            quantity=1.0,
            entry_price=40000.0,
            entry_value=40000.0,
            current_price=50000.0,
            current_value=50000.0,
            unrealized_pnl=10000.0,
            unrealized_pnl_percent=25.0,
            status="open"
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_pos
        mock_db.execute.return_value = mock_result
        
        # Sell 0.5 BTC (Partial Close)
        await adapter.execute_market_order(
            db=mock_db, 
            account_id=1, 
            symbol="BTCUSDT", 
            action="sell", 
            quantity=0.5
        )
        
        assert existing_pos.quantity == 0.5
        assert existing_pos.entry_price == 40000.0 # Entry price shouldn't change on reduction
        assert existing_pos.status == "open"