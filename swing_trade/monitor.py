"""CLI zum Ueberwachen offener Positionen: prueft Stop/Target/Time-Stop gegen
den aktuellen Kursverlauf, dokumentiert das Ergebnis als Markdown-Report und
verschickt optional eine SMS pro ausgeloester Position (Stop/Target/Time-Stop).

Ergaenzt `swing_trade` (das NEUE Kandidaten aus einer Watchlist bewertet) um
die Ueberwachung von Trades, die bereits eroeffnet wurden.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from .notify import NotifyConfigError, send_exit_alerts
from .positions import evaluate_position, load_positions, render_position_report

REPORTS_DIR = Path("reports")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="swing-trade-monitor",
        description="Prueft offene Positionen gegen Stop/Target/Time-Stop und dokumentiert das Ergebnis.",
    )
    parser.add_argument("positions", type=Path, help="Pfad zur Positions-CSV (siehe positions.example.csv)")
    parser.add_argument("--data-source", choices=["yfinance", "csv"], default="yfinance")
    parser.add_argument("--price-dir", type=Path, default=None, help="Verzeichnis mit <TICKER>.csv (nur bei --data-source csv)")
    parser.add_argument("--output", "-o", type=Path, default=None)
    parser.add_argument(
        "--notify-sms",
        action="store_true",
        help="Bei jeder ausgeloesten Position (Stop/Target/Time-Stop) eine eigene Twilio-SMS verschicken.",
    )
    parser.add_argument("--sms-to", type=str, default=None, help="Zielnummer fuer --notify-sms, ueberschreibt TWILIO_TO_NUMBER.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.data_source == "csv" and args.price_dir is None:
        print("Fehler: --price-dir ist erforderlich fuer --data-source csv", file=sys.stderr)
        return 1

    try:
        positions = load_positions(args.positions)
    except (ValueError, FileNotFoundError) as exc:
        print(f"Fehler beim Einlesen der Positionen: {exc}", file=sys.stderr)
        return 1

    if not positions:
        print("Keine Positionen in der Datei.", file=sys.stderr)
        return 1

    statuses = []
    for position in positions:
        print(f"Pruefe {position.ticker} ...", file=sys.stderr)
        try:
            statuses.append(evaluate_position(position, data_source=args.data_source, price_dir=args.price_dir))
        except Exception as exc:
            print(f"  Uebersprungen ({position.ticker}): {exc}", file=sys.stderr)

    if not statuses:
        print("Keine Position konnte geprueft werden.", file=sys.stderr)
        return 1

    report = render_position_report(statuses)

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = args.output or (REPORTS_DIR / f"position_check_{timestamp}.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")

    print(f"Report gespeichert unter: {output_path}", file=sys.stderr)
    print(report)

    if args.notify_sms:
        try:
            sids = send_exit_alerts(statuses, to_number=args.sms_to)
            if sids:
                print(f"{len(sids)} SMS-Alert(s) verschickt: {', '.join(sids)}", file=sys.stderr)
            else:
                print("Keine SMS verschickt - keine Position hat Stop/Target/Time-Stop ausgeloest.", file=sys.stderr)
        except NotifyConfigError as exc:
            print(f"SMS-Alerts nicht verschickt: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
