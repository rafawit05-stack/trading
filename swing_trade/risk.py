"""Trade-Plan: Entry/Stop/Targets, Positionsgroesse und R:R nach Kosten.

Stop-Regel (Framework): stop = max(structure_stop, entry - 1.5*ATR).
Fuer einen Long-Trade sind beide Kandidaten Preise UNTER dem Entry - "max"
waehlt damit bewusst den ENGEREN (naeher am Entry liegenden) der beiden Stops,
um den Verlust auf ca. 1.5*ATR zu begrenzen ("loss still bounded").

Luecke im Original-Framework: ein rein struktureller Stop kann zufaellig sehr
nah am Entry liegen (z.B. gestriges Tief direkt unter dem Kaufkurs) und wuerde
dann von normalem Kursrauschen ausgeloest ("noise doesn't trigger" waere
verletzt). Dieser Code ergaenzt daher einen Mindestabstand von 0.5*ATR: liegt
der berechnete Stop enger als das, wird er auf den Mindestabstand aufgeweitet
und die Anpassung im Trade-Plan vermerkt.
"""

from __future__ import annotations

import math

import pandas as pd

from . import indicators as ind
from .models import CandidateInput, RiskPlan
from .thresholds import (
    MIN_RR_AFTER_COSTS,
    NOISE_FLOOR_ATR_MULTIPLE,
    STOP_ATR_MULTIPLE,
)


def _round_trip_cost_per_share(price: float, commission_bps: float, slippage_bps: float) -> float:
    return price * (commission_bps + slippage_bps) / 10_000


def propose_entry_stop(df: pd.DataFrame, playbook: str, lookback: int = 20) -> tuple[float, float, list[str]]:
    notes: list[str] = []
    close = df["Close"]
    last_close = close.iloc[-1]
    atr_val = ind.atr(df, 14).iloc[-1]

    if playbook == "A":
        pivot = df["High"].shift(1).rolling(lookback).max().iloc[-1]
        entry = max(last_close, pivot * 1.001)
        if last_close > pivot * 1.10:
            notes.append(
                f"Kandidat ist bereits {((last_close / pivot) - 1) * 100:.1f}% ueber dem Pivot "
                f"({pivot:.2f}) - moeglicherweise ueberdehnt fuer einen frischen Breakout-Einstieg."
            )
        structure_stop = df["Low"].shift(1).rolling(10).min().iloc[-1]
    else:
        entry = last_close
        ema20 = ind.ema(close, 20).iloc[-1]
        sma50 = ind.sma(close, 50).iloc[-1]
        structure_stop = min(ema20, sma50) * 0.997

    stop_candidate = max(structure_stop, entry - STOP_ATR_MULTIPLE * atr_val)
    noise_floor = entry - NOISE_FLOOR_ATR_MULTIPLE * atr_val
    if stop_candidate > noise_floor:
        stop = noise_floor
        notes.append(
            "Struktureller Stop lag enger als 0.5x ATR am Entry (Rauschgefahr) - "
            "auf Mindestabstand aufgeweitet."
        )
    else:
        stop = stop_candidate

    return float(entry), float(stop), notes


def build_risk_plan(
    df: pd.DataFrame,
    candidate: CandidateInput,
    playbook: str,
    is_a_plus: bool,
) -> RiskPlan | None:
    entry, stop, notes = propose_entry_stop(df, playbook)

    if stop >= entry:
        return None

    risk_per_share = entry - stop
    target1 = entry + 2 * risk_per_share
    target2 = entry + 3 * risk_per_share

    risk_pct = candidate.risk_pct_a_plus if is_a_plus else candidate.risk_pct_default
    risk_dollars = candidate.capital * risk_pct / 100
    shares = math.floor(risk_dollars / risk_per_share) if risk_per_share > 0 else 0

    entry_cost = _round_trip_cost_per_share(entry, candidate.commission_bps, candidate.slippage_bps)
    stop_cost = _round_trip_cost_per_share(stop, candidate.commission_bps, candidate.slippage_bps)
    target_cost = _round_trip_cost_per_share(target1, candidate.commission_bps, candidate.slippage_bps)

    effective_risk = risk_per_share + entry_cost + stop_cost
    effective_reward = (target1 - entry) - entry_cost - target_cost
    rr_raw = (target1 - entry) / risk_per_share
    rr_after_costs = effective_reward / effective_risk if effective_risk > 0 else 0.0

    invalidation = (
        "Ausloeser fuer den Einstieg ist nicht mehr gueltig (z.B. Rueckfall unter den "
        "Pivot/die Unterstuetzung auf Schlusskursbasis) oder fundamentaler Bruch der These."
    )

    return RiskPlan(
        entry=round(entry, 4),
        stop=round(stop, 4),
        target1=round(target1, 4),
        target2=round(target2, 4),
        risk_per_share=round(risk_per_share, 4),
        shares=shares,
        risk_dollars=round(risk_dollars, 2),
        rr_raw=round(rr_raw, 2),
        rr_after_costs=round(rr_after_costs, 2),
        time_stop_sessions=candidate.hold_sessions_max,
        invalidation=invalidation,
        adjustments=notes,
    )


__all__ = ["build_risk_plan", "propose_entry_stop", "MIN_RR_AFTER_COSTS"]
