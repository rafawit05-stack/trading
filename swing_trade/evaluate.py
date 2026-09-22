"""Orchestrierung: Gates + Scoring + Risk-Plan fuer einen Kandidaten."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd

from . import data as data_module
from . import gates as gates_module
from . import scoring
from .models import CandidateInput, EvaluationResult, FactorScore
from .risk import build_risk_plan
from .thresholds import A_PLUS_MIN_WEIGHTED_SCORE

DEFAULT_WEIGHTS = {
    "Trend qual.": 1 / 7,
    "Momentum": 1 / 7,
    "Volume": 1 / 7,
    "Volatility": 1 / 7,
    "Pattern": 1 / 7,
    "Location": 1 / 7,
    "Fundamentals": 1 / 7,
}


def _weighted_average(scores: list[FactorScore], weights: dict[str, float]) -> float:
    relevant = [(s, weights.get(s.concept, 0.0)) for s in scores if weights.get(s.concept, 0.0) > 0]
    total_weight = sum(w for _, w in relevant)
    if total_weight == 0:
        return 0.0
    return sum(s.primary_score * w for s, w in relevant) / total_weight


def evaluate_candidate(
    candidate: CandidateInput,
    data_source: str = "yfinance",
    price_dir: Path | None = None,
    weights: dict[str, float] | None = None,
    sentiment_score: float | None = None,
) -> EvaluationResult:
    weights = weights or DEFAULT_WEIGHTS

    df = data_module.load_price_history(candidate.ticker, data_source, price_dir)
    benchmark_df = data_module.load_benchmark_history(candidate.market, data_source, price_dir)
    fundamentals = data_module.load_fundamentals(candidate.ticker, data_source)

    sector = candidate.sector or fundamentals.sector

    gate_list = [
        gates_module.gate_regime(benchmark_df),
        gates_module.gate_trend(df),
        gates_module.gate_relative_strength(df, benchmark_df),
        gates_module.gate_liquidity(df, candidate.market, fundamentals.market_cap, fundamentals.avg_bid_ask_spread_pct),
        gates_module.gate_exclusions(candidate, fundamentals.next_earnings_date),
    ]

    factor_scores = [
        scoring.score_trend_quality(df),
        scoring.score_momentum(df, candidate.playbook),
        scoring.score_volume(df, candidate.playbook),
        scoring.score_volatility(df, candidate.market, fundamentals.market_cap),
        scoring.score_pattern(df, candidate.playbook),
        scoring.score_location(df, candidate.playbook),
        scoring.score_fundamentals(fundamentals.eps_yoy_positive, fundamentals.revenue_yoy_positive),
    ]
    sentiment_factor = scoring.score_sentiment(sentiment_score)
    if sentiment_factor is not None:
        factor_scores.append(sentiment_factor)

    weighted_score = _weighted_average(factor_scores, weights)
    all_confirmed = all(f.confirmed for f in factor_scores if f.concept != "Fundamentals" and f.concept != "News & Sentiment")

    provisional_gates_ok = all(g.status == "pass" for g in gate_list)
    is_a_plus = provisional_gates_ok and weighted_score >= A_PLUS_MIN_WEIGHTED_SCORE and all_confirmed

    risk_plan = build_risk_plan(df, candidate, candidate.playbook, is_a_plus)
    gate_list.append(gates_module.gate_risk_reward(risk_plan.rr_after_costs if risk_plan else None))

    auto_rejected = any(g.status == "fail" for g in gate_list) or risk_plan is None
    needs_manual_review = (not auto_rejected) and any(g.status == "unknown" for g in gate_list)

    warnings = []
    if risk_plan:
        warnings.extend(risk_plan.adjustments)
    if sector:
        pass  # Sektor wird auf Portfolio-Ebene fuer die Korrelations-/Klumpenpruefung genutzt.
    if fundamentals.avg_bid_ask_spread_pct is None:
        warnings.append("Spread-Daten nicht verfuegbar - G4 ggf. manuell pruefen.")

    return EvaluationResult(
        candidate=candidate,
        gates=gate_list,
        auto_rejected=auto_rejected,
        needs_manual_review=needs_manual_review,
        factor_scores=factor_scores,
        weighted_score=round(weighted_score, 2),
        is_a_plus=is_a_plus,
        risk_plan=risk_plan,
        warnings=warnings,
        as_of=dt.date.today(),
    )


def sector_concentration_warnings(results: list[EvaluationResult], max_per_sector: int = 2) -> list[str]:
    sectors: dict[str, list[str]] = {}
    for r in results:
        if r.auto_rejected:
            continue
        sector = r.candidate.sector
        if not sector:
            continue
        sectors.setdefault(sector, []).append(r.candidate.ticker)

    warnings = []
    for sector, tickers in sectors.items():
        if len(tickers) > max_per_sector:
            warnings.append(
                f"Klumpenrisiko: {len(tickers)} Kandidaten im Sektor '{sector}' "
                f"({', '.join(tickers)}) - Korrelations-Limit pruefen."
            )
    return warnings
