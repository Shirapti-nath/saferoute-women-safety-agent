"""SOS alert system — Twilio SMS with graceful simulation fallback."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from config import (
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_PHONE_NUMBER,
)

logger = logging.getLogger("saferoute.alert_system")


@dataclass
class AlertResult:
    """Outcome of an SOS or journey alert dispatch."""
    success: bool
    method: str               # "twilio" | "simulated"
    contacts_notified: list[str]
    contacts_failed: list[str]
    message_sent: str
    timestamp: str
    error: Optional[str] = None


def _build_sos_message(user_name: str, location: str) -> str:
    ts = datetime.now().strftime("%d %b %Y %H:%M")
    return (
        f"🆘 SOS ALERT from SafeRoute\n"
        f"{user_name} needs help!\n"
        f"Last known location: {location}\n"
        f"Time: {ts}\n"
        f"Please call them immediately or contact Police: 100"
    )


def _build_journey_alert_message(user_name: str, destination: str) -> str:
    ts = datetime.now().strftime("%d %b %Y %H:%M")
    return (
        f"⚠️ SafeRoute Journey Alert\n"
        f"{user_name} has NOT confirmed safe arrival at {destination}.\n"
        f"Expected arrival was overdue as of {ts}.\n"
        f"Please check on them immediately. Police: 100"
    )


def _twilio_send(to_number: str, message: str) -> tuple[bool, str]:
    """Send one SMS via Twilio. Returns (success, error_or_sid)."""
    try:
        from twilio.rest import Client

        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=to_number,
        )
        logger.info("Twilio SMS sent to %s — SID: %s", to_number, msg.sid)
        return True, msg.sid
    except Exception as exc:
        logger.error("Twilio send failed to %s: %s", to_number, exc)
        return False, str(exc)


def _is_twilio_configured() -> bool:
    return bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER)


def _clean_contacts(contacts: list[str]) -> list[str]:
    """Return non-empty, stripped contact numbers."""
    return [c.strip() for c in contacts if c and c.strip()]


# ── Public API ────────────────────────────────────────────────────────────────

def trigger_sos(
    user_name: str,
    location: str,
    contacts: list[str],
) -> AlertResult:
    """Send SOS SMS to all trusted contacts.

    Uses Twilio when configured; otherwise simulates the alert.
    Never raises — always returns an AlertResult.
    """
    clean_contacts = _clean_contacts(contacts)
    message = _build_sos_message(user_name, location)
    ts = datetime.now().strftime("%d %b %Y %H:%M:%S")

    if not clean_contacts:
        return AlertResult(
            success=False,
            method="none",
            contacts_notified=[],
            contacts_failed=[],
            message_sent=message,
            timestamp=ts,
            error="No trusted contacts configured. Please add contacts in the SOS tab.",
        )

    if not _is_twilio_configured():
        # Graceful simulation
        logger.info("[SIMULATED SOS] Would send to: %s\nMessage:\n%s", clean_contacts, message)
        return AlertResult(
            success=True,
            method="simulated",
            contacts_notified=clean_contacts,
            contacts_failed=[],
            message_sent=message,
            timestamp=ts,
        )

    # Real Twilio dispatch
    notified: list[str] = []
    failed: list[str] = []

    for number in clean_contacts:
        ok, _ = _twilio_send(number, message)
        if ok:
            notified.append(number)
        else:
            failed.append(number)

    return AlertResult(
        success=bool(notified),
        method="twilio",
        contacts_notified=notified,
        contacts_failed=failed,
        message_sent=message,
        timestamp=ts,
        error=f"Failed to reach: {', '.join(failed)}" if failed else None,
    )


def trigger_journey_alert(
    user_name: str,
    destination: str,
    contacts: list[str],
) -> AlertResult:
    """Send a missed-arrival alert to trusted contacts.

    Falls back to simulation when Twilio is not configured.
    """
    clean_contacts = _clean_contacts(contacts)
    message = _build_journey_alert_message(user_name, destination)
    ts = datetime.now().strftime("%d %b %Y %H:%M:%S")

    if not clean_contacts:
        return AlertResult(
            success=False,
            method="none",
            contacts_notified=[],
            contacts_failed=[],
            message_sent=message,
            timestamp=ts,
            error="No trusted contacts configured.",
        )

    if not _is_twilio_configured():
        logger.info("[SIMULATED JOURNEY ALERT] Would send to: %s", clean_contacts)
        return AlertResult(
            success=True,
            method="simulated",
            contacts_notified=clean_contacts,
            contacts_failed=[],
            message_sent=message,
            timestamp=ts,
        )

    notified: list[str] = []
    failed: list[str] = []
    for number in clean_contacts:
        ok, _ = _twilio_send(number, message)
        (notified if ok else failed).append(number)

    return AlertResult(
        success=bool(notified),
        method="twilio",
        contacts_notified=notified,
        contacts_failed=failed,
        message_sent=message,
        timestamp=ts,
        error=f"Failed to reach: {', '.join(failed)}" if failed else None,
    )
