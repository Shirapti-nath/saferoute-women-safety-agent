"""Address geocoding via OpenStreetMap Nominatim (free, no API key required)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

from config import GEOCODE_TIMEOUT_SECONDS, NOMINATIM_USER_AGENT

logger = logging.getLogger("saferoute.geocoding")

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_last_request_ts: float = 0.0   # Nominatim rate-limit: 1 req/sec


@dataclass
class Location:
    """Geocoded location result."""
    address: str
    lat: float
    lon: float
    display_name: str
    place_type: str = "place"

    def __str__(self) -> str:
        return f"{self.display_name} ({self.lat:.4f}, {self.lon:.4f})"


# ── Known Pune landmarks — instant lookup, no network call ───────────────────
_PUNE_CACHE: dict[str, tuple[float, float]] = {
    "koregaon park":        (18.5362, 73.8938),
    "koregaon park pune":   (18.5362, 73.8938),
    "hinjewadi":            (18.5912, 73.7389),
    "hinjewadi it park":    (18.5912, 73.7389),
    "hinjewadi pune":       (18.5912, 73.7389),
    "shivajinagar":         (18.5308, 73.8474),
    "shivajinagar pune":    (18.5308, 73.8474),
    "hadapsar":             (18.5018, 73.9252),
    "hadapsar pune":        (18.5018, 73.9252),
    "kothrud":              (18.5074, 73.8077),
    "kothrud pune":         (18.5074, 73.8077),
    "viman nagar":          (18.5679, 73.9143),
    "viman nagar pune":     (18.5679, 73.9143),
    "yerawada":             (18.5489, 73.8917),
    "yerawada pune":        (18.5489, 73.8917),
    "fc road":              (18.5195, 73.8412),
    "deccan":               (18.5195, 73.8412),
    "wakad":                (18.5984, 73.7611),
    "wakad pune":           (18.5984, 73.7611),
    "katraj":               (18.4530, 73.8644),
    "katraj pune":          (18.4530, 73.8644),
    "baner":                (18.5590, 73.7868),
    "aundh":                (18.5588, 73.8080),
    "pune station":         (18.5284, 73.8742),
    "pune railway station": (18.5284, 73.8742),
    "magarpatta":           (18.5145, 73.9285),
    "kalyani nagar":        (18.5450, 73.9016),
    "camp pune":            (18.5142, 73.8764),
}


def _rate_limit() -> None:
    """Ensure at least 1 second between Nominatim requests."""
    global _last_request_ts
    elapsed = time.monotonic() - _last_request_ts
    if elapsed < 1.1:
        time.sleep(1.1 - elapsed)
    _last_request_ts = time.monotonic()


def geocode(address: str, city_hint: str = "Pune, India") -> Optional[Location]:
    """Convert a free-text address to a Location.

    Checks the local Pune cache first; falls back to Nominatim API.
    Returns None on failure (never raises).
    """
    key = address.strip().lower()

    # Fast path: known landmark
    if key in _PUNE_CACHE:
        lat, lon = _PUNE_CACHE[key]
        logger.debug("Cache hit for '%s'", address)
        return Location(
            address=address,
            lat=lat,
            lon=lon,
            display_name=address,
            place_type="landmark",
        )

    # Also try with city suffix stripped
    key_no_city = key.replace(", pune", "").replace(" pune", "").strip()
    if key_no_city in _PUNE_CACHE:
        lat, lon = _PUNE_CACHE[key_no_city]
        return Location(address=address, lat=lat, lon=lon, display_name=address, place_type="landmark")

    # Nominatim API call
    query = f"{address}, {city_hint}" if city_hint.lower() not in key else address
    try:
        _rate_limit()
        resp = requests.get(
            _NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": 1, "addressdetails": 0},
            headers={"User-Agent": NOMINATIM_USER_AGENT},
            timeout=GEOCODE_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        results = resp.json()
        if results:
            r = results[0]
            return Location(
                address=address,
                lat=float(r["lat"]),
                lon=float(r["lon"]),
                display_name=r.get("display_name", address),
                place_type=r.get("type", "place"),
            )
        logger.warning("Nominatim returned no results for '%s'", query)
    except requests.exceptions.Timeout:
        logger.warning("Nominatim timeout for '%s'", query)
    except Exception as exc:
        logger.error("Geocoding error for '%s': %s", query, exc)

    return None


def geocode_with_fallback(address: str, city_hint: str = "Pune, India") -> Location:
    """Geocode an address; if it fails, return a central Pune fallback location."""
    result = geocode(address, city_hint)
    if result:
        return result
    logger.warning("Using Pune centre fallback for '%s'", address)
    return Location(
        address=address,
        lat=18.5204,
        lon=73.8567,
        display_name=f"{address} (approximate — Pune centre)",
        place_type="fallback",
    )


def coords_to_label(lat: float, lon: float) -> str:
    """Format a coordinate pair as a short human-readable string."""
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"{abs(lat):.4f}°{ns}, {abs(lon):.4f}°{ew}"
