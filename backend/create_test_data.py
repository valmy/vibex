#!/usr/bin/env python3
"""Create test data for E2E tests."""

import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def create_test_data():
    """Create test data for E2E tests."""
    engine = create_async_engine(
        "postgresql+asyncpg://trading_user:trading_password@localhost:5432/trading_db"
    )
    
    try:
        async with engine.begin() as conn:
            # Check existing data
            result = await conn.execute(text("SELECT COUNT(*) FROM trading.accounts"))
            account_count = result.fetchone()[0]
            print(f"Existing accounts: {account_count}")
            
            result = await conn.execute(text("SELECT COUNT(*) FROM trading.market_data"))
            market_count = result.fetchone()[0]
            print(f"Existing market data: {market_count}")
            
            # Create test user if not exists
            result = await conn.execute(text("""
                SELECT id FROM trading.users WHERE address = '0xCfbEE662dc66475Bf5F3b7203b4b6EE03028952F'
            """))
            user = result.fetchone()
            if user:
                user_id = user[0]
                print(f"Test user already exists: {user_id}")
            else:
                print("Creating test user...")
                result = await conn.execute(text("""
                    INSERT INTO trading.users (address, created_at, updated_at)
                    VALUES ('0xCfbEE662dc66475Bf5F3b7203b4b6EE03028952F', NOW(), NOW())
                    RETURNING id
                """))
                user_id = result.fetchone()[0]
                print(f"Test user created: {user_id}")
            
            # Create test account if not exists
            result = await conn.execute(text("""
                SELECT id FROM trading.accounts WHERE id = 1
            """))
            account = result.fetchone()
            if account:
                print("Test account already exists: 1")
            else:
                print("Creating test account...")
                await conn.execute(text("""
                    INSERT INTO trading.accounts
                    (id, user_id, name, description, status, leverage, max_position_size_usd,
                     risk_per_trade, is_paper_trading, is_multi_account, is_enabled, created_at, updated_at)
                    VALUES (1, :user_id, 'Test Account', 'Test trading account', 'active', 2.0, 10000.0,
                            0.02, true, false, true, NOW(), NOW())
                """), {"user_id": user_id})
                print("Test account created: 1")
            
            # Check if BTCUSDT market data exists
            result = await conn.execute(text("""
                SELECT COUNT(*) FROM trading.market_data WHERE symbol = 'BTCUSDT'
            """))
            btc_count = result.fetchone()[0]
            print(f"BTCUSDT market data records: {btc_count}")
            
            if btc_count == 0:
                print("Creating BTCUSDT market data...")
                # Create 100 candles of BTCUSDT data with 5m interval (as expected by context builder)
                # Use naive datetime (database expects TIMESTAMP WITHOUT TIME ZONE)
                now = datetime.now()
                for i in range(100):
                    # Create 5-minute candles going back 500 minutes (8.3 hours) from now
                    timestamp = now - timedelta(minutes=(100-i) * 5)
                    price = 50000 + (i * 10)  # Gradually increasing price
                    await conn.execute(text("""
                        INSERT INTO trading.market_data
                        (time, symbol, interval, open, high, low, close, volume,
                         quote_asset_volume, number_of_trades, taker_buy_base_asset_volume,
                         taker_buy_quote_asset_volume, funding_rate)
                        VALUES (:time, 'BTCUSDT', '5m', :price, :price, :price, :price,
                                100000, 5000000000, 1000, 50000, 2500000, 0.0001)
                    """), {
                        "time": timestamp,
                        "price": price,
                    })
                print("BTCUSDT market data created")
            
            # Check if ETHUSDT market data exists
            result = await conn.execute(text("""
                SELECT COUNT(*) FROM trading.market_data WHERE symbol = 'ETHUSDT'
            """))
            eth_count = result.fetchone()[0]
            print(f"ETHUSDT market data records: {eth_count}")
            
            if eth_count == 0:
                print("Creating ETHUSDT market data...")
                # Create 100 candles of ETHUSDT data with 5m interval
                # Use naive datetime (database expects TIMESTAMP WITHOUT TIME ZONE)
                now = datetime.now()
                for i in range(100):
                    # Create 5-minute candles going back 500 minutes from now
                    timestamp = now - timedelta(minutes=(100-i) * 5)
                    price = 3000 + (i * 5)  # Gradually increasing price
                    await conn.execute(text("""
                        INSERT INTO trading.market_data
                        (time, symbol, interval, open, high, low, close, volume,
                         quote_asset_volume, number_of_trades, taker_buy_base_asset_volume,
                         taker_buy_quote_asset_volume, funding_rate)
                        VALUES (:time, 'ETHUSDT', '5m', :price, :price, :price, :price,
                                50000, 150000000, 500, 25000, 7500000, 0.00005)
                    """), {
                        "time": timestamp,
                        "price": price,
                    })
                print("ETHUSDT market data created")
            
            print("\n✓ Test data setup complete!")
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_test_data())

