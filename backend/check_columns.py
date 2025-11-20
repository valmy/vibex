import asyncio
import os

os.environ["ENVIRONMENT"] = "testing"
from sqlalchemy import text

from app.db.session import get_session_factory, init_db


async def check_columns():
    await init_db()
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            text(
                "SELECT column_name FROM information_schema.columns WHERE table_schema = 'trading' AND table_name = 'performance_metrics'"
            )
        )
        columns = [row[0] for row in result.fetchall()]
        print(f"Columns in performance_metrics: {columns}")
        if "max_drawdown" in columns:
            print("max_drawdown exists!")
        else:
            print("max_drawdown MISSING!")


if __name__ == "__main__":
    asyncio.run(check_columns())
