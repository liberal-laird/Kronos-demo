"""
Kronos 预测服务: 模型加载 + 执行预测 + 计算指标
"""
import asyncio
import gc
import time
from datetime import timedelta
from typing import Any, Dict

import numpy as np
import pandas as pd
import torch

from backend.config import MODEL_PATH, DEFAULT_N_PREDICTIONS, DEFAULT_VOL_WINDOW

# 全局 model 缓存
_predictor = None


async def get_predictor():
    """获取/初始化 KronosPredictor 全局单例（在子线程中加载以避免阻塞事件循环）。"""
    global _predictor
    if _predictor is not None:
        return _predictor
    _predictor = await asyncio.to_thread(_load_model)
    return _predictor


def _load_model():
    """在子线程中加载 Kronos 模型和 tokenizer（同步操作）。"""
    from model import KronosTokenizer, Kronos, KronosPredictor

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[predictor] Loading Kronos model on {device}...")
    tokenizer = KronosTokenizer.from_pretrained(
        "NeoQuasar/Kronos-Tokenizer-2k",
        cache_dir=str(MODEL_PATH),
    )
    model = Kronos.from_pretrained(
        "NeoQuasar/Kronos-base",
        cache_dir=str(MODEL_PATH),
    )
    tokenizer.eval()
    model.eval()
    instance = KronosPredictor(model, tokenizer, device=device, max_context=512)
    print(f"[predictor] Kronos model loaded successfully on {device}.")
    return instance


async def run_prediction(
    df: pd.DataFrame,
    predictor,
    pred_horizon: int = 10,
    n_predictions: int = DEFAULT_N_PREDICTIONS,
    vol_window: int = DEFAULT_VOL_WINDOW,
) -> Dict[str, Any]:
    """
    执行 Kronos 预测并返回结构化结果。
    因为 PyTorch 推理是同步阻塞的，放在线程池中执行。
    """
    return await asyncio.to_thread(
        _run_prediction_sync, df, predictor, pred_horizon, n_predictions, vol_window
    )


def _run_prediction_sync(
    df: pd.DataFrame,
    predictor,
    pred_horizon: int,
    n_predictions: int,
    vol_window: int,
) -> Dict[str, Any]:
    """同步执行预测逻辑。"""
    # 预留最后一条 bar 用于对齐
    df_for_model = df.iloc[:-1]

    last_timestamp = df_for_model["timestamps"].max()
    start_new_range = last_timestamp + pd.Timedelta(days=1)
    y_timestamp = pd.Series(
        pd.date_range(start=start_new_range, periods=pred_horizon, freq="D"),
        name="y_timestamp",
    )
    x_timestamp = df_for_model["timestamps"]
    x_df = df_for_model[["open", "high", "low", "close", "volume", "amount"]]

    with torch.no_grad():
        print(f"[predictor] Making prediction (T=1.0, samples={n_predictions})...")
        begin = time.time()
        close_preds_df, volume_preds_df = predictor.predict(
            df=x_df,
            x_timestamp=x_timestamp,
            y_timestamp=y_timestamp,
            pred_len=pred_horizon,
            T=1.0,
            top_p=0.95,
            sample_count=n_predictions,
            verbose=True,
        )
        v_close_preds_df = close_preds_df  # 复用
        print(f"[predictor] Prediction completed in {time.time() - begin:.2f}s")

    # 计算指标
    last_close = float(df_for_model["close"].iloc[-1])
    upside_prob, vol_amp_prob = _calculate_metrics(
        df_for_model, close_preds_df, v_close_preds_df, vol_window
    )

    # 构建日期-数据点列表
    points = []
    pred_dates = [
        (last_timestamp + timedelta(days=i + 1)).date()
        for i in range(len(close_preds_df))
    ]
    for i, d in enumerate(pred_dates):
        row = close_preds_df.iloc[i]
        vol_row = volume_preds_df.iloc[i]
        points.append({
            "date": d.isoformat(),  # 返回日期字符串
            "day_index": i + 1,
            "mean_close": float(row.mean()),
            "min_close": float(row.min()),
            "max_close": float(row.max()),
            "mean_volume": float(vol_row.mean()),
        })

    # 样式: 历史数据点 (最后 pred_horizon*3 天用于前端绘图)
    hist_window_for_plot = min(len(df_for_model), pred_horizon * 6)
    hist_df = df_for_model.tail(hist_window_for_plot)
    historical_points = []
    for _, row in hist_df.iterrows():
        historical_points.append({
            "date": row["timestamps"].to_pydatetime().date().isoformat(),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["volume"]),
        })

    # 清理
    del close_preds_df, volume_preds_df, v_close_preds_df, df_for_model
    gc.collect()

    return {
        "last_close": last_close,
        "upside_prob": round(upside_prob, 4),
        "vol_amp_prob": round(vol_amp_prob, 4),
        "prediction_points": points,
        "historical_points": historical_points,
    }


def _calculate_metrics(
    hist_df: pd.DataFrame,
    close_preds_df: pd.DataFrame,
    v_close_preds_df: pd.DataFrame,
    vol_window: int,
):
    """计算上行概率和波动率放大概率。"""
    last_close = hist_df["close"].iloc[-1]

    # 上行概率
    final_day_preds = close_preds_df.iloc[-1]
    upside_prob = (final_day_preds > last_close).mean()

    # 波动率放大概率
    hist_log_returns = np.log(hist_df["close"] / hist_df["close"].shift(1))
    historical_vol = hist_log_returns.iloc[-vol_window:].std()

    amplification_count = 0
    for col in v_close_preds_df.columns:
        full_sequence = pd.concat([
            pd.Series([last_close]), v_close_preds_df[col]
        ]).reset_index(drop=True)
        pred_log_returns = np.log(full_sequence / full_sequence.shift(1))
        predicted_vol = pred_log_returns.std()
        if predicted_vol > historical_vol:
            amplification_count += 1

    vol_amp_prob = amplification_count / len(v_close_preds_df.columns)
    return float(upside_prob), float(vol_amp_prob)
