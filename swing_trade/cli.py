"""Kommandozeilen-Interface fuer das Swing-Trade Evaluation Framework."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from .evaluate import DEFAULT_WEIGHTS, evaluate_candidate
from .notify import NotifyConfigError, send_sms_summary
from .report import render_report
from .watchlist import load_watchlist

REPORTS_DIR = Path("reports")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="swing-trade",
        description="Bewertet eine Watchlist nach dem Swing-Trade Evaluation Framework (Gates, Scoring, Risk-Plan).",
    )
    parser.add_argument("watchlist", type=Path, help="Pfad zur Watchlist-CSV (siehe watchlist.example.csv)")
    parser.add_argument("--data-source", choices=["yfinance", "csv"], default="yfinance")
    parser.add_argument("--price-dir", type=Path, default=None, help="Verzeichnis mit <TICKER>.csv (nur bei --data-source csv)")
    parser.add_argument("--capital", type=float, default=10_000.0, help="Kapitalbasis fuer die Positionsgroesse")
    parser.add_argument("--risk-pct", type=float, default=1.0, help="Risiko pro Trade in %% des Kapitals (Standard: 1%%, A+ Setups: 2%%)")
    parser.add_argument("--risk-pct-a-plus", type=float, default=2.0)
    parser.add_argument("--commission-bps", type=float, default=5.0, help="Kommission je Order in Basispunkten")
    parser.add_argument("--slippage-bps", type=float, default=5.0, help="Erwartete Slippage in Basispunkten")
    parser.add_argument("--hold-sessions-max", type=int, default=10, help="Time-Stop in Handelstagen")
    parser.add_argument(
        "--weights",
        type=str,
        default=None,
        help="Eigene Gewichtung als 'Konzept=Zahl,...' (z.B. aus einem Backtest), sonst Gleichgewichtung.",
    )
    parser.add_argument("--output", "-o", type=Path, default=None)
    parser.add_argument(
        "--notify-sms",
        action="store_true",
        help="Kurzsummary per Twilio-SMS verschicken (Zugangsdaten aus TWILIO_*-Umgebungsvariablen).",
    )
    parser.add_argument(
        "--sms-to",
        type=str,
        default=None,
        help="Zielnummer fuer --notify-sms, ueberschreibt TWILIO_TO_NUMBER.",
    )
    return parser.parse_args(argv)


def _parse_weights(raw: str | None) -> dict[str, float] | None:
    if not raw:
        return None
    parts = [p.split("=") for p in raw.split(",")]
    weights = {k.strip(): float(v) for k, v in parts}
    total = sum(weights.values())
    if total <= 0:
        raise SystemExit("Fehler: Summe der Gewichte muss groesser als 0 sein.")
    return {k: v / total for k, v in weights.items()}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.data_source == "csv" and args.price_dir is None:
        print("Fehler: --price-dir ist erforderlich fuer --data-source csv", file=sys.stderr)
        return 1

    defaults = dict(
        capital=args.capital,
        risk_pct_default=args.risk_pct,
        risk_pct_a_plus=args.risk_pct_a_plus,
        commission_bps=args.commission_bps,
        slippage_bps=args.slippage_bps,
        hold_sessions_max=args.hold_sessions_max,
    )

    try:
        entries = load_watchlist(args.watchlist, defaults)
    except (ValueError, FileNotFoundError) as exc:
        print(f"Fehler beim Einlesen der Watchlist: {exc}", file=sys.stderr)
        return 1

    weights = _parse_weights(args.weights) or DEFAULT_WEIGHTS

    results = []
    for candidate, sentiment_score in entries:
        print(f"Bewerte {candidate.ticker} ({candidate.market}, Playbook {candidate.playbook}) ...", file=sys.stderr)
        try:
            result = evaluate_candidate(
                candidate,
                data_source=args.data_source,
                price_dir=args.price_dir,
                weights=weights,
                sentiment_score=sentiment_score,
            )
            results.append(result)
        except Exception as exc:
            print(f"  Übersprungen ({candidate.ticker}): {exc}", file=sys.stderr)

    if not results:
        print("Keine Kandidaten konnten bewertet werden.", file=sys.stderr)
        return 1

    report = render_report(results, weights)

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = args.output or (REPORTS_DIR / f"swing_trade_report_{timestamp}.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")

    print(f"Report gespeichert unter: {output_path}", file=sys.stderr)
    print(report)

    if args.notify_sms:
        try:
            sid = send_sms_summary(results, to_number=args.sms_to)
            print(f"SMS-Summary verschickt (SID: {sid})", file=sys.stderr)
        except NotifyConfigError as exc:
            print(f"SMS-Summary nicht verschickt: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
