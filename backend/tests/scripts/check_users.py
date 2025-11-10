import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+asyncpg://trading_user:trading_password@localhost:5432/trading_db"

async def check_users():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with async_session() as session:
            result = await session.execute(text("SELECT * FROM trading.users LIMIT 20;"))
            rows = result.fetchall()
            
            if rows:
                # Get column names
                columns = result.keys()
                print(f"Found {len(rows)} users:\n")
                print("Columns:", list(columns))
                print("\n" + "="*100)
                
                for i, row in enumerate(rows, 1):
                    print(f"\nUser {i}:")
                    for col, val in zip(columns, row):
                        print(f"  {col}: {val}")
            else:
                print("No users found")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await engine.dispose()

asyncio.run(check_users())

