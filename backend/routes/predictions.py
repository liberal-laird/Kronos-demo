"""
Predictions 路由: 触发预测 / 查询预测 / 删除预测
"""
import uuid
import traceback
from datetime import date

from sanic import Blueprint
from sanic.exceptions import NotFound, BadRequest
from sanic.response import json

from backend.config import (
    DEFAULT_PRED_HORIZON,
    DEFAULT_N_PREDICTIONS,
    DEFAULT_HIST_POINTS,
    DEFAULT_VOL_WINDOW,
)
from backend.models.prediction import Prediction, PredictionPoint
from backend.services.data_fetcher import fetch_us_stock_data

predictions_bp = Blueprint("predictions", url_prefix="/api/predictions")


# --- 辅助: 将 ORM 对象序列化为 dict ---

def serialize_prediction(p: Prediction) -> dict:
    return {
        "id": str(p.id),
        "symbol": p.symbol,
        "interval": p.interval,
        "hist_points": p.hist_points,
        "pred_horizon": p.pred_horizon,
        "n_predictions": p.n_predictions,
        "last_close": float(p.last_close) if p.last_close is not None else None,
        "upside_prob": float(p.upside_prob) if p.upside_prob is not None else None,
        "vol_amp_prob": float(p.vol_amp_prob) if p.vol_amp_prob is not None else None,
        "chart_path": p.chart_path,
        "status": p.status,
        "error_message": p.error_message,
        "created_at": p.created_at.isoformat(),
    }


def serialize_point(pt: PredictionPoint) -> dict:
    return {
        "id": pt.id,
        "prediction_id": str(pt.prediction_id),
        "date": pt.date.isoformat(),
        "day_index": pt.day_index,
        "mean_close": float(pt.mean_close),
        "min_close": float(pt.min_close),
        "max_close": float(pt.max_close),
        "mean_volume": float(pt.mean_volume),
    }


# --- 路由 ---

@predictions_bp.post("/")
async def create_prediction(request):
    """
    触发一次新的预测。
    Body: {symbol, interval?, hist_points?, pred_horizon?, n_predictions?, vol_window?}
    """
    try:
        body = request.json or {}
    except Exception:
        body = {}

    symbol = (body.get("symbol") or "").upper().strip()
    if not symbol:
        raise BadRequest("symbol is required")

    interval = body.get("interval", "1d")
    hist_points = body.get("hist_points", DEFAULT_HIST_POINTS)
    pred_horizon = body.get("pred_horizon", DEFAULT_PRED_HORIZON)
    n_predictions = body.get("n_predictions", DEFAULT_N_PREDICTIONS)
    vol_window = body.get("vol_window", DEFAULT_VOL_WINDOW)

    # 1. 创建 pending 记录
    pred_id = uuid.uuid4()
    pred = await Prediction.create(
        id=pred_id,
        symbol=symbol,
        interval=interval,
        hist_points=hist_points,
        pred_horizon=pred_horizon,
        n_predictions=n_predictions,
        status="pending",
    )

    # 2. 异步执行预测（不阻塞响应）
    async def execute():
        from backend.services.predictor import run_prediction
        # 从 DB 重新获取，确保在正确的异步上下文/事务中
        p = await Prediction.filter(id=pred_id).first()
        try:
            df = await fetch_us_stock_data(symbol, hist_points, pred_horizon, vol_window)
            predictor = request.app.ctx.predictor
            result = await run_prediction(df, predictor, pred_horizon, n_predictions, vol_window)

            # 更新预测记录
            p.last_close = result["last_close"]
            p.upside_prob = result["upside_prob"]
            p.vol_amp_prob = result["vol_amp_prob"]
            p.status = "completed"

            # 存储数据点
            for pt in result["prediction_points"]:
                await PredictionPoint.create(
                    prediction=p,
                    date=date.fromisoformat(pt["date"]),
                    day_index=pt["day_index"],
                    mean_close=pt["mean_close"],
                    min_close=pt["min_close"],
                    max_close=pt["max_close"],
                    mean_volume=pt["mean_volume"],
                )
            await p.save()
            print(f"[predictions] Prediction {p.id} for {symbol} completed.")
        except Exception as e:
            print(f"[predictions] Prediction {pred_id} failed: {e}")
            traceback.print_exc()
            p.status = "failed"
            p.error_message = str(e)
            await p.save()

    request.app.add_task(execute())
    # request.app.add_task(execute())

    return json({"prediction_id": str(pred_id), "status": "pending"}, status=202)


@predictions_bp.get("/")
async def list_predictions(request):
    """查询预测列表，支持 ?symbol=AAPL&limit=20&offset=0"""
    symbol = request.args.get("symbol")
    limit = min(int(request.args.get("limit", 20)), 100)
    offset = int(request.args.get("offset", 0))

    qs = Prediction.all()
    if symbol:
        qs = qs.filter(symbol=symbol.upper())
    total = await qs.count()
    items = await qs.limit(limit).offset(offset)

    return json({
        "total": total,
        "items": [serialize_prediction(p) for p in items],
    })


@predictions_bp.get("/latest")
async def latest_prediction(request):
    """获取最新完成的预测 (含 data points 和 historical points)。"""
    symbol = (request.args.get("symbol") or "").upper()
    if not symbol:
        raise BadRequest("symbol is required")

    pred = await Prediction.filter(symbol=symbol, status="completed").first()
    if not pred:
        raise NotFound(f"No completed prediction found for {symbol}")

    # 获取预测数据点
    pts = await PredictionPoint.filter(prediction=pred).order_by("day_index")

    # 直接从小数构建序列化数据
    from decimal import Decimal
    import json as _json

    prediction_points = []
    for pt in pts:
        prediction_points.append({
            "date": pt.date.isoformat() if isinstance(pt.date, date) else str(pt.date),
            "day_index": pt.day_index,
            "mean_close": float(pt.mean_close),
            "min_close": float(pt.min_close),
            "max_close": float(pt.max_close),
            "mean_volume": float(pt.mean_volume),
        })

    # 不再存储 historical points，前端从预测数据反推
    return json({
        "prediction": serialize_prediction(pred),
        "prediction_points": prediction_points,
    })


@predictions_bp.get("/<prediction_id:str>")
async def get_prediction(request, prediction_id: str):
    """获取单个预测详情 (含 data points)。"""
    pred = await Prediction.filter(id=prediction_id).first()
    if not pred:
        raise NotFound(f"Prediction {prediction_id} not found")

    pts = await PredictionPoint.filter(prediction=pred).order_by("day_index")

    return json({
        "prediction": serialize_prediction(pred),
        "prediction_points": [serialize_point(pt) for pt in pts],
    })


@predictions_bp.delete("/<prediction_id:str>")
async def delete_prediction(request, prediction_id: str):
    """删除预测及其关联数据点。"""
    pred = await Prediction.filter(id=prediction_id).first()
    if not pred:
        raise NotFound(f"Prediction {prediction_id} not found")

    await PredictionPoint.filter(prediction=pred).delete()
    await pred.delete()
    return json({"message": "deleted"}, status=200)
