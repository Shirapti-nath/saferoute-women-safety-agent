"""Distress keyword detector with Gemini AI analysis and rule-based fallback."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from config import DISTRESS_KEYWORDS, GEMINI_API_KEY, GEMINI_MODEL, GEMINI_TEMPERATURE

logger = logging.getLogger("saferoute.distress_detector")


@dataclass
class DistressResult:
    """Result from distress analysis."""
    is_distress: bool
    risk_level: str          # "high" | "medium" | "low" | "none"
    confidence: float        # 0.0 – 1.0
    detected_signals: list[str]
    recommended_action: str
    ai_analysis: str
    used_ai: bool


_RISK_COLOURS = {
    "high":   "#C0392B",
    "medium": "#F39C12",
    "low":    "#F1C40F",
    "none":   "#1E8449",
}

_HIGH_RISK_PHRASES = [
    "following me", "being followed", "help me", "i need help",
    "attack", "attacked", "assault", "threatened", "grab",
]

_MEDIUM_RISK_PHRASES = [
    "feel unsafe", "i am scared", "i'm scared", "scared",
    "someone is watching", "watching me", "danger", "unsafe",
    "harassed", "harassment",
]

_LOW_RISK_PHRASES = [
    "nervous", "worried", "anxious", "uncomfortable", "uneasy",
    "suspicious", "strange man", "weird",
]


# ── Rule-based detector (no API key needed) ───────────────────────────────────

def _rule_based_detect(text: str) -> DistressResult:
    """Keyword-matching fallback when Gemini is unavailable."""
    lowered = text.lower()
    signals: list[str] = []
    risk = "none"

    for phrase in _HIGH_RISK_PHRASES:
        if phrase in lowered:
            signals.append(phrase)
            risk = "high"

    if risk != "high":
        for phrase in _MEDIUM_RISK_PHRASES:
            if phrase in lowered:
                signals.append(phrase)
                risk = "medium"

    if risk == "none":
        for phrase in _LOW_RISK_PHRASES:
            if phrase in lowered:
                signals.append(phrase)
                risk = "low"

    is_distress = risk in ("high", "medium")
    confidence = {"high": 0.90, "medium": 0.75, "low": 0.50, "none": 0.95}[risk]

    action_map = {
        "high":   "Immediately move to a crowded public place. Trigger SOS alert now.",
        "medium": "Stay aware of your surroundings. Share your location with a trusted contact.",
        "low":    "Trust your instincts. Move towards a busier area and stay alert.",
        "none":   "No distress signals detected. Stay safe and keep emergency contacts handy.",
    }

    analysis_map = {
        "high":   f"High-risk signals detected: {', '.join(signals)}. Immediate action required.",
        "medium": f"Moderate distress signals: {', '.join(signals)}. Take precautionary steps.",
        "low":    f"Mild unease detected: {', '.join(signals)}. Remain cautious.",
        "none":   "No distress indicators found in the message.",
    }

    return DistressResult(
        is_distress=is_distress,
        risk_level=risk,
        confidence=confidence,
        detected_signals=signals,
        recommended_action=action_map[risk],
        ai_analysis=analysis_map[risk],
        used_ai=False,
    )


# ── Gemini-powered detector ───────────────────────────────────────────────────

def _gemini_detect(text: str) -> Optional[DistressResult]:
    """Use Gemini to analyse distress signals. Returns None on any failure."""
    if not GEMINI_API_KEY:
        return None
    try:
        import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            generation_config={"temperature": GEMINI_TEMPERATURE, "max_output_tokens": 512},
        )

        prompt = f"""You are a women safety AI assistant. Analyse the following message for distress signals.

Message: "{text}"

Respond in this exact format (no extra text):
RISK_LEVEL: <high|medium|low|none>
CONFIDENCE: <0.0-1.0>
SIGNALS: <comma-separated list of detected phrases, or "none">
ACTION: <one sentence recommended action>
ANALYSIS: <one or two sentence analysis>

Rules:
- high = immediate danger (being followed, attacked, needs help NOW)
- medium = feels unsafe, scared, being watched
- low = nervous, anxious, uncomfortable
- none = no distress detected"""

        response = model.generate_content(prompt)
        raw = response.text.strip()
        return _parse_gemini_response(raw)

    except Exception as exc:
        logger.warning("Gemini distress detection failed: %s — falling back to rules", exc)
        return None


def _parse_gemini_response(raw: str) -> Optional[DistressResult]:
    """Parse structured Gemini output into a DistressResult."""
    try:
        lines = {line.split(":", 1)[0].strip(): line.split(":", 1)[1].strip()
                 for line in raw.splitlines() if ":" in line}

        risk = lines.get("RISK_LEVEL", "none").lower()
        if risk not in ("high", "medium", "low", "none"):
            risk = "none"

        confidence = float(lines.get("CONFIDENCE", "0.8"))
        signals_raw = lines.get("SIGNALS", "none")
        signals = [] if signals_raw.lower() == "none" else [s.strip() for s in signals_raw.split(",")]
        action = lines.get("ACTION", "Stay safe and contact emergency services if needed.")
        analysis = lines.get("ANALYSIS", "")

        return DistressResult(
            is_distress=risk in ("high", "medium"),
            risk_level=risk,
            confidence=confidence,
            detected_signals=signals,
            recommended_action=action,
            ai_analysis=analysis,
            used_ai=True,
        )
    except Exception as exc:
        logger.warning("Failed to parse Gemini response: %s", exc)
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def detect_distress(user_message: str) -> DistressResult:
    """Analyse a user message for distress signals.

    Uses Gemini if available, falls back to rule-based detection.
    Never raises — always returns a DistressResult.
    """
    if not user_message or not user_message.strip():
        return DistressResult(
            is_distress=False,
            risk_level="none",
            confidence=1.0,
            detected_signals=[],
            recommended_action="Please type how you are feeling.",
            ai_analysis="No message provided.",
            used_ai=False,
        )

    logger.info("Analysing distress in message (len=%d)", len(user_message))

    # Try Gemini first
    if GEMINI_API_KEY:
        result = _gemini_detect(user_message)
        if result:
            return result

    # Rule-based fallback
    return _rule_based_detect(user_message)


def risk_colour(risk_level: str) -> str:
    """Return the hex colour for a given risk level."""
    return _RISK_COLOURS.get(risk_level, "#888888")
