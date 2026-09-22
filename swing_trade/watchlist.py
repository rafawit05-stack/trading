"""Einlesen der Watchlist-CSV-Datei.

Erwartete Spalten (Reihenfolge egal):
  ticker           - Pflicht, z.B. AAPL oder SAP.DE
  market           - Pflicht, "US" oder "EU"
  playbook         - Pflicht, "A" (Breakout) oder "B" (Pullback)
  sector           - optional, fuer die Klumpenrisiko-Warnung
  red_flag         - optional, Freitext -> fuehrt zu automatischem Ausschluss (G5)
  earnings_is_thesis - optional, "true"/"false" (Default false)
  sentiment_score  - optional, 0-10
  notes            - optional, Freitext
"""

from __future__ import annotations

import csv
from pathlib import Path

from .models import CandidateInput

REQUIRED_COLUMNS = {"ticker", "market", "playbook"}


def _parse_bool(value: str | None) -> bool:
    return str(value).strip().lower() in ("true", "1", "yes", "ja")


def load_watchlist(path: Path, defaults: dict) -> list[tuple[CandidateInput, float | None]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED_COLUMNS - set(c.strip() for c in (reader.fieldnames or []))
        if missing:
            raise ValueError(f"Watchlist-Datei fehlen Pflichtspalten: {', '.join(sorted(missing))}")

        rows = []
        for row in reader:
            ticker = row["ticker"].strip()
            market = row["market"].strip().upper()
            playbook = row["playbook"].strip().upper()
            if market not in ("US", "EU"):
                raise ValueError(f"Ungueltiger market fuer {ticker}: {market!r} (erwartet US/EU)")
            if playbook not in ("A", "B"):
                raise ValueError(f"Ungueltiger playbook fuer {ticker}: {playbook!r} (erwartet A/B)")

            sentiment_raw = (row.get("sentiment_score") or "").strip()
            sentiment_score = float(sentiment_raw) if sentiment_raw else None

            candidate = CandidateInput(
                ticker=ticker,
                market=market,
                playbook=playbook,
                sector=(row.get("sector") or "").strip() or None,
                red_flag=(row.get("red_flag") or "").strip() or None,
                earnings_is_thesis=_parse_bool(row.get("earnings_is_thesis")),
                notes=(row.get("notes") or "").strip() or None,
                **defaults,
            )
            rows.append((candidate, sentiment_score))
        return rows
