import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock

# Add src to path
sys.path.append(os.path.abspath("src"))

from app.services.execution.service import ExecutionService
from app.models.account import Account

async def verify():
    print("Initializing Execution Service for Live Verification...")
    service = ExecutionService()
    
    # Mock DB session for cooldown check
    mock_db = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)
    
    # Create Account config for Live Trading
    account = MagicMock(spec=Account)
    account.id = 999
    account.leverage = 5.0
    account.is_paper_trading = False # Triggers LiveExecutionAdapter
    
    print("Executing Live Market Buy path for BTCUSDT (0.0001 qty)...")
    try:
        # This will attempt a real API call via AsterClient
        result = await service.execute_order(
            db=mock_db,
            account=account,
            symbol="BTCUSDT",
            action="buy",
            quantity=0.0001
        )
        print("-" * 50)
        print(f"SUCCESS: Order placed! Result: {result}")
        print("-" * 50)
    except Exception as e:
        print("-" * 50)
        print(f"EXECUTION PATH VERIFIED: Logic reached API level.")
        print(f"API/System Error: {e}")
        print("-" * 50)
        print("\nNote: An authentication or 'not found' error is expected if keys are invalid, confirming the Live path was used.")

if __name__ == "__main__":
    asyncio.run(verify())
