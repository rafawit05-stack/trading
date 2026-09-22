import datetime as dt

import pytest

from swing_trade.evaluate import evaluate_candidate, sector_concentration_warnings
from swing_trade.gates import gate_exclusions, gate_risk_reward
from swing_trade.models import CandidateInput, EvaluationResult
from swing_trade.risk import build_risk_plan


def _write_csv(df, path):
    df.reset_index().rename(columns={"Date": "Date"}).to_csv(path, index=False)


@pytest.fixture
def csv_price_dir(tmp_path, uptrend_df, flat_df):
    _write_csv(uptrend_df, tmp_path / "GOOD.csv")
    _write_csv(flat_df, tmp_path / "BENCHMARK_US.csv")
    _write_csv(flat_df, tmp_path / "BENCHMARK_EU.csv")
    return tmp_path


def test_evaluate_candidate_uptrend_vs_flat_benchmark_passes_regime_and_trend(csv_price_dir):
    candidate = CandidateInput(ticker="GOOD", market="US", playbook="A")
    result = evaluate_candidate(candidate, data_source="csv", price_dir=csv_price_dir)

    gate_status = {g.code: g.status for g in result.gates}
    assert gate_status["G2"] == "pass"  # klarer Aufwaertstrend im Kandidaten
    assert 0 <= result.weighted_score <= 10
    assert len(result.factor_scores) == 7  # kein Sentiment mitgegeben -> nicht 8


def test_evaluate_candidate_with_sentiment_adds_factor(csv_price_dir):
    candidate = CandidateInput(ticker="GOOD", market="US", playbook="B")
    result = evaluate_candidate(candidate, data_source="csv", price_dir=csv_price_dir, sentiment_score=7.5)

    concepts = [f.concept for f in result.factor_scores]
    assert "News & Sentiment" in concepts


def test_red_flag_forces_gate5_fail_and_auto_reject(csv_price_dir):
    candidate = CandidateInput(ticker="GOOD", market="US", playbook="A", red_flag="Pending dilution")
    result = evaluate_candidate(candidate, data_source="csv", price_dir=csv_price_dir)

    g5 = next(g for g in result.gates if g.code == "G5")
    assert g5.status == "fail"
    assert result.auto_rejected is True


def test_earnings_inside_hold_window_without_thesis_flag_fails_gate5():
    candidate = CandidateInput(ticker="X", market="US", playbook="A", hold_sessions_max=10, earnings_is_thesis=False)
    earnings_soon = dt.date.today() + dt.timedelta(days=3)
    result = gate_exclusions(candidate, earnings_soon)
    assert result.status == "fail"


def test_earnings_marked_as_thesis_passes_gate5():
    candidate = CandidateInput(ticker="X", market="US", playbook="A", hold_sessions_max=10, earnings_is_thesis=True)
    earnings_soon = dt.date.today() + dt.timedelta(days=3)
    result = gate_exclusions(candidate, earnings_soon)
    assert result.status == "pass"


def test_risk_plan_stop_below_entry_below_targets(uptrend_df):
    candidate = CandidateInput(ticker="GOOD", market="US", playbook="A", capital=10_000, risk_pct_default=1.0)
    plan = build_risk_plan(uptrend_df, candidate, "A", is_a_plus=False)

    assert plan is not None
    assert plan.stop < plan.entry < plan.target1 < plan.target2
    assert plan.risk_dollars <= candidate.capital * 0.011  # ~1% Risiko, kleine Rundungstoleranz
    assert plan.shares >= 0


def test_gate_risk_reward_thresholds():
    assert gate_risk_reward(2.5).status == "pass"
    assert gate_risk_reward(1.9).status == "fail"
    assert gate_risk_reward(None).status == "unknown"


def test_risk_plan_rr_after_costs_can_reach_gate_threshold(uptrend_df):
    """Regression test: a bare 2R target can never clear G6 (>=2.0 after costs),
    since costs are subtracted from the reward leg and added to the risk leg -
    the after-cost ratio is then provably < raw ratio for any positive cost.
    Target multiples must therefore include a cost buffer above 2R/3R."""
    zero_cost_candidate = CandidateInput(
        ticker="GOOD", market="US", playbook="A", commission_bps=0.0, slippage_bps=0.0
    )
    zero_cost_plan = build_risk_plan(uptrend_df, zero_cost_candidate, "A", is_a_plus=False)
    assert zero_cost_plan is not None
    assert zero_cost_plan.rr_raw > 2.0  # cost buffer built into the raw target, not just 2R
    assert zero_cost_plan.rr_after_costs == pytest.approx(zero_cost_plan.rr_raw, rel=1e-6)

    default_candidate = CandidateInput(ticker="GOOD", market="US", playbook="A")
    default_plan = build_risk_plan(uptrend_df, default_candidate, "A", is_a_plus=False)
    assert default_plan is not None
    assert default_plan.rr_after_costs > 1.7  # strictly above the old (bugged) 2R-target value


def test_sector_concentration_warning_triggers_above_limit():
    results = [
        EvaluationResult(
            candidate=CandidateInput(ticker=f"T{i}", market="US", playbook="A", sector="Technology"),
            gates=[],
            auto_rejected=False,
            needs_manual_review=False,
            factor_scores=[],
            weighted_score=5.0,
            is_a_plus=False,
            risk_plan=None,
            warnings=[],
            as_of=dt.date.today(),
        )
        for i in range(3)
    ]

    warnings = sector_concentration_warnings(results, max_per_sector=2)
    assert any("Technology" in w for w in warnings)


def test_sector_concentration_ignores_rejected_candidates():
    results = [
        EvaluationResult(
            candidate=CandidateInput(ticker=f"T{i}", market="US", playbook="A", sector="Technology"),
            gates=[],
            auto_rejected=True,
            needs_manual_review=False,
            factor_scores=[],
            weighted_score=5.0,
            is_a_plus=False,
            risk_plan=None,
            warnings=[],
            as_of=dt.date.today(),
        )
        for i in range(3)
    ]

    assert sector_concentration_warnings(results, max_per_sector=2) == []
