import numpy as np
import pandas as pd

from swing_trade import indicators as ind


def test_sma_matches_manual_mean():
    s = pd.Series(range(1, 11), dtype=float)
    result = ind.sma(s, 3)
    assert np.isclose(result.iloc[-1], (8 + 9 + 10) / 3)
    assert result.iloc[:2].isna().all()


def test_rsi_is_high_for_strict_uptrend():
    s = pd.Series(np.linspace(100, 200, 60))
    result = ind.rsi(s, 14)
    assert result.iloc[-1] > 90


def test_rsi_is_low_for_strict_downtrend():
    s = pd.Series(np.linspace(200, 100, 60))
    result = ind.rsi(s, 14)
    assert result.iloc[-1] < 10


def test_atr_is_positive(uptrend_df):
    result = ind.atr(uptrend_df, 14)
    assert (result.dropna() > 0).all()


def test_atr_pct_reasonable_range(uptrend_df):
    result = ind.atr_pct(uptrend_df, 14).dropna()
    assert (result > 0).all()
    assert (result < 20).all()  # sanity bound for the synthetic series used here


def test_adx_within_bounds(uptrend_df):
    result = ind.adx(uptrend_df, 14).dropna()
    assert (result >= 0).all()
    assert (result <= 100).all()


def test_macd_bullish_in_uptrend(uptrend_df):
    macd_line, signal_line, hist = ind.macd(uptrend_df["Close"])
    assert macd_line.iloc[-1] > 0
    assert hist.iloc[-30:].mean() >= 0


def test_obv_increases_in_uptrend(uptrend_df):
    result = ind.obv(uptrend_df)
    assert result.iloc[-1] > result.iloc[0]


def test_bollinger_band_ordering(uptrend_df):
    upper, mid, lower, bandwidth = ind.bollinger(uptrend_df["Close"], 20, 2.0)
    valid = mid.notna()
    assert (upper[valid] >= mid[valid]).all()
    assert (mid[valid] >= lower[valid]).all()
    assert (bandwidth[valid] >= 0).all()


def test_week52_high_is_max_high(uptrend_df):
    window = 50
    result = ind.week52_high(uptrend_df, window=window)
    manual = uptrend_df["High"].rolling(window, min_periods=min(window, len(uptrend_df))).max()
    pd.testing.assert_series_equal(result, manual, check_names=False)
    assert result.iloc[-1] == uptrend_df["High"].tail(window).max()


def test_fib_retracement_pct_bounds():
    # Price exactly halfway between swing low and swing high -> 50% retracement
    assert np.isclose(ind.fib_retracement_pct(150, 200, 100), 0.5)
    assert ind.fib_retracement_pct(100, 100, 100) is None


def test_swing_high_low(uptrend_df):
    high = ind.swing_high(uptrend_df, 10)
    low = ind.swing_low(uptrend_df, 10)
    valid = high.notna() & low.notna()
    assert (high[valid] >= low[valid]).all()
