"""Mock safety data loader and area-matching utilities."""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

logger = logging.getLogger("saferoute.mock_data")

_DATA_FILE = Path(__file__).parent.parent / "data" / "safety_zones.json"

# Cached after first load
_zones: list[dict[str, Any]] = []
_police_stations: list[dict[str, Any]] = []


def _load() -> None:
    """Load safety_zones.json once and cache results."""
    global _zones, _police_stations
    if _zones:
        return
    try:
        data = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
        _zones = data.get("zones", [])
        _police_stations = data.get("police_stations", [])
        logger.info("Loaded %d safety zones and %d police stations", len(_zones), len(_police_stations))
    except Exception as exc:
        logger.error("Failed to load safety_zones.json: %s", exc)
        _zones = []
        _police_stations = []


# ── Haversine distance ────────────────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in kilometres between two coordinates."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


# ── Public API ────────────────────────────────────────────────────────────────

def get_all_zones() -> list[dict[str, Any]]:
    """Return the full list of safety zone records."""
    _load()
    return list(_zones)


def get_zone_for_coords(lat: float, lon: float) -> dict[str, Any] | None:
    """Return the nearest zone whose radius contains the given coordinates.

    Falls back to the closest zone if none strictly contains the point.
    """
    _load()
    if not _zones:
        return None

    best: dict[str, Any] | None = None
    best_dist = float("inf")

    for zone in _zones:
        dist = _haversine_km(lat, lon, zone["lat"], zone["lon"])
        if dist <= zone["radius_km"] and dist < best_dist:
            best = zone
            best_dist = dist

    if best:
        return best

    # Fallback: closest zone regardless of radius
    for zone in _zones:
        dist = _haversine_km(lat, lon, zone["lat"], zone["lon"])
        if dist < best_dist:
            best = zone
            best_dist = dist

    return best


def get_zone_by_name(name: str) -> dict[str, Any] | None:
    """Fuzzy-match a zone by name (case-insensitive substring)."""
    _load()
    name_lower = name.lower()
    for zone in _zones:
        if name_lower in zone["name"].lower():
            return zone
    return None


def get_safety_score_for_coords(lat: float, lon: float) -> int:
    """Return the base safety score (0-100) for a coordinate pair."""
    zone = get_zone_for_coords(lat, lon)
    return zone["safety_score"] if zone else 70  # neutral default


def get_area_attributes(lat: float, lon: float) -> dict[str, Any]:
    """Return lighting, road type, crowd density, and isolated segment count.

    Returns safe defaults when no zone matches.
    """
    zone = get_zone_for_coords(lat, lon)
    if zone:
        return {
            "name":               zone["name"],
            "lighting":           zone["lighting"],
            "road_type":          zone["road_type"],
            "crowd_density":      zone["crowd_density"],
            "isolated_segments":  zone["isolated_segments"],
            "safety_score":       zone["safety_score"],
            "notes":              zone.get("notes", ""),
        }
    return {
        "name":               "Unknown area",
        "lighting":           "dim",
        "road_type":          "mixed",
        "crowd_density":      "medium",
        "isolated_segments":  1,
        "safety_score":       70,
        "notes":              "",
    }


def get_nearest_police_station(lat: float, lon: float) -> dict[str, Any] | None:
    """Return the police station record closest to the given coordinates."""
    _load()
    if not _police_stations:
        return None

    return min(
        _police_stations,
        key=lambda ps: _haversine_km(lat, lon, ps["lat"], ps["lon"]),
    )


def get_mock_route_segments(
    start_lat: float, start_lon: float, end_lat: float, end_lon: float, num_segments: int = 4
) -> list[dict[str, Any]]:
    """Generate interpolated waypoints and attach zone attributes to each.

    Used to simulate multi-segment route analysis without a real routing API.
    """
    segments: list[dict[str, Any]] = []
    for i in range(num_segments):
        t = i / max(num_segments - 1, 1)
        lat = start_lat + t * (end_lat - start_lat)
        lon = start_lon + t * (end_lon - start_lon)
        attrs = get_area_attributes(lat, lon)
        segments.append({
            "index": i,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "fraction": round(t, 3),
            **attrs,
        })
    return segments


def get_simulated_alternative_route(
    start_lat: float, start_lon: float, end_lat: float, end_lon: float
) -> list[dict[str, Any]]:
    """Return a slightly offset alternative route for comparison on the map."""
    offset = 0.008  # ~900 m lateral offset
    mid_lat = (start_lat + end_lat) / 2 + offset
    mid_lon = (start_lon + end_lon) / 2 + offset
    waypoints = [
        (start_lat, start_lon),
        (mid_lat, mid_lon),
        (end_lat, end_lon),
    ]
    segments: list[dict[str, Any]] = []
    for i, (lat, lon) in enumerate(waypoints):
        attrs = get_area_attributes(lat, lon)
        segments.append({"index": i, "lat": lat, "lon": lon, **attrs})
    return segments
