from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.position import Position
from app.services.execution.service import ExecutionService
from app.services.market_data.client import AsterClient


@pytest.mark.unit
class TestPositionReconciliation:
    @pytest.fixture
    def mock_db(self):
        db = MagicMock(spec=AsyncSession)
        db.execute = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        return db

    @pytest.fixture
    def mock_client(self):
        client = MagicMock(spec=AsterClient)
        client.fetch_positions = AsyncMock()
        return client

    @pytest.fixture
    def service(self):
        return ExecutionService()

    @pytest.mark.asyncio
    async def test_reconcile_close_missing_remote(self, service, mock_db, mock_client):
        """Test that local position is closed if it doesn't exist on remote."""
        account = MagicMock(spec=Account)
        account.id = 1
        account.is_paper_trading = False

        # 1. Mock local position exists
        local_pos = Position(
            id=1, account_id=1, symbol="BTCUSDT", status="open", quantity=1.0, side="long"
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [local_pos]
        mock_db.execute.return_value = mock_result

        # 2. Mock remote returns NO positions
        mock_client.fetch_positions.return_value = []

        # 3. Reconcile
        with MagicMock():
            # We need to ensure service uses our mock client
            # Actually, ExecutionService creates adapter which might have its own client.
            # I should update ExecutionService to accept an optional adapter or factory.
            # For now, I'll patch the factory to return an adapter with our mock client.
            with pytest.MonkeyPatch().context() as mp:
                mock_adapter = MagicMock()
                mock_adapter.client = mock_client
                mp.setattr(
                    "app.services.execution.service.ExecutionAdapterFactory.get_adapter",
                    lambda x: mock_adapter,
                )

                await service.reconcile_positions(mock_db, account)

        # 4. Verify local marked as closed
        assert local_pos.status == "closed"
        assert local_pos.quantity == 0.0
        mock_db.commit.assert_called_once()
