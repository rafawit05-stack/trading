"""Rendert die Evaluationsergebnisse als Markdown-Report."""

from __future__ import annotations

import datetime as dt

from .evaluate import DEFAULT_WEIGHTS, sector_concentration_warnings
from .models import EvaluationResult

CHECKLIST = """## Checkliste pro Kandidat (manuell abhaken vor Order)

- [ ] Playbook eindeutig gewaehlt (A ODER B, nicht gemischt)
- [ ] G1-G6 alle PASS (nicht nur UNKNOWN/ignoriert)
- [ ] Primaerindikatoren stimmig; Bestaetigung vorhanden
- [ ] Liquiditaet & Spread fuer den Markt ok
- [ ] Stop, Groesse, Targets, Invalidation, Time-Stop VOR dem Einstieg notiert
- [ ] R:R >= 2:1 nach Kosten
- [ ] Keine qualitativen Red Flags (Kapitalerhoehung, Delisting, Lock-up-Ablauf, \
reine Meme-/Squeeze-Dynamik) - dies prueft das Tool NICHT automatisch
- [ ] Earnings ausserhalb des Haltefensters (oder bewusst als These gewaehlt)
- [ ] Position im Handelsjournal dokumentiert
"""


def _gate_line(gate) -> str:
    icon = {"pass": "✅", "fail": "❌", "unknown": "❓"}[gate.status]
    return f"- {icon} **{gate.code} {gate.label}**: {gate.detail}"


def _factor_line(factor) -> str:
    return f"- **{factor.concept}**: {factor.primary_score:.1f}/10 - {factor.detail}"


def _candidate_section(result: EvaluationResult) -> str:
    c = result.candidate
    lines = [f"### {c.ticker} ({c.market}, Playbook {c.playbook})", ""]
    lines.append(f"Gesamtscore: **{result.weighted_score:.1f}/10**" + (" — A+ Setup" if result.is_a_plus else ""))
    lines.append("")
    lines.append("**Gates:**")
    lines.extend(_gate_line(g) for g in result.gates)
    lines.append("")
    lines.append("**Scoring:**")
    lines.extend(_factor_line(f) for f in result.factor_scores)
    lines.append("")

    if result.risk_plan:
        rp = result.risk_plan
        lines.append("**Trade-Plan:**")
        lines.append(f"- Entry: {rp.entry} | Stop: {rp.stop} | Target 1 (2R): {rp.target1} | Target 2 (3R): {rp.target2}")
        lines.append(f"- Risiko/Aktie: {rp.risk_per_share} | Positionsgroesse: {rp.shares} Stueck | Kapitalrisiko: {rp.risk_dollars}")
        lines.append(f"- R:R (roh): {rp.rr_raw} | R:R (nach Kosten): {rp.rr_after_costs}")
        lines.append(f"- Time-Stop: {rp.time_stop_sessions} Sessions")
        lines.append(f"- Invalidation: {rp.invalidation}")
        if rp.adjustments:
            lines.append(f"- Anpassungen: {'; '.join(rp.adjustments)}")
    else:
        lines.append("**Trade-Plan:** nicht berechenbar (Stop >= Entry oder fehlende Daten).")

    if result.warnings:
        lines.append("")
        lines.append("**Hinweise:** " + "; ".join(result.warnings))
    if c.notes:
        lines.append(f"**Notiz:** {c.notes}")

    return "\n".join(lines)


def render_report(results: list[EvaluationResult], weights: dict | None = None) -> str:
    weights = weights or DEFAULT_WEIGHTS
    confirmed = sorted(
        [r for r in results if not r.auto_rejected and not r.needs_manual_review],
        key=lambda r: r.weighted_score,
        reverse=True,
    )
    manual_review = [r for r in results if not r.auto_rejected and r.needs_manual_review]
    rejected = [r for r in results if r.auto_rejected]

    lines = [
        "# Swing-Trade Evaluation Report",
        "",
        f"- Erstellt am: {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- Kandidaten gesamt: {len(results)} | Bestaetigt: {len(confirmed)} | "
        f"Manuelle Pruefung noetig: {len(manual_review)} | Abgelehnt: {len(rejected)}",
        "- Gewichtung: " + ", ".join(f"{k}={v * 100:.0f}%" for k, v in weights.items()),
        "",
        "**Analyse, keine Anlageberatung.** Gewichtungen sind Platzhalter (gleichgewichtet, "
        "sofern nicht per --weights ueberschrieben) - das Framework selbst verlangt, dass "
        "Gewichte aus einem Walk-Forward-Backtest stammen, nicht aus Annahmen. Jede UNKNOWN-Markierung "
        "bedeutet 'nicht verifizierbar', nicht 'bestanden'.",
        "",
        "---",
        "",
        "## Ranking (bestaetigte Kandidaten, alle Gates PASS)",
        "",
    ]

    if confirmed:
        lines.append("| Rang | Ticker | Playbook | Score | A+ | Entry | Stop | R:R (n. Kosten) |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for i, r in enumerate(confirmed, 1):
            rp = r.risk_plan
            lines.append(
                f"| {i} | {r.candidate.ticker} | {r.candidate.playbook} | {r.weighted_score:.1f} | "
                f"{'✓' if r.is_a_plus else ''} | {rp.entry} | {rp.stop} | {rp.rr_after_costs} |"
            )
    else:
        lines.append("_Kein Kandidat hat alle Gates bestanden._")

    sector_warnings = sector_concentration_warnings(results)
    if sector_warnings:
        lines.append("")
        lines.append("**Portfolio-Hinweise:**")
        lines.extend(f"- {w}" for w in sector_warnings)

    lines.append("")
    lines.append("---")
    lines.append("")

    if confirmed:
        lines.append("## Bestaetigte Kandidaten im Detail")
        lines.append("")
        for r in confirmed:
            lines.append(_candidate_section(r))
            lines.append("")

    if manual_review:
        lines.append("## Manuelle Pruefung noetig (mind. ein Gate nicht verifizierbar)")
        lines.append("")
        for r in manual_review:
            lines.append(_candidate_section(r))
            lines.append("")

    if rejected:
        lines.append("## Abgelehnt")
        lines.append("")
        for r in rejected:
            failed = [g for g in r.gates if g.status == "fail"]
            reasons = "; ".join(f"{g.code}: {g.detail}" for g in failed) or "Trade-Plan ungueltig"
            lines.append(f"- **{r.candidate.ticker}**: {reasons}")
        lines.append("")

    lines.append(CHECKLIST)

    return "\n".join(lines)
