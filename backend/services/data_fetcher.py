"""
数据获取服务: 从 yfinance 拉取美股日线数据
"""
import pandas as pd
import yfinance as yf

from backend.config import DEFAULT_PRED_HORIZON, DEFAULT_VOL_WINDOW


async def fetch_us_stock_data(
    symbol: str,
    hist_points: int = 252,
    pred_horizon: int = DEFAULT_PRED_HORIZON,
    vol_window: int = DEFAULT_VOL_WINDOW,
) -> pd.DataFrame:
    """
    使用 yfinance 拉取美股日线数据。
    返回 DataFrame: timestamps | open | high | low | close | volume | amount
    """
    total_bars = hist_points + vol_window + pred_horizon
    period_days = total_bars + 20

    ticker = yf.Ticker(symbol)

    if period_days <= 400:
        period = "2y"
    elif period_days <= 1250:
        period = "5y"
    else:
        period = "10y"

    df = ticker.history(period=period, interval="1d")

    if df.empty:
        raise RuntimeError(f"No data returned for symbol '{symbol}'. Check the ticker.")

    df = df.rename_axis("timestamps").reset_index()
    df["timestamps"] = pd.to_datetime(df["timestamps"])

    df = df.rename(columns={
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    })
    df["amount"] = df["close"] * df["volume"]

    needed_cols = ["timestamps", "open", "high", "low", "close", "volume", "amount"]
    df = df[needed_cols]
    df = df.tail(total_bars).reset_index(drop=True)

    for col in ["open", "high", "low", "close", "volume", "amount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if df.isnull().any().any():
        df = df.dropna().reset_index(drop=True)

    return df
