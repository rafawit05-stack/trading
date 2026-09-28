"""Optionale Telegram-Benachrichtigung nach einem swing_trade-Lauf bzw. Positions-Check.

Nutzt die Telegram Bot API direkt per HTTPS (kein SDK noetig) - siehe README
fuer die Schritt-fuer-Schritt-Anleitung zum Anlegen des Bots.
"""

from __future__ import annotations

import os

import requests

from .models import EvaluationResult, PositionStatus

MAX_CANDIDATES_IN_MESSAGE = 3

ACTIONABLE_POSITION_STATUSES = {"stop_hit", "target1_hit", "target2_hit", "time_stop_expired"}

TELEGRAM_API_BASE = "https://api.telegram.org"


class NotifyConfigError(RuntimeError):
    """Fehlende oder unvollstaendige Telegram-Konfiguration."""


def send_message(text: str, chat_id: str | None = None) -> int:
    """Verschickt `text` per Telegram-Bot. Gibt die Telegram message_id zurueck.

    Zugangsdaten aus TELEGRAM_BOT_TOKEN; Ziel-Chat aus `chat_id` oder
    TELEGRAM_CHAT_ID (Parameter hat Vorrang).
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    target_chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")

    missing = [
        name
        for name, value in [("TELEGRAM_BOT_TOKEN", token), ("TELEGRAM_CHAT_ID", target_chat_id)]
        if not value
    ]
    if missing:
        raise NotifyConfigError("Fehlende Telegram-Konfiguration: " + ", ".join(missing))

    response = requests.post(
        f"{TELEGRAM_API_BASE}/bot{token}/sendMessage",
        json={"chat_id": target_chat_id, "text": text},
        timeout=10,
    )
    if not response.ok:
        raise NotifyConfigError(f"Telegram-API-Fehler ({response.status_code}): {response.text}")

    return response.json()["result"]["message_id"]


def build_summary_message(results: list[EvaluationResult]) -> str:
    confirmed = sorted(
        [r for r in results if not r.auto_rejected and not r.needs_manual_review],
        key=lambda r: r.weighted_score,
        reverse=True,
    )
    a_plus = [r for r in confirmed if r.is_a_plus]

    lines = [
        f"Swing-Trade: {len(results)} geprueft, {len(confirmed)} bestaetigt"
        + (f", {len(a_plus)} A+" if a_plus else "")
        + "."
    ]

    top = confirmed[:MAX_CANDIDATES_IN_MESSAGE]
    for r in top:
        rp = r.risk_plan
        marker = " A+" if r.is_a_plus else ""
        lines.append(
            f"{r.candidate.ticker}{marker}: Entry {rp.entry} Stop {rp.stop} "
            f"R:R {rp.rr_after_costs}"
        )

    if not confirmed:
        lines.append("Kein Kandidat hat alle Gates bestanden.")

    lines.append("Analyse, keine Anlageberatung.")
    return "\n".join(lines)


def send_summary_alert(results: list[EvaluationResult], chat_id: str | None = None) -> int:
    """Verschickt eine Kurzsummary neuer Kandidaten per Telegram. Gibt die
    Telegram message_id zurueck."""
    return send_message(build_summary_message(results), chat_id=chat_id)


def build_exit_message(status: PositionStatus) -> str:
    p = status.position
    label = {
        "stop_hit": "STOP",
        "target1_hit": "TARGET 1",
        "target2_hit": "TARGET 2",
        "time_stop_expired": "TIME-STOP",
    }[status.status]
    price = status.trigger_price if status.trigger_price is not None else status.current_price
    return (
        f"{p.ticker} {label}: {price} erreicht am {status.trigger_date}.\n"
        f"{status.action}\n"
        "Analyse, keine Anlageberatung."
    )


def send_exit_alerts(statuses: list[PositionStatus], chat_id: str | None = None) -> list[int]:
    """Verschickt fuer jede Position mit einem ausgeloesten Stop/Target/Time-Stop
    eine eigene Telegram-Nachricht. Gibt die Liste der verschickten message_ids
    zurueck. Positionen im Status "open" werden nicht gemeldet.
    """
    message_ids = []
    for status in statuses:
        if status.status in ACTIONABLE_POSITION_STATUSES:
            message_ids.append(send_message(build_exit_message(status), chat_id=chat_id))
    return message_ids
