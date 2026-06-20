"""
Kronos-demo 后端配置
"""
import os
from pathlib import Path

# --- 项目路径 ---
BASE_DIR = Path(__file__).parent.parent.resolve()
MODEL_PATH = BASE_DIR / "hf_model"

# --- Kronos 预测默认参数 ---
DEFAULT_SYMBOL = "CRCL"
DEFAULT_INTERVAL = "1d"
DEFAULT_HIST_POINTS = 252
DEFAULT_PRED_HORIZON = 5
DEFAULT_N_PREDICTIONS = 30
DEFAULT_VOL_WINDOW = 21

# --- 股票种子数据 (首次启动自动写入数据库) ---
SEED_SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
    "META", "NVDA", "NFLX", "AMD", "INTC",
    "BABA", "JD", "SQ", "SNAP", "UBER",
    "PYPL", "DIS", "BA", "JPM", "GS",
]
# 注意: PRESET_STOCKS 已废弃，改为从数据库读取
# 种子数据定义在 backend/routes/stocks.py

# --- 数据库配置 (环境变量优先) ---
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_NAME = os.getenv("DB_NAME", "kronos_demo")

TORTOISE_ORM = {
    "connections": {
        "default": {
            "engine": "tortoise.backends.asyncpg",
            "credentials": {
                "host": DB_HOST,
                "port": DB_PORT,
                "user": DB_USER,
                "password": DB_PASSWORD,
                "database": DB_NAME,
            },
        },
    },
    "apps": {
        "models": {
            "models": ["backend.models.prediction", "backend.models.stock"],
            "default_connection": "default",
        },
    },
    "use_tz": True,
    "timezone": "UTC",
}

# --- Sanic 服务配置 ---
SANIC_HOST = os.getenv("SANIC_HOST", "0.0.0.0")
SANIC_PORT = int(os.getenv("SANIC_PORT", "8000"))
SANIC_DEBUG = os.getenv("SANIC_DEBUG", "true").lower() == "true"

# --- 定时任务: 美股收盘后自动预测的时间 (UTC) ---
SCHEDULE_HOUR_UTC = 21
SCHEDULE_MINUTE_UTC = 5
# 定时任务从数据库读取启用的股票，不再硬编码
