"""
Kronos-demo Sanic 后端入口
"""
from sanic import Sanic
from sanic.response import json
from tortoise.contrib.sanic import register_tortoise

from backend.config import TORTOISE_ORM, SANIC_HOST, SANIC_PORT, SANIC_DEBUG

app = Sanic("KronosDemo")


@app.listener("before_server_start")
async def setup_predictor(app):
    """服务启动前加载 Kronos 模型、种子股票、启动定时任务。"""
    from backend.services.predictor import get_predictor
    app.ctx.predictor = await get_predictor()
    print("[server] Kronos predictor loaded.")

    # 种子股票 (放在 server 启动时，确保表已创建)
    from backend.models.stock import Stock
    seed = ["AAPL","MSFT","GOOGL","AMZN","TSLA","META","NVDA","NFLX","AMD","INTC","BABA","JD","SQ","SNAP","UBER","PYPL","DIS","BA","JPM","GS"]
    for sym in seed:
        await Stock.get_or_create(symbol=sym)
    print(f"[server] Seeded {len(seed)} stocks.")

    from backend.tasks.scheduler import start_scheduler
    start_scheduler(app)


@app.listener("after_server_stop")
async def cleanup_app(app):
    """服务停止后清理。"""
    print("[server] Shutting down.")


# --- 初始化 Tortoise ORM ---
register_tortoise(
    app,
    config=TORTOISE_ORM,
    generate_schemas=True,  # 开发环境自动建表
)

# --- 注册路由 ---
from backend.routes.stocks import stocks_bp
from backend.routes.predictions import predictions_bp

app.blueprint(stocks_bp)
app.blueprint(predictions_bp)


# --- CORS (开发阶段宽松) ---
@app.middleware("response")
async def add_cors_headers(request, response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"


@app.middleware("request")
async def handle_options(request):
    if request.method == "OPTIONS":
        return json(None, status=204)


# --- 健康检查 ---
@app.get("/api/health")
async def health(request):
    return json({"status": "ok"})


if __name__ == "__main__":
    app.run(
        host=SANIC_HOST,
        port=SANIC_PORT,
        debug=SANIC_DEBUG,
        access_log=True,
        single_process=True,
    )
