import asyncio
import os

# Set testing environment before importing app modules
os.environ["ENVIRONMENT"] = "testing"

from app.db.session import get_session_factory, init_db
from app.services.market_data.service import MarketDataService


async def main():
    """Sync market data for BTCUSDT and ETHUSDT."""
    await init_db()
    session_factory = get_session_factory()
    async with session_factory() as session:
        service = MarketDataService()
        symbols = ["BTCUSDT", "ETHUSDT"]
        timeframes = ["5m", "4h"]
        for symbol in symbols:
            for timeframe in timeframes:
                print(f"Syncing {symbol} for {timeframe}...")
                await service.sync_market_data(session, symbol, timeframe)
    print("Data sync complete.")


if __name__ == "__main__":
    asyncio.run(main())
