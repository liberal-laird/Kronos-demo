"""
定时任务调度器: 每个交易日 UTC 21:05 自动预测数据库中的股票
"""
import uuid
import traceback
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.config import SCHEDULE_HOUR_UTC, SCHEDULE_MINUTE_UTC
from backend.models.prediction import Prediction, PredictionPoint
from backend.models.stock import Stock


scheduler = AsyncIOScheduler(timezone="UTC")


async def scheduled_predict(app):
    """定时执行的预测任务。从数据库读取启用的股票。"""
    stocks = await Stock.filter(enabled=True)
    symbols = [s.symbol for s in stocks]
    print(f"[scheduler] Running scheduled prediction for {len(symbols)} symbols: {symbols}")
    for symbol in symbols:
        try:
            from backend.services.data_fetcher import fetch_us_stock_data
            from backend.services.predictor import run_prediction

            predictor = app.ctx.predictor
            df = await fetch_us_stock_data(symbol)
            result = await run_prediction(df, predictor)

            pred = await Prediction.create(
                id=uuid.uuid4(),
                symbol=symbol,
                interval="1d",
                last_close=result["last_close"],
                upside_prob=result["upside_prob"],
                vol_amp_prob=result["vol_amp_prob"],
                status="completed",
            )

            for pt in result["prediction_points"]:
                await PredictionPoint.create(
                    prediction=pred,
                    date=date.fromisoformat(pt["date"]),
                    day_index=pt["day_index"],
                    mean_close=pt["mean_close"],
                    min_close=pt["min_close"],
                    max_close=pt["max_close"],
                    mean_volume=pt["mean_volume"],
                )
            print(f"[scheduler] {symbol}: prediction {pred.id} completed.")
        except Exception as e:
            print(f"[scheduler] {symbol}: FAILED - {e}")
            traceback.print_exc()
            await Prediction.create(
                id=uuid.uuid4(),
                symbol=symbol,
                interval="1d",
                status="failed",
                error_message=str(e),
            )


def start_scheduler(app):
    """启动定时任务调度器。"""
    scheduler.add_job(
        scheduled_predict,
        "cron",
        args=[app],
        hour=SCHEDULE_HOUR_UTC,
        minute=SCHEDULE_MINUTE_UTC,
        id="daily_predict",
        replace_existing=True,
    )
    scheduler.start()
    print(
        f"[scheduler] Started. Will run daily at "
        f"{SCHEDULE_HOUR_UTC:02d}:{SCHEDULE_MINUTE_UTC:02d} UTC."
    )
