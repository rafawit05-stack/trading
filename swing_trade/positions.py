"""Einlesen offener Positionen und Abgleich mit dem Kursverlauf: Stop/Target/
Time-Stop-Ueberwachung fuer bereits eroeffnete Trades (im Unterschied zu
evaluate.py, das NEUE Kandidaten aus einer Watchlist bewertet).

Erwartete Spalten in der Positions-CSV (Reihenfolge egal):
  ticker, market, playbook, entry_date (YYYY-MM-DD), entry, stop, target1,
  target2, time_stop_sessions, shares (optional), notes (optional)

Diese Werte kommen 1:1 aus dem Trade-Plan, den evaluate_candidate() bei der
Aufnahme des Trades erzeugt hat (siehe reports/*.md).
"""

from __future__ import annotations

import csv
import dataclasses
import datetime as dt
from pathlib import Path

import pandas as pd

from . import data as data_module
from .models import Position, PositionStatus

REQUIRED_COLUMNS = {
    "ticker", "market", "playbook", "entry_date", "entry", "stop", "target1",
    "target2", "time_stop_sessions",
}


def load_positions(path: Path) -> list[Position]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED_COLUMNS - set(c.strip() for c in (reader.fieldnames or []))
        if missing:
            raise ValueError(f"Positions-Datei fehlen Pflichtspalten: {', '.join(sorted(missing))}")

        positions = []
        for row in reader:
            market = row["market"].strip().upper()
            playbook = row["playbook"].strip().upper()
            if market not in ("US", "EU"):
                raise ValueError(f"Ungueltiger market fuer {row['ticker']}: {market!r}")
            if playbook not in ("A", "B"):
                raise ValueError(f"Ungueltiger playbook fuer {row['ticker']}: {playbook!r}")

            shares_raw = (row.get("shares") or "").strip()
            positions.append(
                Position(
                    ticker=row["ticker"].strip(),
                    market=market,
                    playbook=playbook,
                    entry_date=dt.date.fromisoformat(row["entry_date"].strip()),
                    entry=float(row["entry"]),
                    stop=float(row["stop"]),
                    target1=float(row["target1"]),
                    target2=float(row["target2"]),
                    time_stop_sessions=int(row["time_stop_sessions"]),
                    shares=int(shares_raw) if shares_raw else 0,
                    notes=(row.get("notes") or "").strip() or None,
                )
            )
        return positions


def evaluate_position(
    position: Position,
    data_source: str = "yfinance",
    price_dir: Path | None = None,
) -> PositionStatus:
    df = data_module.load_price_history(position.ticker, data_source, price_dir)
    since_entry = df[df.index.date >= position.entry_date]

    if since_entry.empty:
        current_price = df["Close"].iloc[-1]
        return PositionStatus(
            position=position,
            status="open",
            as_of=df.index[-1].date(),
            trigger_date=None,
            trigger_price=None,
            current_price=round(float(current_price), 4),
            sessions_held=0,
            unrealized_pct=round((current_price - position.entry) / position.entry * 100, 2),
            action="Keine Kursdaten seit Entry-Datum - noch nichts zu tun. Naechster Check nach der naechsten Session.",
        )

    status: str = "open"
    trigger_date: dt.date | None = None
    trigger_price: float | None = None

    for idx, row in since_entry.iterrows():
        if row["Low"] <= position.stop:
            status, trigger_date, trigger_price = "stop_hit", idx.date(), position.stop
            break
        if row["High"] >= position.target2:
            status, trigger_date, trigger_price = "target2_hit", idx.date(), position.target2
            break
        if row["High"] >= position.target1:
            status, trigger_date, trigger_price = "target1_hit", idx.date(), position.target1
            break

    sessions_held = len(since_entry) - 1
    last_close = float(df["Close"].iloc[-1])
    as_of = df.index[-1].date()

    if status == "open" and sessions_held >= position.time_stop_sessions:
        status = "time_stop_expired"
        trigger_date = as_of
        trigger_price = last_close

    unrealized_pct = round((last_close - position.entry) / position.entry * 100, 2)

    if status == "stop_hit":
        action = f"STOP GERISSEN am {trigger_date} bei {trigger_price:.2f} - Position gemaess Plan schliessen."
    elif status == "target1_hit":
        action = f"TARGET 1 (2R) erreicht am {trigger_date} bei {trigger_price:.2f} - Teilverkauf/Stop auf Break-even gemaess Plan pruefen."
    elif status == "target2_hit":
        action = f"TARGET 2 (3R) erreicht am {trigger_date} bei {trigger_price:.2f} - Restposition gemaess Plan schliessen bzw. Gewinn sichern."
    elif status == "time_stop_expired":
        action = f"TIME-STOP erreicht ({sessions_held}/{position.time_stop_sessions} Sessions) - Position gemaess Plan schliessen, unabhaengig vom Kurs."
    else:
        action = (
            f"Weiter halten - Stop {position.stop:.2f} und Targets ({position.target1:.2f} / "
            f"{position.target2:.2f}) noch nicht erreicht, Time-Stop bei {position.time_stop_sessions} "
            f"Sessions ({sessions_held} bisher)."
        )

    return PositionStatus(
        position=position,
        status=status,
        as_of=as_of,
        trigger_date=trigger_date,
        trigger_price=round(trigger_price, 4) if trigger_price is not None else None,
        current_price=round(last_close, 4),
        sessions_held=sessions_held,
        unrealized_pct=unrealized_pct,
        action=action,
    )


def render_position_report(statuses: list[PositionStatus]) -> str:
    lines = [
        "# Positions-Check",
        "",
        f"- Erstellt am: {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "**Analyse, keine Anlageberatung.** Stop-Treffer werden ueber das Tagestief seit "
        "Entry-Datum geprueft, Targets ueber das Tageshoch - beides ohne Beruecksichtigung "
        "von Gaps/Slippage bei der tatsaechlichen Ausfuehrung.",
        "",
        "---",
        "",
    ]
    for s in statuses:
        p = s.position
        icon = {
            "open": "⏳",
            "stop_hit": "❌",
            "target1_hit": "✅",
            "target2_hit": "\U0001f3af",
            "time_stop_expired": "⏰",
        }[s.status]
        lines.append(f"## {icon} {p.ticker} ({p.market}, Playbook {p.playbook})")
        lines.append("")
        lines.append(
            f"- Entry: {p.entry} ({p.entry_date}) | Stop: {p.stop} | Target 1: {p.target1} | Target 2: {p.target2}"
        )
        lines.append(
            f"- Aktueller Kurs ({s.as_of}): {s.current_price} | unrealisiert: {s.unrealized_pct:+.2f}% | "
            f"Sessions gehalten: {s.sessions_held}/{p.time_stop_sessions}"
        )
        lines.append(f"- **Status**: {s.status}")
        lines.append(f"- **Aktion**: {s.action}")
        if p.notes:
            lines.append(f"- Notiz: {p.notes}")
        lines.append("")
    return "\n".join(lines)


__all__ = ["load_positions", "evaluate_position", "render_position_report"]
