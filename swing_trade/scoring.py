"""Scored Factors: ein Primaerindikator + optionaler Bestaetigungs-Bonus pro
Konzept, playbook-abhaengig wo im Framework vorgegeben.

Luecke im Original-Framework, die hier korrigiert wird: die Konzepttabelle
listet fuer "Volume" nur die Breakout-Regel (>= 1.5x 20-Tage-Volumen), obwohl
der Playbook-B-Text ausdruecklich einen Volumen-Dry-up waehrend des Pullbacks
verlangt - das Gegenteil einer Volumenexpansion. Diese Implementierung nutzt
daher für Playbook B eine eigene Dry-up/Pickup-Regel statt der Breakout-Regel.

"News & Sentiment" taucht im Fliesstext als zu bewertender (nicht gate-faehiger)
Faktor auf, fehlt aber in der Konzepttabelle des Frameworks. Da hierfuer keine
automatisierte Datenquelle angebunden ist, wird der Faktor nur einbezogen, wenn
ein sentiment_score (0-10) explizit in der Watchlist mitgegeben wird - sonst
wird er weggelassen statt mit einem erfundenen Neutralwert aufgefuellt.
"""

from __future__ import annotations

import pandas as pd

from . import indicators as ind
from .models import CandidateInput, FactorScore
from .thresholds import ATR_BAND_DEFAULT, ATR_BAND_LARGE_EU, LARGE_EU_MARKET_CAP


def _band_score(value: float | None, lo: float, hi: float, span: float) -> float | None:
    if value is None or pd.isna(value):
        return None
    if lo <= value <= hi:
        return 10.0
    dist = lo - value if value < lo else value - hi
    return max(0.0, 10.0 - (dist / span) * 10.0)


def score_trend_quality(df: pd.DataFrame) -> FactorScore:
    adx_val = ind.adx(df, 14).iloc[-1]
    primary = _band_score(adx_val, 20, 40, span=20)
    if primary is None:
        return FactorScore("Trend qual.", 5.0, False, "ADX nicht berechenbar (zu wenig Historie).")

    senkou_a, senkou_b = ind.ichimoku_cloud(df)
    confirmed = False
    if not pd.isna(senkou_a.iloc[-1]) and not pd.isna(senkou_b.iloc[-1]):
        cloud_top = max(senkou_a.iloc[-1], senkou_b.iloc[-1])
        confirmed = df["Close"].iloc[-1] > cloud_top

    score = min(10.0, primary + (1.0 if confirmed else 0.0))
    return FactorScore("Trend qual.", score, confirmed, f"ADX14={adx_val:.1f}, Ichimoku-Bestaetigung={confirmed}")


def score_momentum(df: pd.DataFrame, playbook: str) -> FactorScore:
    rsi_val = ind.rsi(df["Close"], 14).iloc[-1]
    if pd.isna(rsi_val):
        return FactorScore("Momentum", 5.0, False, "RSI nicht berechenbar.")

    if playbook == "A":
        primary = 5 + (rsi_val - 50) / 30 * 5 if rsi_val >= 50 else 5 * (rsi_val / 50)
        primary = max(0.0, min(10.0, primary))
    else:
        primary = _band_score(rsi_val, 40, 50, span=20) or 0.0

    macd_line, signal_line, hist = ind.macd(df["Close"])
    confirmed = False
    if len(hist) >= 2 and not hist.iloc[-1:].isna().any() and not hist.iloc[-2:-1].isna().any():
        bullish_cross = hist.iloc[-1] > 0 and hist.iloc[-2] <= 0
        confirmed = bool(macd_line.iloc[-1] > signal_line.iloc[-1] or bullish_cross)

    score = min(10.0, primary + (1.0 if confirmed else 0.0))
    return FactorScore("Momentum", score, confirmed, f"RSI14={rsi_val:.1f}, MACD-Bestaetigung={confirmed}")


def score_volume(df: pd.DataFrame, playbook: str) -> FactorScore:
    volume = df["Volume"]
    avg20 = volume.shift(1).rolling(20).mean().iloc[-1]
    if pd.isna(avg20) or avg20 == 0:
        return FactorScore("Volume", 5.0, False, "20-Tage-Durchschnittsvolumen nicht berechenbar.")

    if playbook == "A":
        ratio = volume.iloc[-1] / avg20
        primary = max(0.0, min(10.0, (ratio - 1) / 0.5 * 10))
        detail = f"Breakout-Volumen = {ratio:.2f}x 20-Tage-Ø"
    else:
        dryup_ratio = volume.iloc[-6:-1].mean() / avg20
        pickup = volume.iloc[-1] > volume.iloc[-2]
        dryup_score = max(0.0, min(10.0, 10 - (dryup_ratio - 0.8) / 0.4 * 10))
        primary = 0.5 * dryup_score + 0.5 * (10.0 if pickup else 3.0)
        detail = f"Dry-up-Volumen = {dryup_ratio:.2f}x 20-Tage-Ø, Pickup heute={pickup}"

    obv = ind.obv(df)
    lookback = min(10, len(obv) - 1)
    confirmed = False
    if lookback > 0:
        obv_delta = obv.iloc[-1] - obv.iloc[-1 - lookback]
        price_delta = df["Close"].iloc[-1] - df["Close"].iloc[-1 - lookback]
        confirmed = (obv_delta > 0) == (price_delta > 0)

    score = min(10.0, primary + (1.0 if confirmed else 0.0))
    return FactorScore("Volume", score, confirmed, detail + f", OBV-Bestaetigung={confirmed}")


def score_volatility(df: pd.DataFrame, market: str, market_cap: float | None) -> FactorScore:
    atr_pct_val = ind.atr_pct(df, 14).iloc[-1]
    if pd.isna(atr_pct_val):
        return FactorScore("Volatility", 5.0, False, "ATR% nicht berechenbar.")

    band = ATR_BAND_DEFAULT[market]
    if market == "EU" and market_cap is not None and market_cap >= LARGE_EU_MARKET_CAP:
        band = ATR_BAND_LARGE_EU

    primary = _band_score(atr_pct_val, band[0], band[1], span=4) or 0.0

    _, _, _, bandwidth = ind.bollinger(df["Close"], 20, 2.0)
    confirmed = False
    recent = bandwidth.tail(60).dropna()
    if len(recent) >= 20:
        confirmed = bool(recent.iloc[-1] <= recent.quantile(0.20))

    score = min(10.0, primary + (1.0 if confirmed else 0.0))
    return FactorScore("Volatility", score, confirmed, f"ATR%={atr_pct_val:.2f} (Band {band[0]}-{band[1]}%), Squeeze={confirmed}")


def score_pattern(df: pd.DataFrame, playbook: str) -> FactorScore:
    close = df["Close"]
    _, _, _, bandwidth = ind.bollinger(close, 20, 2.0)

    if playbook == "A":
        pivot = df["High"].shift(1).rolling(20).max().iloc[-1]
        breakout = close.iloc[-1] > pivot if not pd.isna(pivot) else False
        if len(bandwidth.dropna()) >= 11:
            contraction = max(0.0, min(10.0, (bandwidth.iloc[-11] - bandwidth.iloc[-1]) / bandwidth.iloc[-11] * 10)) if bandwidth.iloc[-11] > 0 else 5.0
        else:
            contraction = 5.0
        primary = 0.5 * (10.0 if breakout else 0.0) + 0.5 * contraction
        near_level = pivot is not None and not pd.isna(pivot) and abs(close.iloc[-1] - pivot) / pivot < 0.015
        detail = f"Breakout={breakout}, Volatilitaets-Kontraktion={contraction:.1f}/10"
    else:
        ema20 = ind.ema(close, 20).iloc[-1]
        sma50 = ind.sma(close, 50).iloc[-1]
        support = min(ema20, sma50)
        near_support = abs(close.iloc[-1] - support) / close.iloc[-1] < 0.03
        last_open, last_close, last_high, last_low = df["Open"].iloc[-1], close.iloc[-1], df["High"].iloc[-1], df["Low"].iloc[-1]
        day_range = last_high - last_low
        reversal_candle = last_close > last_open and day_range > 0 and (last_close - last_low) / day_range > 0.5
        primary = 0.5 * (10.0 if near_support else 0.0) + 0.5 * (10.0 if reversal_candle else 0.0)
        near_level = near_support
        detail = f"Naehe zur Unterstuetzung={near_support}, Reversal-Kerze={reversal_candle}"

    confirmed = bool(near_level)
    score = min(10.0, primary + (1.0 if confirmed else 0.0))
    return FactorScore("Pattern", score, confirmed, detail + f", sauberer Retest={confirmed} (heuristisch, kein echtes Chartmuster-Erkennen)")


def score_location(df: pd.DataFrame, playbook: str) -> FactorScore:
    close = df["Close"]
    week52 = ind.week52_high(df).iloc[-1]
    if pd.isna(week52) or week52 <= 0:
        return FactorScore("Location", 5.0, False, "52-Wochen-Hoch nicht berechenbar.")

    dist_pct = (week52 - close.iloc[-1]) / week52 * 100
    primary = max(0.0, 10.0 - dist_pct / 25 * 10)

    confirmed = False
    detail_extra = ""
    if playbook == "B":
        sw_high = ind.swing_high(df, 60).iloc[-1]
        sw_low = ind.swing_low(df, 60).iloc[-1]
        retracement = ind.fib_retracement_pct(close.iloc[-1], sw_high, sw_low)
        if retracement is not None:
            confirmed = 0.382 <= retracement <= 0.618
            detail_extra = f", Fib-Retracement={retracement * 100:.1f}%"

    score = min(10.0, primary + (1.0 if confirmed else 0.0))
    return FactorScore("Location", score, confirmed, f"{dist_pct:.1f}% unter 52W-Hoch{detail_extra}")


def score_fundamentals(eps_yoy_positive: bool | None, revenue_yoy_positive: bool | None) -> FactorScore:
    if eps_yoy_positive is None and revenue_yoy_positive is None:
        return FactorScore("Fundamentals", 5.0, False, "EPS/Umsatz-YoY nicht verfuegbar - neutral gewertet.")

    values = [v for v in (eps_yoy_positive, revenue_yoy_positive) if v is not None]
    positive_count = sum(1 for v in values if v)
    if len(values) == 2:
        primary = {2: 10.0, 1: 6.0, 0: 2.0}[positive_count]
    else:
        primary = 7.0 if positive_count == 1 else 3.0

    detail = f"EPS YoY positiv={eps_yoy_positive}, Umsatz YoY positiv={revenue_yoy_positive}"
    return FactorScore(
        "Fundamentals", primary, False,
        detail + " (Schaetzungsrevisionen nicht verfuegbar, kein Bonus angewendet)",
    )


def score_sentiment(sentiment_score: float | None) -> FactorScore | None:
    if sentiment_score is None:
        return None
    return FactorScore("News & Sentiment", max(0.0, min(10.0, sentiment_score)), False, "Manuell/extern zugefuehrter Sentiment-Score.")
