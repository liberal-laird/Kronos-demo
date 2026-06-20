"""
Stock 路由: 获取/添加/删除股票（存入数据库）
"""
from sanic import Blueprint
from sanic.exceptions import NotFound, BadRequest
from sanic.response import json

from backend.models.stock import Stock

stocks_bp = Blueprint("stocks", url_prefix="/api/stocks")

# 种子数据 — 首次启动时自动写入
SEED_SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
    "META", "NVDA", "NFLX", "AMD", "INTC",
    "BABA", "JD", "SQ", "SNAP", "UBER",
    "PYPL", "DIS", "BA", "JPM", "GS",
]


@stocks_bp.listener("before_server_start")
async def seed_stocks(app, loop):
    """确保种子数据存在。"""
    for sym in SEED_SYMBOLS:
        await Stock.get_or_create(symbol=sym)
    print(f"[stocks] Seeded {len(SEED_SYMBOLS)} symbols.")


@stocks_bp.get("/")
async def list_stocks(request):
    """返回所有启用的股票列表。"""
    stocks = await Stock.filter(enabled=True).order_by("symbol")
    return json({"stocks": [s.symbol for s in stocks]})


@stocks_bp.post("/")
async def add_stock(request):
    """添加自定义股票。Body: {symbol, name?}"""
    try:
        body = request.json or {}
    except Exception:
        body = {}

    symbol = (body.get("symbol") or "").upper().strip()
    if not symbol:
        raise BadRequest("symbol is required")

    # 检查长度/格式
    if len(symbol) > 10 or not symbol.isascii():
        raise BadRequest("Invalid symbol format")

    name = body.get("name") or None

    stock, created = await Stock.get_or_create(
        symbol=symbol,
        defaults={"name": name, "enabled": True},
    )
    if not created:
        # 更新 name 如果提供了
        if name and stock.name != name:
            stock.name = name
            await stock.save()

    return json({
        "symbol": stock.symbol,
        "name": stock.name,
        "enabled": stock.enabled,
        "created": created,
    }, status=201 if created else 200)


@stocks_bp.delete("/<symbol:str>")
async def delete_stock(request, symbol: str):
    """删除股票（或设为禁用，保留历史预测）。"""
    symbol = symbol.upper()
    stock = await Stock.filter(symbol=symbol).first()
    if not stock:
        raise NotFound(f"Stock '{symbol}' not found")

    # 软删除: 设为禁用而非删除记录
    stock.enabled = False
    await stock.save()
    return json({"message": f"Stock '{symbol}' disabled", "symbol": symbol})

