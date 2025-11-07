#!/usr/bin/env python
"""Check if market data exists in the database."""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env.local if it exists (for local testing)
env_local = Path(__file__).parent / ".env.local"
if env_local.exists():
    load_dotenv(env_local, override=True)
else:
    load_dotenv()

from sqlalchemy import select, func
from app.db.session import get_session_factory, init_db
from app.models.market_data import MarketData


async def check_market_data():
    """Check if market data exists in the database."""
    # Initialize database first
    await init_db()
    engine = get_session_factory()
    
    async with engine() as session:
        # Count total market data records
        count_result = await session.execute(select(func.count(MarketData.id)))
        total_count = count_result.scalar()
        
        print(f"Total market data records: {total_count}")
        
        if total_count == 0:
            print("❌ No market data found in database")
            return False
        
        # Get sample data
        result = await session.execute(
            select(MarketData)
            .order_by(MarketData.time.desc())
            .limit(5)
        )
        samples = result.scalars().all()
        
        print(f"\n✅ Found {total_count} market data records")
        print("\nRecent samples:")
        for sample in samples:
            print(f"  - {sample.symbol} @ {sample.time}: {sample.close}")
        
        return True


if __name__ == "__main__":
    asyncio.run(check_market_data())

