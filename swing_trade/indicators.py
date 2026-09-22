"""Reine Indikator-Berechnungen auf OHLCV-Daten (pandas), ohne Netzwerkzugriff.

Erwartet ein DataFrame mit Spalten ['Open', 'High', 'Low', 'Close', 'Volume'],
aufsteigend nach Datum sortiert.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    result = 100 - (100 / (1 + rs))
    return result.where(avg_loss != 0, 100.0)


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["Close"].shift(1)
    ranges = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - prev_close).abs(),
            (df["Low"] - prev_close).abs(),
        ],
        axis=1,
    )
    return ranges.max(axis=1)


def atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    tr = true_range(df)
    return tr.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()


def atr_pct(df: pd.DataFrame, window: int = 14) -> pd.Series:
    return atr(df, window) / df["Close"] * 100


def adx(df: pd.DataFrame, window: int = 14) -> pd.Series:
    up_move = df["High"].diff()
    down_move = -df["Low"].diff()

    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)

    tr = true_range(df)
    atr_smooth = tr.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()

    plus_di = 100 * plus_dm.ewm(alpha=1 / window, adjust=False, min_periods=window).mean() / atr_smooth
    minus_di = 100 * minus_dm.ewm(alpha=1 / window, adjust=False, min_periods=window).mean() / atr_smooth

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def obv(df: pd.DataFrame) -> pd.Series:
    direction = np.sign(df["Close"].diff().fillna(0))
    return (direction * df["Volume"]).cumsum()


def bollinger(close: pd.Series, window: int = 20, num_std: float = 2.0):
    mid = sma(close, window)
    std = close.rolling(window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    bandwidth = (upper - lower) / mid
    return upper, mid, lower, bandwidth


def ichimoku_cloud(df: pd.DataFrame, tenkan_n: int = 9, kijun_n: int = 26, senkou_b_n: int = 52):
    tenkan = (df["High"].rolling(tenkan_n).max() + df["Low"].rolling(tenkan_n).min()) / 2
    kijun = (df["High"].rolling(kijun_n).max() + df["Low"].rolling(kijun_n).min()) / 2
    senkou_a = ((tenkan + kijun) / 2).shift(kijun_n)
    senkou_b = ((df["High"].rolling(senkou_b_n).max() + df["Low"].rolling(senkou_b_n).min()) / 2).shift(kijun_n)
    return senkou_a, senkou_b


def swing_low(df: pd.DataFrame, window: int) -> pd.Series:
    return df["Low"].rolling(window).min()


def swing_high(df: pd.DataFrame, window: int) -> pd.Series:
    return df["High"].rolling(window).max()


def week52_high(df: pd.DataFrame, window: int = 252) -> pd.Series:
    return df["High"].rolling(window, min_periods=min(window, len(df))).max()


def fib_retracement_pct(price: float, swing_high_val: float, swing_low_val: float) -> float | None:
    span = swing_high_val - swing_low_val
    if span <= 0:
        return None
    return (swing_high_val - price) / span
