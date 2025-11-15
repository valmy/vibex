#!/usr/bin/env python3
"""Add funding_rate column to market_data table if it doesn't exist."""

import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def main():
    """Add funding_rate column to market_data table."""
    engine = create_async_engine(
        "postgresql+asyncpg://trading_user:trading_password@localhost:5432/trading_db"
    )
    
    try:
        async with engine.begin() as conn:
            # Check if column exists
            result = await conn.execute(
                text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'trading'
                    AND table_name = 'market_data'
                    AND column_name = 'funding_rate'
                """)
            )
            exists = result.fetchone()
            
            if exists:
                print("✓ funding_rate column already exists")
            else:
                print("Adding funding_rate column...")
                await conn.execute(
                    text("""
                        ALTER TABLE trading.market_data
                        ADD COLUMN funding_rate FLOAT NULL
                    """)
                )
                print("✓ funding_rate column added successfully")
    except Exception as e:
        print(f"✗ Error: {e}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

