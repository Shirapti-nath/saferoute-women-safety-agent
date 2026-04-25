"""Route safety scoring engine — pure Python, no LLM involved."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from config import SafetyLevel, ScoreWeights, SAFETY_LABELS
from utils.geocoding import geocode_with_fallback, Location
from utils.mock_data import (
    get_mock_route_segments,
    get_simulated_alternative_route,
    get_nearest_police_station,
    get_all_zones,
)

logger = logging.getLogger("saferoute.route_analyser")


@dataclass
class RouteScore:
    """Full scoring result for one route option."""
    route_label: str
    overall_score: int
    safety_label: str
    colour: str
    distance_km: float
    duration_minutes: int
    segments: list[dict[str, Any]]
    penalties: list[str]
    bonuses: list[str]
    explanation: str
    is_recommended: bool = False


@dataclass
class RouteAnalysis:
    """Complete analysis returned to the agent / UI."""
    source: str
    destination: str
    source_location: Location
    destination_location: Location
    travel_time: str          # "now" or ISO string
    is_night: bool
    primary: RouteScore
    alternative: RouteScore
    recommended: RouteScore
    police_station: dict[str, Any] | None
    all_zones: list[dict[str, Any]]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_night_time(dt: datetime) -> bool:
    return dt.hour >= 20 or dt.hour < 5


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def _score_colour(score: int) -> str:
    if score >= SafetyLevel.SAFE_MIN:
        return "#1E8449"
    if score >= SafetyLevel.MODERATE_MIN:
        return "#F39C12"
    return "#C0392B"


def _score_label(score: int) -> str:
    if score >= SafetyLevel.SAFE_MIN:
        return SAFETY_LABELS["safe"]
    if score >= SafetyLevel.MODERATE_MIN:
        return SAFETY_LABELS["moderate"]
    return SAFETY_LABELS["danger"]


def _walk_duration(distance_km: float) -> int:
    """Estimate walking minutes at 5 km/h."""
    return max(1, int((distance_km / 5.0) * 60))


# ── Core scoring ──────────────────────────────────────────────────────────────

def _score_route(
    segments: list[dict[str, Any]],
    distance_km: float,
    is_night: bool,
    label: str,
) -> RouteScore:
    """Apply scoring rules to a list of route segments and return a RouteScore."""
    score = 100
    penalties: list[str] = []
    bonuses: list[str] = []

    # Night-time penalty (applied once for the whole route)
    if is_night:
        score += ScoreWeights.NIGHT_PENALTY
        penalties.append(f"Night travel ({ScoreWeights.NIGHT_PENALTY} pts)")

    # Distance penalty
    if distance_km > 5:
        score += ScoreWeights.LONG_WALK_PENALTY
        penalties.append(f"Long route >{distance_km:.1f} km ({ScoreWeights.LONG_WALK_PENALTY} pts)")
    elif distance_km <= 2:
        score += ScoreWeights.SHORT_DISTANCE_BONUS
        bonuses.append(f"Short distance ({ScoreWeights.SHORT_DISTANCE_BONUS} pts)")

    # Per-segment evaluation
    for seg in segments:
        lighting = seg.get("lighting", "dim")
        road_type = seg.get("road_type", "mixed")
        crowd = seg.get("crowd_density", "medium")
        isolated = seg.get("isolated_segments", 0)
        area_score = seg.get("safety_score", 70)
        name = seg.get("name", "area")

        # Lighting
        if lighting == "well-lit":
            score += ScoreWeights.WELL_LIT_BONUS
            bonuses.append(f"{name}: well-lit (+{ScoreWeights.WELL_LIT_BONUS})")
        elif lighting == "dark":
            score += ScoreWeights.LOW_LIGHT_PENALTY
            penalties.append(f"{name}: dark area ({ScoreWeights.LOW_LIGHT_PENALTY})")
        elif lighting == "dim":
            score += ScoreWeights.LOW_LIGHT_PENALTY // 2
            penalties.append(f"{name}: dim lighting ({ScoreWeights.LOW_LIGHT_PENALTY // 2})")

        # Road type
        if road_type == "main_road":
            score += ScoreWeights.MAIN_ROAD_BONUS
            bonuses.append(f"{name}: main road (+{ScoreWeights.MAIN_ROAD_BONUS})")
        elif road_type == "isolated":
            score += ScoreWeights.ISOLATED_ROAD_PENALTY
            penalties.append(f"{name}: isolated road ({ScoreWeights.ISOLATED_ROAD_PENALTY})")

        # Crowd
        if crowd == "high":
            score += ScoreWeights.CROWDED_AREA_BONUS
            bonuses.append(f"{name}: crowded area (+{ScoreWeights.CROWDED_AREA_BONUS})")

        # Crime proxy from area safety score
        if area_score < 60:
            score += ScoreWeights.HIGH_CRIME_PENALTY
            penalties.append(f"{name}: high-risk zone ({ScoreWeights.HIGH_CRIME_PENALTY})")

        # Isolated segments
        for _ in range(isolated):
            score += ScoreWeights.ISOLATED_ROAD_PENALTY
            penalties.append(f"{name}: isolated segment ({ScoreWeights.ISOLATED_ROAD_PENALTY})")

    # Clamp 0-100
    score = max(0, min(100, score))

    explanation = _build_explanation(label, score, distance_km, is_night, penalties, bonuses)

    return RouteScore(
        route_label=label,
        overall_score=score,
        safety_label=_score_label(score),
        colour=_score_colour(score),
        distance_km=round(distance_km, 2),
        duration_minutes=_walk_duration(distance_km),
        segments=segments,
        penalties=penalties,
        bonuses=bonuses,
        explanation=explanation,
    )


def _build_explanation(
    label: str,
    score: int,
    distance_km: float,
    is_night: bool,
    penalties: list[str],
    bonuses: list[str],
) -> str:
    parts = [f"**{label}** — Safety score: {score}/100 ({_score_label(score)})"]
    parts.append(f"Distance: ~{distance_km:.1f} km | Est. time: {_walk_duration(distance_km)} min")
    if is_night:
        parts.append("⚠️ Night-time travel detected — extra caution advised.")
    if bonuses:
        parts.append("✅ Positive factors: " + "; ".join(bonuses[:3]))
    if penalties:
        parts.append("⚠️ Risk factors: " + "; ".join(penalties[:3]))
    return "\n".join(parts)


# ── Public API ────────────────────────────────────────────────────────────────

def analyse_route(
    source: str,
    destination: str,
    travel_time: str = "now",
) -> RouteAnalysis:
    """Main entry point — geocode, score two route options, return full analysis.

    Args:
        source: Free-text start address.
        destination: Free-text end address.
        travel_time: "now" or an ISO-format datetime string.

    Returns:
        RouteAnalysis with primary route, alternative, and recommendation.
    """
    logger.info("Analysing route: %s → %s (time=%s)", source, destination, travel_time)

    # Resolve time
    if travel_time == "now":
        dt = datetime.now()
    else:
        try:
            dt = datetime.fromisoformat(travel_time)
        except ValueError:
            dt = datetime.now()

    is_night = _is_night_time(dt)

    # Geocode
    src_loc = geocode_with_fallback(source)
    dst_loc = geocode_with_fallback(destination)

    distance_km = _haversine_km(src_loc.lat, src_loc.lon, dst_loc.lat, dst_loc.lon)

    # Build route segments
    primary_segs = get_mock_route_segments(src_loc.lat, src_loc.lon, dst_loc.lat, dst_loc.lon, num_segments=5)
    alt_segs = get_simulated_alternative_route(src_loc.lat, src_loc.lon, dst_loc.lat, dst_loc.lon)

    # Score both routes
    primary = _score_route(primary_segs, distance_km, is_night, "Direct Route")
    alternative = _score_route(alt_segs, distance_km * 1.15, is_night, "Alternative Route")

    # Recommend the safer one
    if primary.overall_score >= alternative.overall_score:
        primary.is_recommended = True
        recommended = primary
    else:
        alternative.is_recommended = True
        recommended = alternative

    police = get_nearest_police_station(src_loc.lat, src_loc.lon)
    zones = get_all_zones()

    return RouteAnalysis(
        source=source,
        destination=destination,
        source_location=src_loc,
        destination_location=dst_loc,
        travel_time=travel_time,
        is_night=is_night,
        primary=primary,
        alternative=alternative,
        recommended=recommended,
        police_station=police,
        all_zones=zones,
    )
