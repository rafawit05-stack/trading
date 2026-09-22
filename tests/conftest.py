import numpy as np
import pandas as pd
import pytest


def make_ohlcv(n=300, start_price=100.0, daily_drift=0.002, daily_vol=0.01, seed=0, volume_base=1_000_000):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2023-01-02", periods=n)
    returns = rng.normal(daily_drift, daily_vol, size=n)
    close = start_price * np.cumprod(1 + returns)

    open_ = close * (1 + rng.normal(0, 0.002, size=n))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.003, size=n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.003, size=n)))
    volume = rng.normal(volume_base, volume_base * 0.15, size=n).clip(min=1000)

    df = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=dates,
    )
    df.index.name = "Date"
    return df


@pytest.fixture
def uptrend_df():
    return make_ohlcv(n=300, daily_drift=0.0025, daily_vol=0.01, seed=1)


@pytest.fixture
def downtrend_df():
    return make_ohlcv(n=300, daily_drift=-0.0025, daily_vol=0.01, seed=2)


@pytest.fixture
def flat_df():
    return make_ohlcv(n=300, daily_drift=0.0, daily_vol=0.005, seed=3)
