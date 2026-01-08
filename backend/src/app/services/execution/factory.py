from app.models.account import Account
from .adapters.base import ExecutionAdapter
from .adapters.paper_adapter import PaperExecutionAdapter
from .adapters.live_adapter import LiveExecutionAdapter

class ExecutionAdapterFactory:
    """Factory for creating execution adapters based on account configuration."""

    @staticmethod
    def get_adapter(account: Account) -> ExecutionAdapter:
        """
        Get the appropriate execution adapter for the given account.
        
        Args:
            account: The trading account model.
            
        Returns:
            An instance of ExecutionAdapter (Paper or Live).
        """
        if account.is_paper_trading:
            return PaperExecutionAdapter()
        return LiveExecutionAdapter()
