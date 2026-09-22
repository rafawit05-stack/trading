"""Datenklassen fuer das Swing-Trade Evaluation Framework."""

from __future__ import annotations

import dataclasses
import datetime as dt

GateStatus = str  # "pass" | "fail" | "unknown"


@dataclasses.dataclass
class CandidateInput:
    ticker: str
    market: str  # "US" | "EU"
    playbook: str  # "A" | "B"
    sector: str | None = None
    red_flag: str | None = None
    earnings_is_thesis: bool = False
    capital: float = 10_000.0
    risk_pct_default: float = 1.0
    risk_pct_a_plus: float = 2.0
    commission_bps: float = 5.0
    slippage_bps: float = 5.0
    hold_sessions_max: int = 10
    notes: str | None = None


@dataclasses.dataclass
class GateResult:
    code: str
    label: str
    status: GateStatus
    detail: str


@dataclasses.dataclass
class FactorScore:
    concept: str
    primary_score: float  # 0-10, includes confirmation bonus, capped at 10
    confirmed: bool
    detail: str


@dataclasses.dataclass
class RiskPlan:
    entry: float
    stop: float
    target1: float
    target2: float
    risk_per_share: float
    shares: int
    risk_dollars: float
    rr_raw: float
    rr_after_costs: float
    time_stop_sessions: int
    invalidation: str
    adjustments: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class EvaluationResult:
    candidate: CandidateInput
    gates: list[GateResult]
    auto_rejected: bool
    needs_manual_review: bool
    factor_scores: list[FactorScore]
    weighted_score: float
    is_a_plus: bool
    risk_plan: RiskPlan | None
    warnings: list[str]
    as_of: dt.date
