import pytest
from unittest.mock import MagicMock
from app.models.account import Account
from app.services.execution.factory import ExecutionAdapterFactory
from app.services.execution.adapters.paper_adapter import PaperExecutionAdapter
from app.services.execution.adapters.live_adapter import LiveExecutionAdapter

@pytest.mark.unit
class TestExecutionAdapterFactory:
    def test_get_paper_adapter(self):
        """Test that factory returns PaperExecutionAdapter when is_paper_trading is True."""
        account = MagicMock(spec=Account)
        account.is_paper_trading = True
        
        adapter = ExecutionAdapterFactory.get_adapter(account)
        
        assert isinstance(adapter, PaperExecutionAdapter)

    def test_get_live_adapter(self):
        """Test that factory returns LiveExecutionAdapter when is_paper_trading is False."""
        account = MagicMock(spec=Account)
        account.is_paper_trading = False
        
        adapter = ExecutionAdapterFactory.get_adapter(account)
        
        assert isinstance(adapter, LiveExecutionAdapter)
