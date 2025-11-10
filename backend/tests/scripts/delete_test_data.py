#!/usr/bin/env python3
"""Delete test data."""

import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def delete_test_data():
    """Delete test data."""
    engine = create_async_engine(
        "postgresql+asyncpg://trading_user:trading_password@localhost:5432/trading_db"
    )
    
    try:
        async with engine.begin() as conn:
            # Delete test market data
            await conn.execute(text("DELETE FROM trading.market_data WHERE symbol IN ('BTCUSDT', 'ETHUSDT')"))
            print("✓ Test market data deleted")
            
            # Delete test account
            await conn.execute(text("DELETE FROM trading.accounts WHERE id = 1"))
            print("✓ Test account deleted")
            
            # Delete test user
            await conn.execute(text("DELETE FROM trading.users WHERE address = '0xCfbEE662dc66475Bf5F3b7203b4b6EE03028952F'"))
            print("✓ Test user deleted")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(delete_test_data())

