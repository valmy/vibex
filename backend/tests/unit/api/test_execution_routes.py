import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, AsyncMock, patch
from app.main import app
from app.db.session import get_db

@pytest.mark.unit
class TestExecutionRoutes:
    
    @pytest.fixture
    def transport(self):
        return ASGITransport(app=app)

    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.execute = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_get_execution_status(self, transport, mock_db):
        """Test GET /api/v1/execution/status/{account_id}"""
        account_id = 1
        
        # Setup overrides
        app.dependency_overrides[get_db] = lambda: mock_db
        
        # Mock account
        mock_account = MagicMock()
        mock_account.id = account_id
        mock_account.name = "Test Account"
        mock_account.is_paper_trading = True
        mock_account.status = "active"
        mock_account.positions = []
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_account
        mock_db.execute.return_value = mock_result

        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(f"/api/v1/execution/status/{account_id}")
        
        # Cleanup overrides
        app.dependency_overrides.clear()
        
        assert response.status_code == 200
        data = response.json()
        assert data["account_id"] == account_id

    @pytest.mark.asyncio
    async def test_trigger_reconciliation(self, transport, mock_db):
        """Test POST /api/v1/execution/reconcile/{account_id}"""
        account_id = 1
        
        # Setup overrides
        app.dependency_overrides[get_db] = lambda: mock_db
        
        # Mock service
        with patch("app.api.routes.execution.get_execution_service") as mock_get_service, \
             patch("app.middleware.verify_token") as mock_verify, \
             patch("app.middleware.sessionmaker") as mock_session_maker:
            
            # 1. Bypass Admin Check
            mock_verify.return_value = MagicMock(username="0x123")
            mock_session = MagicMock()
            mock_session.query().filter().first.return_value = MagicMock(is_admin=True)
            mock_session_maker.return_value.return_value = mock_session
            
            mock_service = AsyncMock()
            mock_service.reconcile_positions.return_value = {"status": "success"}
            mock_get_service.return_value = mock_service
            
            # 2. Mock account fetch
            mock_account = MagicMock()
            mock_account.id = account_id
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_account
            mock_db.execute.return_value = mock_result

            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.post(
                    f"/api/v1/execution/reconcile/{account_id}",
                    headers={"Authorization": "Bearer dummy"}
                )
            
            # Cleanup
            app.dependency_overrides.clear()
            
            assert response.status_code == 200
            assert response.json()["status"] == "success"
            mock_service.reconcile_positions.assert_called_once()
