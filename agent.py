"""SafeRoute LangChain agent — orchestrates all tools with Gemini 2.5 Flash."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_TEMPERATURE, GEMINI_MAX_TOKENS

logger = logging.getLogger("saferoute.agent")


@dataclass
class AgentResponse:
    """Unified response envelope from the SafeRoute agent."""
    action: str
    success: bool
    data: dict[str, Any]
    narrative: str           # Plain-English summary for the UI
    used_ai: bool


# ── Gemini plain-text helper ──────────────────────────────────────────────────

def _gemini_explain(prompt: str, fallback: str) -> tuple[str, bool]:
    """Call Gemini for a short plain-English explanation.

    Returns (text, used_ai). Falls back to `fallback` on any error.
    """
    if not GEMINI_API_KEY:
        return fallback, False
    try:
        import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            generation_config={
                "temperature": GEMINI_TEMPERATURE,
                "max_output_tokens": GEMINI_MAX_TOKENS,
            },
        )
        response = model.generate_content(prompt)
        return response.text.strip(), True
    except Exception as exc:
        logger.warning("Gemini explain call failed: %s", exc)
        return fallback, False


# ── SafeRoute Agent ───────────────────────────────────────────────────────────

class SafeRouteAgent:
    """Central agent that ties all SafeRoute tools together.

    LLM (Gemini) is used ONLY for natural language understanding and generation.
    All computation — scoring, timers, contact management — is pure Python.
    """

    def __init__(self) -> None:
        self._contacts: list[str] = []
        self._user_name: str = "Traveller"
        logger.info("SafeRouteAgent initialised (AI=%s)", "enabled" if GEMINI_API_KEY else "rule-based")

    # ── Contact management ────────────────────────────────────────────────────

    def set_user_profile(self, name: str, contacts: list[str]) -> None:
        """Store user name and trusted contacts in memory."""
        self._user_name = name.strip() or "Traveller"
        self._contacts = [c.strip() for c in contacts if c.strip()]
        logger.info("Profile updated: name=%s contacts=%d", self._user_name, len(self._contacts))

    # ── Tool 1: Analyse route ─────────────────────────────────────────────────

    def analyse_route(
        self,
        source: str,
        destination: str,
        travel_time: str = "now",
    ) -> AgentResponse:
        """Geocode, score, and explain the safest route.

        Pure Python scoring + optional Gemini narrative.
        """
        from tools.route_analyser import analyse_route as _analyse

        try:
            analysis = _analyse(source, destination, travel_time)
            rec = analysis.recommended

            fallback_narrative = (
                f"The {rec.route_label} scores {rec.overall_score}/100 ({rec.safety_label}). "
                f"Distance: {rec.distance_km:.1f} km (~{rec.duration_minutes} min). "
                + (f"⚠️ Night travel detected — extra caution advised. " if analysis.is_night else "")
                + (f"Risk factors: {'; '.join(rec.penalties[:2])}." if rec.penalties else "Route looks clear.")
            )

            prompt = f"""You are a women safety navigation assistant in Pune, India.
A user wants to travel from {source} to {destination} {'at night' if analysis.is_night else 'during the day'}.

Route safety score: {rec.overall_score}/100
Safety rating: {rec.safety_label}
Distance: {rec.distance_km:.1f} km
Estimated time: {rec.duration_minutes} minutes
Risk factors: {'; '.join(rec.penalties[:3]) if rec.penalties else 'None significant'}
Positive factors: {'; '.join(rec.bonuses[:3]) if rec.bonuses else 'None noted'}

Write a 2-3 sentence friendly, reassuring explanation of this route for the traveller.
Be specific about the safety rating and give one concrete piece of advice."""

            narrative, used_ai = _gemini_explain(prompt, fallback_narrative)

            return AgentResponse(
                action="analyse_route",
                success=True,
                data={
                    "analysis": analysis,
                    "source_lat": analysis.source_location.lat,
                    "source_lon": analysis.source_location.lon,
                    "dest_lat": analysis.destination_location.lat,
                    "dest_lon": analysis.destination_location.lon,
                    "primary_score": analysis.primary.overall_score,
                    "alt_score": analysis.alternative.overall_score,
                    "recommended_label": rec.safety_label,
                    "recommended_score": rec.overall_score,
                    "is_night": analysis.is_night,
                    "penalties": rec.penalties,
                    "bonuses": rec.bonuses,
                    "police_station": analysis.police_station,
                    "zones": analysis.all_zones,
                },
                narrative=narrative,
                used_ai=used_ai,
            )

        except Exception as exc:
            logger.error("analyse_route failed: %s", exc)
            return AgentResponse(
                action="analyse_route",
                success=False,
                data={},
                narrative=f"Could not analyse route: {exc}. Please check the addresses and try again.",
                used_ai=False,
            )

    # ── Tool 2: Distress detection ────────────────────────────────────────────

    def detect_distress(self, user_message: str) -> AgentResponse:
        """Analyse user message for distress signals and recommend action."""
        from tools.distress_detector import detect_distress as _detect

        try:
            result = _detect(user_message)

            if result.is_distress:
                narrative = (
                    f"⚠️ {result.ai_analysis}\n\n"
                    f"**Recommended action:** {result.recommended_action}\n\n"
                    f"Risk level: **{result.risk_level.upper()}** "
                    f"(confidence: {result.confidence:.0%})"
                )
            else:
                narrative = (
                    f"✅ No distress signals detected in your message.\n"
                    f"{result.recommended_action}"
                )

            return AgentResponse(
                action="detect_distress",
                success=True,
                data={
                    "is_distress": result.is_distress,
                    "risk_level": result.risk_level,
                    "confidence": result.confidence,
                    "signals": result.detected_signals,
                    "action": result.recommended_action,
                    "used_ai": result.used_ai,
                },
                narrative=narrative,
                used_ai=result.used_ai,
            )

        except Exception as exc:
            logger.error("detect_distress failed: %s", exc)
            return AgentResponse(
                action="detect_distress",
                success=False,
                data={"is_distress": False, "risk_level": "none"},
                narrative="Could not analyse message. If you feel unsafe, call 100 (Police) immediately.",
                used_ai=False,
            )

    # ── Tool 3: Safety tips ───────────────────────────────────────────────────

    def generate_safety_tips(
        self,
        source: str,
        destination: str,
        route_data: dict[str, Any],
        time_of_day: str = "now",
    ) -> AgentResponse:
        """Generate personalised safety tips for the journey."""
        from tools.safety_tips import generate_safety_tips as _tips

        try:
            result = _tips(source, destination, route_data, time_of_day)

            narrative = "**Your personalised safety tips:**\n" + "\n".join(
                f"• {tip}" for tip in result.tips
            )

            return AgentResponse(
                action="generate_safety_tips",
                success=True,
                data={
                    "tips": result.tips,
                    "general": result.general_guidelines,
                    "context": result.context_summary,
                    "used_ai": result.used_ai,
                },
                narrative=narrative,
                used_ai=result.used_ai,
            )

        except Exception as exc:
            logger.error("generate_safety_tips failed: %s", exc)
            return AgentResponse(
                action="generate_safety_tips",
                success=False,
                data={"tips": [], "general": []},
                narrative="Could not generate tips. General advice: stay on main roads and share your location.",
                used_ai=False,
            )

    # ── Tool 4: SOS trigger ───────────────────────────────────────────────────

    def trigger_sos(self, location: str) -> AgentResponse:
        """Send SOS alerts to all registered trusted contacts."""
        from tools.alert_system import trigger_sos as _sos

        try:
            result = _sos(self._user_name, location, self._contacts)

            if result.success:
                method_label = "SMS sent via Twilio" if result.method == "twilio" else "Alert simulated (Twilio not configured)"
                narrative = (
                    f"🆘 SOS ALERT DISPATCHED\n"
                    f"{method_label} to {len(result.contacts_notified)} contact(s).\n"
                    f"Time: {result.timestamp}\n"
                    f"Message sent: \"{result.message_sent[:80]}…\""
                )
            else:
                narrative = f"⚠️ SOS could not be sent: {result.error}"

            return AgentResponse(
                action="trigger_sos",
                success=result.success,
                data={
                    "method": result.method,
                    "notified": result.contacts_notified,
                    "failed": result.contacts_failed,
                    "message": result.message_sent,
                    "timestamp": result.timestamp,
                },
                narrative=narrative,
                used_ai=False,
            )

        except Exception as exc:
            logger.error("trigger_sos failed: %s", exc)
            return AgentResponse(
                action="trigger_sos",
                success=False,
                data={},
                narrative=f"SOS failed: {exc}. Call 100 (Police) or 1091 (Women Helpline) immediately.",
                used_ai=False,
            )

    # ── Tool 5: Journey tracking ──────────────────────────────────────────────

    def start_journey(
        self,
        destination: str,
        expected_arrival_iso: str,
    ) -> AgentResponse:
        """Start journey monitoring."""
        from tools.journey_tracker import start_journey as _start, format_eta

        try:
            session = _start(self._user_name, destination, expected_arrival_iso, self._contacts)

            narrative = (
                f"🗺️ Journey started!\n"
                f"{format_eta(expected_arrival_iso)}\n"
                f"If you don't confirm safe arrival within {15} min of ETA, "
                f"an alert will be sent to your {len(self._contacts)} contact(s)."
            )

            return AgentResponse(
                action="start_journey",
                success=True,
                data={
                    "destination": destination,
                    "started_at": session.started_at.isoformat(),
                    "expected_arrival": session.expected_arrival.isoformat(),
                    "deadline": session.deadline.isoformat(),
                },
                narrative=narrative,
                used_ai=False,
            )

        except Exception as exc:
            logger.error("start_journey failed: %s", exc)
            return AgentResponse(
                action="start_journey",
                success=False,
                data={},
                narrative=f"Could not start journey tracker: {exc}",
                used_ai=False,
            )

    def check_journey_and_alert(self) -> AgentResponse:
        """Poll journey status and fire alert if overdue."""
        from tools.journey_tracker import get_journey_status
        from tools.alert_system import trigger_journey_alert

        status = get_journey_status()

        if status.alert_should_fire and status.session:
            alert = trigger_journey_alert(
                status.session.user_name,
                status.session.destination,
                status.session.contacts,
            )
            narrative = (
                f"{status.message}\n"
                f"Alert sent to {len(alert.contacts_notified)} contact(s) via {alert.method}."
            )
        else:
            narrative = status.message

        return AgentResponse(
            action="check_journey",
            success=True,
            data={
                "active": status.active,
                "alert_fired": status.alert_should_fire,
                "message": status.message,
            },
            narrative=narrative,
            used_ai=False,
        )

    def confirm_safe_arrival(self) -> AgentResponse:
        """Confirm the user arrived safely and close the journey."""
        from tools.journey_tracker import confirm_safe_arrival as _confirm

        status = _confirm()
        return AgentResponse(
            action="confirm_safe_arrival",
            success=True,
            data={"active": status.active},
            narrative=status.message,
            used_ai=False,
        )
