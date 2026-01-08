import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock

# Add src to path
sys.path.append(os.path.abspath("src"))

from app.services.execution.adapters.paper_adapter import PaperExecutionAdapter


async def verify():
    print("Initializing Paper Execution Adapter...")

    # Mock DB session
    mock_db = MagicMock()
    mock_db.add = lambda x: print(f"DB Add: {x}")
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    # Initialize Adapter (uses real AsterClient from config)
    try:
        adapter = PaperExecutionAdapter()

        print("Executing Paper Market Buy for BTCUSDT...")
        # Note: This requires valid ASTERDEX_API_KEY in .env or environment
        result = await adapter.execute_market_order(
            db=mock_db, account_id=1, symbol="BTCUSDT", action="buy", quantity=0.001
        )
        print("-" * 50)
        print(f"Execution Result: {result['status']} at ${result['price']}")
        print(f"Order ID: {result['order_id']}")
        print("-" * 50)

        if result["status"] == "filled" and result["price"] > 0:
            print("SUCCESS: Paper trade executed with real market price.")
        else:
            print("FAILED: Invalid result.")

    except Exception as e:
        print(f"FAILED with error: {e}")
        print(
            "\nNote: This script requires valid ASTERDEX_API_KEY/SECRET in backend/.env to fetch real market prices."
        )


if __name__ == "__main__":
    asyncio.run(verify())
