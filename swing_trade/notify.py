"""Optionale Twilio-SMS-Benachrichtigung nach einem swing_trade-Lauf."""

from __future__ import annotations

import os

from .models import EvaluationResult, PositionStatus

MAX_CANDIDATES_IN_SMS = 3

ACTIONABLE_POSITION_STATUSES = {"stop_hit", "target1_hit", "target2_hit", "time_stop_expired"}


class NotifyConfigError(RuntimeError):
    """Fehlende oder unvollstaendige Twilio-Konfiguration."""


def _twilio_client_and_from():
    try:
        from twilio.rest import Client
    except ImportError as exc:
        raise NotifyConfigError(
            "twilio ist nicht installiert - `pip install -r requirements.txt` ausfuehren."
        ) from exc

    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_FROM_NUMBER")

    missing = [
        name
        for name, value in [
            ("TWILIO_ACCOUNT_SID", account_sid),
            ("TWILIO_AUTH_TOKEN", auth_token),
            ("TWILIO_FROM_NUMBER", from_number),
        ]
        if not value
    ]
    if missing:
        raise NotifyConfigError("Fehlende Twilio-Konfiguration: " + ", ".join(missing))

    return Client(account_sid, auth_token), from_number


def send_sms(body: str, to_number: str | None = None) -> str:
    """Verschickt `body` per Twilio-SMS. Gibt die Nachricht-SID zurueck.

    Zielnummer aus `to_number` oder TWILIO_TO_NUMBER (Parameter hat Vorrang).
    """
    client, from_number = _twilio_client_and_from()
    target_number = to_number or os.environ.get("TWILIO_TO_NUMBER")
    if not target_number:
        raise NotifyConfigError("Fehlende Twilio-Konfiguration: TWILIO_TO_NUMBER")

    message = client.messages.create(body=body, from_=from_number, to=target_number)
    return message.sid


def build_sms_summary(results: list[EvaluationResult]) -> str:
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

    top = confirmed[:MAX_CANDIDATES_IN_SMS]
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


def send_sms_summary(results: list[EvaluationResult], to_number: str | None = None) -> str:
    """Verschickt eine SMS-Kurzsummary neuer Kandidaten via Twilio. Gibt die
    Nachricht-SID zurueck."""
    return send_sms(build_sms_summary(results), to_number=to_number)


def build_exit_sms(status: PositionStatus) -> str:
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


def send_exit_alerts(statuses: list[PositionStatus], to_number: str | None = None) -> list[str]:
    """Verschickt fuer jede Position mit einem ausgeloesten Stop/Target/Time-Stop
    eine eigene SMS. Gibt die Liste der verschickten Nachricht-SIDs zurueck.
    Positionen im Status "open" werden nicht gemeldet.
    """
    sids = []
    for status in statuses:
        if status.status in ACTIONABLE_POSITION_STATUSES:
            sids.append(send_sms(build_exit_sms(status), to_number=to_number))
    return sids
