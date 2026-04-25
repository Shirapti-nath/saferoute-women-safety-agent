"""Journey tracker — monitors expected arrival and fires alert on timeout."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from config import JOURNEY_BUFFER_MINUTES

logger = logging.getLogger("saferoute.journey_tracker")


@dataclass
class JourneySession:
    """State for one active journey."""
    user_name: str
    destination: str
    started_at: datetime
    expected_arrival: datetime
    deadline: datetime          # expected_arrival + buffer
    contacts: list[str]
    confirmed_safe: bool = False
    alert_fired: bool = False

    def minutes_remaining(self) -> int:
        """Minutes left before the alert deadline."""
        delta = self.deadline - datetime.now()
        return max(0, int(delta.total_seconds() / 60))

    def is_overdue(self) -> bool:
        return datetime.now() > self.deadline and not self.confirmed_safe

    def status_label(self) -> str:
        if self.confirmed_safe:
            return "✅ Arrived safely"
        if self.is_overdue():
            return "🔴 OVERDUE — alert triggered"
        mins = self.minutes_remaining()
        return f"🟡 Active — {mins} min until deadline"


@dataclass
class JourneyStatus:
    """Snapshot returned to the UI / agent."""
    active: bool
    session: Optional[JourneySession]
    alert_should_fire: bool
    message: str


# ── Module-level active session (single-user Streamlit app) ──────────────────
_active_session: Optional[JourneySession] = None


def start_journey(
    user_name: str,
    destination: str,
    expected_arrival_iso: str,
    contacts: list[str],
) -> JourneySession:
    """Start tracking a new journey.

    Args:
        user_name: Name of the traveller.
        destination: End location string.
        expected_arrival_iso: ISO datetime string for expected arrival.
        contacts: List of trusted contact phone numbers.

    Returns:
        The new JourneySession.
    """
    global _active_session

    try:
        arrival_dt = datetime.fromisoformat(expected_arrival_iso)
    except ValueError:
        # Default: 30 minutes from now
        arrival_dt = datetime.now() + timedelta(minutes=30)
        logger.warning("Invalid arrival time '%s' — defaulting to 30 min", expected_arrival_iso)

    deadline = arrival_dt + timedelta(minutes=JOURNEY_BUFFER_MINUTES)

    session = JourneySession(
        user_name=user_name,
        destination=destination,
        started_at=datetime.now(),
        expected_arrival=arrival_dt,
        deadline=deadline,
        contacts=contacts,
    )

    _active_session = session
    logger.info(
        "Journey started: %s → %s | ETA %s | Deadline %s",
        user_name, destination, arrival_dt.strftime("%H:%M"), deadline.strftime("%H:%M"),
    )
    return session


def confirm_safe_arrival() -> JourneyStatus:
    """Mark the active journey as safely completed."""
    global _active_session

    if _active_session is None:
        return JourneyStatus(
            active=False,
            session=None,
            alert_should_fire=False,
            message="No active journey to confirm.",
        )

    _active_session.confirmed_safe = True
    logger.info("Safe arrival confirmed by %s", _active_session.user_name)

    msg = (
        f"✅ {_active_session.user_name} confirmed safe arrival at "
        f"{_active_session.destination}. Journey complete."
    )
    status = JourneyStatus(active=False, session=_active_session, alert_should_fire=False, message=msg)
    _active_session = None
    return status


def get_journey_status() -> JourneyStatus:
    """Return the current state of the active journey (if any)."""
    if _active_session is None:
        return JourneyStatus(
            active=False,
            session=None,
            alert_should_fire=False,
            message="No active journey.",
        )

    should_fire = _active_session.is_overdue() and not _active_session.alert_fired

    if should_fire:
        _active_session.alert_fired = True
        msg = (
            f"⚠️ {_active_session.user_name} has not confirmed arrival at "
            f"{_active_session.destination}. Sending alert to contacts."
        )
    else:
        msg = _active_session.status_label()

    return JourneyStatus(
        active=True,
        session=_active_session,
        alert_should_fire=should_fire,
        message=msg,
    )


def cancel_journey() -> str:
    """Cancel the active journey without firing an alert."""
    global _active_session
    if _active_session is None:
        return "No active journey to cancel."
    name = _active_session.user_name
    _active_session = None
    return f"Journey cancelled for {name}."


def format_eta(arrival_iso: str) -> str:
    """Return a human-friendly ETA string from an ISO datetime."""
    try:
        dt = datetime.fromisoformat(arrival_iso)
        deadline = dt + timedelta(minutes=JOURNEY_BUFFER_MINUTES)
        return (
            f"Expected arrival: {dt.strftime('%I:%M %p')}\n"
            f"Alert fires if not confirmed by: {deadline.strftime('%I:%M %p')}"
        )
    except ValueError:
        return "Invalid time format."
