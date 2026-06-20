"""
update_predictions_us_stock.py
基于 update_predictions.py 的方法，使用 Kronos 模型对美股进行 1D 周期的预测。

主要改动：
- 数据源从 Binance 替换为 yfinance（美股）
- 周期从 1h 替换为 1D
- 默认标的从 BTCUSDT 替换为 AAPL
- 预测 horizon 从 24 根 bar 调整为适合日线的长度（例如未来 10 个交易日）
"""

import gc
import os
import re
import subprocess
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import yfinance as yf

from model import KronosTokenizer, Kronos, KronosPredictor

# --- Configuration ---
Config = {
    "REPO_PATH": Path(__file__).parent.resolve(),
    "MODEL_PATH": "hf_model",

    # --- 美股设定 ---
    "SYMBOL": "CRCL",                # 美股 ticker，如 AAPL, MSFT, GOOGL, TSLA, AMZN ...
    "INTERVAL": "1d",                # 日线周期

    # --- 预测参数 ---
    "HIST_POINTS": 252,              # 历史 K 线数量（约一年的交易日）
    "PRED_HORIZON": 10,              # 预测未来多少个交易日
    "N_PREDICTIONS": 30,             # 采样数量（概率预测的轨迹数）
    "VOL_WINDOW": 21,                # 波动率计算窗口（约一个月的交易日）

    # --- 自动提交 ---
    "AUTO_COMMIT_SUMMARY": False,    # 是否自动生成并提交预测摘要
}


def load_model():
    """加载 Kronos 模型和 tokenizer。"""
    print("Loading Kronos model...")
    tokenizer = KronosTokenizer.from_pretrained(
        "NeoQuasar/Kronos-Tokenizer-2k",
        cache_dir=Config["MODEL_PATH"],
    )
    model = Kronos.from_pretrained(
        "NeoQuasar/Kronos-base",
        cache_dir=Config["MODEL_PATH"],
    )
    tokenizer.eval()
    model.eval()
    predictor = KronosPredictor(model, tokenizer, device="cpu", max_context=512)
    print("Model loaded successfully.")
    return predictor


def fetch_us_stock_data():
    """
    使用 yfinance 拉取美股日线数据。
    返回与原始代码兼容的 DataFrame：
        timestamps | open | high | low | close | volume | amount

    amount 使用 close * volume 近似。
    """
    symbol = Config["SYMBOL"]
    # 多取一些，确保有足够的历史数据
    total_bars = Config["HIST_POINTS"] + Config["VOL_WINDOW"] + Config["PRED_HORIZON"]
    period_days = total_bars + 20  # 多拉一点防止非交易日的缺失

    print(f"Fetching ~{total_bars} daily bars for {symbol} from Yahoo Finance...")

    ticker = yf.Ticker(symbol)

    # 用 period 拉取，避免 start / end 受到非交易日的干扰
    # yfinance 的 period 参数：'1y', '2y', '5y', '10y' … 这里根据需要的天数选择
    if period_days <= 400:
        period = "2y"
    elif period_days <= 1250:
        period = "5y"
    else:
        period = "10y"

    df = ticker.history(period=period, interval="1d")

    if df.empty:
        raise RuntimeError(f"No data returned for symbol '{symbol}'. Check the ticker.")

    # yfinance 的列: Open, High, Low, Close, Volume (已经是 capital case)；index 是日期
    df = df.rename_axis("timestamps").reset_index()
    df["timestamps"] = pd.to_datetime(df["timestamps"])

    # 统一列名
    df = df.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )

    # amount ≈ 成交额 (close * volume)
    df["amount"] = df["close"] * df["volume"]

    # 保留需要的列
    needed_cols = ["timestamps", "open", "high", "low", "close", "volume", "amount"]
    df = df[needed_cols]

    # 只取最后 total_bars 条（防止取到过多数据）
    df = df.tail(total_bars).reset_index(drop=True)

    # 类型转换
    for col in ["open", "high", "low", "close", "volume", "amount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 检查是否有 NaN
    if df.isnull().any().any():
        print("Warning: Some values are NaN; dropping rows with NaN...")
        df = df.dropna().reset_index(drop=True)

    # 确保时间戳为 DatetimeIndex（但没有 set_index，因为原代码依赖 timestamps 列）
    print(f"Data fetched successfully. {len(df)} rows from {df['timestamps'].min().date()} to {df['timestamps'].max().date()}.")
    return df


def make_prediction(df, predictor):
    """
    使用 Kronos 模型生成概率预测。
    日线版本——预测 frequency 为 'D'（每个自然日），yfinance 数据没有盘中时间信息，
    所以用 'D' 频率生成未来的时间索引。
    """
    last_timestamp = df["timestamps"].max()
    # 日线预测，取下一个交易日作为起点
    start_new_range = last_timestamp + pd.Timedelta(days=1)
    new_timestamps_index = pd.date_range(
        start=start_new_range,
        periods=Config["PRED_HORIZON"],
        freq="D",                    # 日频率
    )
    y_timestamp = pd.Series(new_timestamps_index, name="y_timestamp")
    x_timestamp = df["timestamps"]
    x_df = df[["open", "high", "low", "close", "volume", "amount"]]

    with torch.no_grad():
        print("Making main prediction (T=1.0)...")
        begin_time = time.time()
        close_preds_main, volume_preds_main = predictor.predict(
            df=x_df,
            x_timestamp=x_timestamp,
            y_timestamp=y_timestamp,
            pred_len=Config["PRED_HORIZON"],
            T=1.0,
            top_p=0.95,
            sample_count=Config["N_PREDICTIONS"],
            verbose=True,
        )
        print(f"Main prediction completed in {time.time() - begin_time:.2f} seconds.")

        # 波动率预测——和原代码保持一致，复用 main prediction
        close_preds_volatility = close_preds_main

    return close_preds_main, volume_preds_main, close_preds_volatility


def calculate_metrics(hist_df, close_preds_df, v_close_preds_df):
    """
    计算 horizon 内的上行概率和波动率放大概率。

    - upsided_prob:   预测 horizon 末价格高于当前收盘价的概率
    - vol_amp_prob:   预测波动率 > 历史波动率的概率
    """
    last_close = hist_df["close"].iloc[-1]

    # 1. 上行概率
    final_day_preds = close_preds_df.iloc[-1]
    upside_prob = (final_day_preds > last_close).mean()

    # 2. 波动率放大概率
    hist_log_returns = np.log(hist_df["close"] / hist_df["close"].shift(1))
    historical_vol = hist_log_returns.iloc[-Config["VOL_WINDOW"]:].std()

    amplification_count = 0
    for col in v_close_preds_df.columns:
        full_sequence = pd.concat(
            [pd.Series([last_close]), v_close_preds_df[col]]
        ).reset_index(drop=True)
        pred_log_returns = np.log(full_sequence / full_sequence.shift(1))
        predicted_vol = pred_log_returns.std()
        if predicted_vol > historical_vol:
            amplification_count += 1

    vol_amp_prob = amplification_count / len(v_close_preds_df.columns)

    print(
        f"Upside Probability ({Config['PRED_HORIZON']}D): {upside_prob:.2%}, "
        f"Volatility Amplification Probability: {vol_amp_prob:.2%}"
    )
    return upside_prob, vol_amp_prob


def create_plot(hist_df, close_preds_df, volume_preds_df):
    """生成并保存预测图表。"""
    print("Generating forecast chart...")
    fig, (ax1, ax2) = plt.subplots(
        2, 1,
        figsize=(15, 10),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )

    # 因为日线，推时时间直接用 timedelta(days=...)
    hist_time = hist_df["timestamps"]
    last_hist_time = hist_time.iloc[-1]
    pred_time = pd.to_datetime([
        last_hist_time + timedelta(days=i + 1) for i in range(len(close_preds_df))
    ])

    # --- 价格子图 ---
    ax1.plot(
        hist_time, hist_df["close"],
        color="royalblue", label="Historical Price", linewidth=1.5,
    )
    mean_preds = close_preds_df.mean(axis=1)
    ax1.plot(
        pred_time, mean_preds,
        color="darkorange", linestyle="-", label="Mean Forecast",
    )
    ax1.fill_between(
        pred_time,
        close_preds_df.min(axis=1),
        close_preds_df.max(axis=1),
        color="darkorange", alpha=0.2,
        label="Forecast Range (Min-Max)",
    )
    ax1.set_title(
        f"{Config['SYMBOL']} US Stock Probabilistic Price & Volume Forecast "
        f"(Next {Config['PRED_HORIZON']} Trading Days)",
        fontsize=16, weight="bold",
    )
    ax1.set_ylabel("Price (USD)")
    ax1.legend()
    ax1.grid(True, which="both", linestyle="--", linewidth=0.5)

    # --- 成交量子图 ---
    ax2.bar(
        hist_time, hist_df["volume"],
        color="skyblue", label="Historical Volume", width=0.6,
    )
    ax2.bar(
        pred_time, volume_preds_df.mean(axis=1),
        color="sandybrown", label="Mean Forecasted Volume", width=0.6,
    )
    ax2.set_ylabel("Volume")
    ax2.set_xlabel("Date")
    ax2.legend()
    ax2.grid(True, which="both", linestyle="--", linewidth=0.5)

    # 分隔线
    separator_time = hist_time.iloc[-1] + timedelta(hours=12)
    for ax in [ax1, ax2]:
        ax.axvline(
            x=separator_time, color="red", linestyle="--",
            linewidth=1.5, label="_nolegend_",
        )
        ax.tick_params(axis="x", rotation=30)

    fig.tight_layout()
    chart_path = Config["REPO_PATH"] / "prediction_chart_us_stock.png"
    fig.savefig(chart_path, dpi=120)
    plt.close(fig)
    print(f"Chart saved to: {chart_path}")




def print_summary(hist_df, close_preds_df, upside_prob, vol_amp_prob):
    """打印预测摘要。"""
    last_close = hist_df["close"].iloc[-1]
    mean_final = close_preds_df.iloc[-1].mean()
    pct_change = (mean_final / last_close - 1) * 100

    print("\n" + "=" * 60)
    print(f"  {Config['SYMBOL']} {Config['PRED_HORIZON']}-Day Forecast Summary")
    print("=" * 60)
    print(f"  Last Close           : ${last_close:.2f}")
    print(f"  Predicted Mean Close : ${mean_final:.2f}  ({pct_change:+.2f}%)")
    print(f"  Upside Probability   : {upside_prob:.1%}")
    print(f"  Vol Amplification    : {vol_amp_prob:.1%}")
    print("=" * 60 + "\n")


def main_task(model):
    """执行一次完整的更新周期。"""
    print(
        "\n" + "=" * 60 +
        f"\nStarting US Stock update task at {datetime.now(timezone.utc)}\n" +
        "=" * 60
    )

    # 1. 拉取美股日线数据
    df_full = fetch_us_stock_data()

    # 2. 模型使用最后一条 bar 之前的所有数据（预留最后一条用于对齐）
    df_for_model = df_full.iloc[:-1]

    # 3. 预测
    close_preds, volume_preds, v_close_preds = make_prediction(df_for_model, model)

    # 4. 计算指标
    hist_df_for_plot = df_for_model.tail(Config["HIST_POINTS"])
    hist_df_for_metrics = df_for_model.tail(Config["VOL_WINDOW"])

    upside_prob, vol_amp_prob = calculate_metrics(
        hist_df_for_metrics, close_preds, v_close_preds,
    )

    # 5. 画图
    create_plot(hist_df_for_plot, close_preds, volume_preds)


    # 7. 打印摘要
    print_summary(hist_df_for_metrics, close_preds, upside_prob, vol_amp_prob)

    # --- 内存清理 ---
    del df_full, df_for_model, close_preds, volume_preds, v_close_preds
    del hist_df_for_plot, hist_df_for_metrics
    gc.collect()
    # ---

    print(
        "-" * 60 +
        "\n--- Task completed successfully ---\n" +
        "-" * 60 + "\n"
    )


def run_scheduler(model):
    """
    一个持续运行日线任务的调度器。

    因为美股日线每天只需在收盘后运行一次，这里默认在
    UTC 21:00（美东 16:00 / 夏令时美东 17:00）附近执行。
    """
    print("US Stock daily scheduler started.")
    print(f"Will run prediction once per day at ~21:05 UTC (after US market close).")
    print(f"Symbol: {Config['SYMBOL']}, Interval: {Config['INTERVAL']}")

    while True:
        now = datetime.now(timezone.utc)
        # 目标：下一个 UTC 21:05
        next_run_time = now.replace(hour=21, minute=5, second=0, microsecond=0)
        if now >= next_run_time:
            next_run_time += timedelta(days=1)

        sleep_seconds = (next_run_time - now).total_seconds()
        if sleep_seconds > 0:
            print(
                f"Current time: {now:%Y-%m-%d %H:%M:%S UTC}. "
                f"Next run at: {next_run_time:%Y-%m-%d %H:%M:%S UTC}. "
                f"Waiting for {sleep_seconds:.0f} seconds..."
            )
            time.sleep(sleep_seconds)

        try:
            main_task(model)
        except Exception as e:
            print("\n!!!!!! A critical error occurred in the main task !!!!!!!")
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            print("Retrying in 5 minutes...")
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n")
            time.sleep(300)


if __name__ == "__main__":
    model_path = Path(Config["MODEL_PATH"])
    model_path.mkdir(parents=True, exist_ok=True)

    loaded_model = load_model()
    # 启动时立即运行一次
    main_task(loaded_model)
    # 然后开始日线调度
    run_scheduler(loaded_model)
