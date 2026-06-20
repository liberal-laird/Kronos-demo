"""
数据库初始化脚本 — 在线上部署前手动执行：
  python init_db.py
"""
import asyncio
import sys

from tortoise import Tortoise
from backend.config import TORTOISE_ORM


async def init():
    print("[init_db] Connecting...")
    await Tortoise.init(config=TORTOISE_ORM)

    print("[init_db] Creating tables...")
    await Tortoise.generate_schemas(safe=True)

    print("[init_db] Seeding stocks...")
    from backend.models.stock import Stock
    seed = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
        "META", "NVDA", "NFLX", "AMD", "INTC",
        "BABA", "JD", "SQ", "SNAP", "UBER",
        "PYPL", "DIS", "BA", "JPM", "GS",
    ]
    for sym in seed:
        _, created = await Stock.get_or_create(symbol=sym)
        if created:
            print(f"  + {sym}")

    print("[init_db] Done — all tables and seed data ready.")
    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(init())
