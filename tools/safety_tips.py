"""Personalised safety tips generator using Gemini with rule-based fallback."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_TEMPERATURE

logger = logging.getLogger("saferoute.safety_tips")


@dataclass
class SafetyTipsResult:
    """Personalised tips for a specific journey."""
    tips: list[str]
    general_guidelines: list[str]
    used_ai: bool
    context_summary: str


# ── Static rule-based tips ────────────────────────────────────────────────────

_NIGHT_TIPS = [
    "Share your live location with a trusted contact before starting.",
    "Prefer well-lit main roads even if they are slightly longer.",
    "Keep your phone charged and emergency numbers on speed dial.",
    "Avoid wearing headphones so you stay aware of your surroundings.",
    "Let someone know your expected arrival time.",
]

_HIGH_RISK_TIPS = [
    "Avoid this route if travelling alone — consider a cab or auto.",
    "Travel in groups whenever possible through this area.",
    "Stay on the main road; avoid shortcuts through isolated lanes.",
    "Keep the Women Helpline (1091) ready to dial instantly.",
    "Consider sharing your live location on WhatsApp with a family member.",
]

_MODERATE_TIPS = [
    "Inform a trusted contact about your route and ETA.",
    "Prefer travelling during peak hours when the area is busier.",
    "Keep your bag close and stay aware of people around you.",
    "Trust your instincts — if something feels wrong, move to a crowd.",
    "Identify safe spots (shops, police posts) along the way.",
]

_GENERAL_SAFETY = [
    "Save 100 (Police) and 1091 (Women Helpline) as speed-dial contacts.",
    "Share live location via Google Maps or WhatsApp before solo travel.",
    "Prefer well-lit, populated streets over shortcuts.",
    "Carry a personal safety alarm or whistle.",
    "Avoid displaying expensive jewellery or devices in unfamiliar areas.",
    "Use verified cab services and share ride details with contacts.",
    "If followed, enter a shop or public building — do not go home.",
]

_ISOLATED_SEGMENT_TIP = (
    "This route has {n} isolated stretch(es) — "
    "consider sharing live location before travelling this section."
)


def _rule_based_tips(
    score: int,
    is_night: bool,
    isolated_count: int,
    distance_km: float,
) -> SafetyTipsResult:
    """Generate contextual tips from static rules."""
    tips: list[str] = []

    if is_night:
        tips.extend(_NIGHT_TIPS[:3])

    if score < 60:
        tips.extend(_HIGH_RISK_TIPS[:3])
    elif score < 80:
        tips.extend(_MODERATE_TIPS[:3])

    if isolated_count > 0:
        tips.append(_ISOLATED_SEGMENT_TIP.format(n=isolated_count))

    if distance_km > 3:
        tips.append("For journeys over 3 km, prefer a cab over walking alone.")

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_tips = [t for t in tips if not (t in seen or seen.add(t))]  # type: ignore[func-returns-value]

    ctx = f"Score {score}/100 | {'Night' if is_night else 'Day'} | {distance_km:.1f} km"

    return SafetyTipsResult(
        tips=unique_tips or ["Stay aware of your surroundings and trust your instincts."],
        general_guidelines=_GENERAL_SAFETY,
        used_ai=False,
        context_summary=ctx,
    )


# ── Gemini-powered tips ───────────────────────────────────────────────────────

def _gemini_tips(
    source: str,
    destination: str,
    score: int,
    is_night: bool,
    isolated_count: int,
    distance_km: float,
    area_notes: list[str],
) -> SafetyTipsResult | None:
    """Generate personalised tips with Gemini. Returns None on any failure."""
    if not GEMINI_API_KEY:
        return None
    try:
        import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            generation_config={"temperature": GEMINI_TEMPERATURE, "max_output_tokens": 600},
        )

        notes_text = "; ".join(area_notes) if area_notes else "No specific notes."
        prompt = f"""You are a women safety advisor in Pune, India.

Journey details:
- From: {source}
- To: {destination}
- Safety score: {score}/100
- Time: {'Night (8PM-5AM)' if is_night else 'Day'}
- Distance: {distance_km:.1f} km
- Isolated road segments: {isolated_count}
- Area notes: {notes_text}

Give exactly 4 personalised safety tips for this specific journey.
Each tip should be practical, specific to this route, and written in plain English.
Format: one tip per line, starting with a relevant emoji.
No numbering, no headers, no extra text."""

        response = model.generate_content(prompt)
        raw_tips = [line.strip() for line in response.text.strip().splitlines() if line.strip()]

        ctx = f"AI-personalised | Score {score}/100 | {'Night' if is_night else 'Day'} | {distance_km:.1f} km"

        return SafetyTipsResult(
            tips=raw_tips[:5],
            general_guidelines=_GENERAL_SAFETY,
            used_ai=True,
            context_summary=ctx,
        )
    except Exception as exc:
        logger.warning("Gemini safety tips failed: %s — falling back to rules", exc)
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def generate_safety_tips(
    source: str,
    destination: str,
    route_info: dict[str, Any],
    time_of_day: str = "now",
) -> SafetyTipsResult:
    """Generate personalised safety tips for a journey.

    Args:
        source: Start address.
        destination: End address.
        route_info: Dict from RouteAnalysis (score, segments, etc.).
        time_of_day: "now" or ISO datetime string.

    Returns:
        SafetyTipsResult — never raises.
    """
    try:
        if time_of_day == "now":
            dt = datetime.now()
        else:
            dt = datetime.fromisoformat(time_of_day)
    except ValueError:
        dt = datetime.now()

    is_night = dt.hour >= 20 or dt.hour < 5
    score: int = route_info.get("overall_score", 70)
    distance_km: float = route_info.get("distance_km", 2.0)

    segments: list[dict[str, Any]] = route_info.get("segments", [])
    isolated_count = sum(s.get("isolated_segments", 0) for s in segments)
    area_notes = [s.get("notes", "") for s in segments if s.get("notes")]

    logger.info("Generating safety tips: score=%d night=%s isolated=%d", score, is_night, isolated_count)

    if GEMINI_API_KEY:
        result = _gemini_tips(source, destination, score, is_night, isolated_count, distance_km, area_notes)
        if result:
            return result

    return _rule_based_tips(score, is_night, isolated_count, distance_km)
