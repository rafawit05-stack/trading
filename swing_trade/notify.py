"""Optionale Twilio-SMS-Benachrichtigung nach einem swing_trade-Lauf."""

from __future__ import annotations

import os

from .models import EvaluationResult

MAX_CANDIDATES_IN_SMS = 3


class NotifyConfigError(RuntimeError):
    """Fehlende oder unvollstaendige Twilio-Konfiguration."""


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
    """Verschickt eine SMS-Kurzsummary via Twilio. Gibt die Nachricht-SID zurueck.

    Zugangsdaten kommen aus den Umgebungsvariablen TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER; die Zielnummer aus TWILIO_TO_NUMBER
    oder dem Parameter `to_number` (Parameter hat Vorrang).
    """
    try:
        from twilio.rest import Client
    except ImportError as exc:
        raise NotifyConfigError(
            "twilio ist nicht installiert - `pip install -r requirements.txt` ausfuehren."
        ) from exc

    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_FROM_NUMBER")
    target_number = to_number or os.environ.get("TWILIO_TO_NUMBER")

    missing = [
        name
        for name, value in [
            ("TWILIO_ACCOUNT_SID", account_sid),
            ("TWILIO_AUTH_TOKEN", auth_token),
            ("TWILIO_FROM_NUMBER", from_number),
            ("TWILIO_TO_NUMBER", target_number),
        ]
        if not value
    ]
    if missing:
        raise NotifyConfigError(
            "Fehlende Twilio-Konfiguration: " + ", ".join(missing)
        )

    body = build_sms_summary(results)
    client = Client(account_sid, auth_token)
    message = client.messages.create(body=body, from_=from_number, to=target_number)
    return message.sid
