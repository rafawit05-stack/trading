"""Hard Gates G1-G6. Jedes Gate liefert PASS / FAIL / UNKNOWN.

UNKNOWN bedeutet "nicht verifizierbar" (z.B. zu wenig Historie, fehlende
Fundamentaldaten) und wird NIE wie PASS behandelt - ein Kandidat mit
UNKNOWN-Gates landet nicht in der bestaetigten Shortlist, sondern im
Bereich "manuelle Pruefung noetig".
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

from . import indicators as ind
from .models import CandidateInput, GateResult
from .thresholds import LIQUIDITY


def gate_regime(benchmark_df: pd.DataFrame) -> GateResult:
    if len(benchmark_df) < 210:
        return GateResult("G1", "Regime (Index > 200-Tage-Linie)", "unknown", "Zu wenig Benchmark-Historie.")
    sma200 = ind.sma(benchmark_df["Close"], 200).iloc[-1]
    price = benchmark_df["Close"].iloc[-1]
    if pd.isna(sma200):
        return GateResult("G1", "Regime (Index > 200-Tage-Linie)", "unknown", "200-Tage-Linie nicht berechenbar.")
    status = "pass" if price > sma200 else "fail"
    return GateResult("G1", "Regime (Index > 200-Tage-Linie)", status, f"Index {price:.2f} vs. SMA200 {sma200:.2f}")


def gate_trend(df: pd.DataFrame) -> GateResult:
    if len(df) < 210:
        return GateResult("G2", "Trend (Preis > 50-SMA > 200-SMA, steigend)", "unknown", "Zu wenig Historie fuer 200-SMA.")
    close = df["Close"]
    sma50 = ind.sma(close, 50)
    sma200 = ind.sma(close, 200)
    if pd.isna(sma50.iloc[-1]) or pd.isna(sma200.iloc[-1]) or pd.isna(sma50.iloc[-11]):
        return GateResult("G2", "Trend (Preis > 50-SMA > 200-SMA, steigend)", "unknown", "Indikatoren nicht vollstaendig berechenbar.")
    price = close.iloc[-1]
    slope_up = sma50.iloc[-1] > sma50.iloc[-11]
    ok = price > sma50.iloc[-1] > sma200.iloc[-1] and slope_up
    detail = (
        f"Preis {price:.2f}, SMA50 {sma50.iloc[-1]:.2f} ({'steigend' if slope_up else 'fallend'}), "
        f"SMA200 {sma200.iloc[-1]:.2f}"
    )
    return GateResult("G2", "Trend (Preis > 50-SMA > 200-SMA, steigend)", "pass" if ok else "fail", detail)


def gate_relative_strength(df: pd.DataFrame, benchmark_df: pd.DataFrame, lookback: int = 63) -> GateResult:
    if len(df) <= lookback or len(benchmark_df) <= lookback:
        return GateResult("G3", "Relative Staerke (3M > Benchmark)", "unknown", "Zu wenig Historie fuer 3-Monats-Vergleich.")
    stock_ret = df["Close"].iloc[-1] / df["Close"].iloc[-lookback - 1] - 1
    bench_ret = benchmark_df["Close"].iloc[-1] / benchmark_df["Close"].iloc[-lookback - 1] - 1
    status = "pass" if stock_ret > bench_ret else "fail"
    return GateResult(
        "G3",
        "Relative Staerke (3M > Benchmark)",
        status,
        f"Aktie {stock_ret * 100:+.1f}% vs. Benchmark {bench_ret * 100:+.1f}%",
    )


def gate_liquidity(df: pd.DataFrame, market: str, market_cap: float | None, spread_pct: float | None) -> GateResult:
    thresholds = LIQUIDITY[market]
    if len(df) < 20:
        return GateResult("G4", "Liquiditaet", "unknown", "Zu wenig Historie fuer 20-Tage-Durchschnittsvolumen.")

    avg_volume = df["Volume"].tail(20).mean()
    avg_close = df["Close"].tail(20).mean()
    avg_turnover = avg_volume * avg_close

    fails = []
    if avg_volume < thresholds["min_avg_volume"]:
        fails.append(f"Volumen {avg_volume:,.0f} < Minimum {thresholds['min_avg_volume']:,.0f}")
    if avg_turnover < thresholds["min_avg_turnover"]:
        fails.append(f"Turnover {avg_turnover:,.0f} < Minimum {thresholds['min_avg_turnover']:,.0f}")
    if spread_pct is not None and spread_pct > thresholds["max_spread_pct"]:
        fails.append(f"Spread {spread_pct:.2f}% > Maximum {thresholds['max_spread_pct']:.2f}%")

    cap_unknown = market_cap is None
    if market_cap is not None and market_cap < thresholds["min_market_cap_floor"]:
        fails.append(f"Marktkap. {market_cap:,.0f} < Floor {thresholds['min_market_cap_floor']:,.0f}")

    detail = f"Ø Volumen {avg_volume:,.0f}, Ø Turnover {avg_turnover:,.0f}"
    if spread_pct is not None:
        detail += f", Spread {spread_pct:.2f}%"
    else:
        detail += ", Spread unbekannt"
    if market_cap is not None:
        detail += f", Marktkap. {market_cap:,.0f}"
    else:
        detail += ", Marktkap. unbekannt"

    if fails:
        return GateResult("G4", "Liquiditaet", "fail", "; ".join(fails))
    if cap_unknown:
        return GateResult("G4", "Liquiditaet", "unknown", detail + " (Marktkap. nicht verifizierbar)")
    return GateResult("G4", "Liquiditaet", "pass", detail)


def gate_exclusions(candidate: CandidateInput, next_earnings_date: dt.date | None) -> GateResult:
    if candidate.red_flag:
        return GateResult("G5", "Exclusions (Red Flags)", "fail", f"Manuell markiert: {candidate.red_flag}")

    if next_earnings_date is not None:
        hold_end = dt.date.today() + dt.timedelta(days=candidate.hold_sessions_max * 1.5)
        if next_earnings_date <= hold_end and not candidate.earnings_is_thesis:
            return GateResult(
                "G5",
                "Exclusions (Red Flags)",
                "fail",
                f"Earnings am {next_earnings_date.isoformat()} liegt im geplanten Haltezeitraum "
                f"(nicht als Katalysator markiert).",
            )

    note = "Automatisiert geprueft: Red-Flag-Feld & Earnings-Fenster."
    note += " Qualitative Red Flags (Dilution, Delisting, Lock-up, Meme-Dynamik) bitte manuell pruefen (siehe Checkliste)."
    return GateResult("G5", "Exclusions (Red Flags)", "pass", note)


def gate_risk_reward(rr_after_costs: float | None) -> GateResult:
    if rr_after_costs is None:
        return GateResult("G6", "R:R >= 2.0 nach Kosten", "unknown", "Trade-Plan konnte nicht berechnet werden.")
    status = "pass" if rr_after_costs >= 2.0 else "fail"
    return GateResult("G6", "R:R >= 2.0 nach Kosten", status, f"R:R nach Kosten = {rr_after_costs:.2f}")
