"""Datenzugriff: Kursverlauf, Fundamentaldaten, Sektor und naechster
Earnings-Termin fuer einen Kandidaten und dessen Marktbenchmark.

Zwei Quellen werden unterstuetzt:
- "yfinance" (Standard): laedt live von Yahoo Finance. Braucht Internetzugriff.
- "csv": liest <price_dir>/<TICKER>.csv mit Spalten Date,Open,High,Low,Close,Volume.
  Fundamentaldaten/Sektor/Earnings kommen dann ausschliesslich aus optionalen
  Feldern der Watchlist-Datei (sonst UNKNOWN) - kein automatischer Abruf.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from pathlib import Path

import pandas as pd

BENCHMARK_BY_MARKET = {
    "US": "^GSPC",
    "EU": "^GDAXI",
}


@dataclasses.dataclass
class Fundamentals:
    market_cap: float | None = None
    sector: str | None = None
    avg_bid_ask_spread_pct: float | None = None
    eps_yoy_positive: bool | None = None
    revenue_yoy_positive: bool | None = None
    next_earnings_date: dt.date | None = None


def _read_price_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["Date"])
    df = df.set_index("Date").sort_index()
    return df[["Open", "High", "Low", "Close", "Volume"]]


def load_price_history(
    ticker: str,
    data_source: str = "yfinance",
    price_dir: Path | None = None,
    period: str = "2y",
) -> pd.DataFrame:
    if data_source == "csv":
        if price_dir is None:
            raise ValueError("--price-dir ist erforderlich fuer --data-source csv")
        path = Path(price_dir) / f"{ticker}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Keine Kursdaten-Datei gefunden: {path}")
        return _read_price_csv(path)

    import yfinance as yf

    df = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=False)
    if df.empty:
        raise ValueError(f"Keine Kursdaten von yfinance fuer '{ticker}' erhalten.")
    return df[["Open", "High", "Low", "Close", "Volume"]]


def load_benchmark_history(market: str, data_source: str = "yfinance", price_dir: Path | None = None, period: str = "2y") -> pd.DataFrame:
    if data_source == "csv":
        path = Path(price_dir) / f"BENCHMARK_{market}.csv"
        if not path.exists():
            raise FileNotFoundError(
                f"Keine Benchmark-Datei gefunden: {path} (wird fuer G1/G3 benoetigt)."
            )
        return _read_price_csv(path)

    ticker = BENCHMARK_BY_MARKET.get(market)
    if ticker is None:
        raise ValueError(f"Unbekannter Markt: {market!r} (erwartet 'US' oder 'EU')")
    return load_price_history(ticker, data_source="yfinance", period=period)


def load_fundamentals(ticker: str, data_source: str = "yfinance") -> Fundamentals:
    if data_source != "yfinance":
        return Fundamentals()

    import yfinance as yf

    t = yf.Ticker(ticker)
    fundamentals = Fundamentals()

    try:
        info = t.info or {}
        fundamentals.market_cap = info.get("marketCap")
        fundamentals.sector = info.get("sector")
        bid, ask = info.get("bid"), info.get("ask")
        if bid and ask and bid > 0:
            fundamentals.avg_bid_ask_spread_pct = (ask - bid) / bid * 100
    except Exception:
        pass

    try:
        income = t.quarterly_income_stmt
        if income is not None and not income.empty and income.shape[1] >= 5:
            revenue_row = next((r for r in income.index if "Total Revenue" in r), None)
            income_row = next((r for r in income.index if r == "Net Income"), None)
            if revenue_row is not None:
                latest, year_ago = income.loc[revenue_row].iloc[0], income.loc[revenue_row].iloc[4]
                fundamentals.revenue_yoy_positive = bool(latest > year_ago)
            if income_row is not None:
                latest, year_ago = income.loc[income_row].iloc[0], income.loc[income_row].iloc[4]
                fundamentals.eps_yoy_positive = bool(latest > year_ago)
    except Exception:
        pass

    try:
        earnings = t.get_earnings_dates(limit=4)
        if earnings is not None and not earnings.empty:
            future = [d for d in earnings.index if d.date() >= dt.date.today()]
            if future:
                fundamentals.next_earnings_date = min(future).date()
    except Exception:
        pass

    return fundamentals
