"""Folium map rendering utilities for SafeRoute."""

from __future__ import annotations

import logging
from typing import Any

import folium
from folium.plugins import AntPath

from config import MAP_DEFAULT_ZOOM, MAP_TILE, PRIMARY_COLOR, DANGER_COLOR, SUCCESS_COLOR

logger = logging.getLogger("saferoute.maps")

# Safety-score → colour mapping
_SCORE_COLOURS = [
    (80, "#1E8449"),   # green  — safe
    (60, "#F39C12"),   # amber  — moderate
    (0,  "#C0392B"),   # red    — danger
]


def _score_to_colour(score: int) -> str:
    for threshold, colour in _SCORE_COLOURS:
        if score >= threshold:
            return colour
    return "#C0392B"


def _score_to_label(score: int) -> str:
    if score >= 80:
        return "Safe"
    if score >= 60:
        return "Moderate"
    return "Avoid"


# ── Base map ──────────────────────────────────────────────────────────────────

def create_base_map(lat: float, lon: float, zoom: int = MAP_DEFAULT_ZOOM) -> folium.Map:
    """Create a centred Folium map with the SafeRoute tile style."""
    return folium.Map(
        location=[lat, lon],
        zoom_start=zoom,
        tiles=MAP_TILE,
        attr="© OpenStreetMap contributors | SafeRoute",
    )


# ── Markers ───────────────────────────────────────────────────────────────────

def add_start_marker(fmap: folium.Map, lat: float, lon: float, label: str) -> None:
    """Add a green start-point marker."""
    folium.Marker(
        location=[lat, lon],
        popup=folium.Popup(f"<b>Start:</b> {label}", max_width=200),
        tooltip=f"Start: {label}",
        icon=folium.Icon(color="green", icon="home", prefix="fa"),
    ).add_to(fmap)


def add_end_marker(fmap: folium.Map, lat: float, lon: float, label: str) -> None:
    """Add a red destination marker."""
    folium.Marker(
        location=[lat, lon],
        popup=folium.Popup(f"<b>Destination:</b> {label}", max_width=200),
        tooltip=f"Destination: {label}",
        icon=folium.Icon(color="red", icon="flag", prefix="fa"),
    ).add_to(fmap)


def add_waypoint_markers(fmap: folium.Map, segments: list[dict[str, Any]]) -> None:
    """Add circle markers for each intermediate route segment with safety info."""
    for seg in segments[1:-1]:   # skip start and end
        score = seg.get("safety_score", 70)
        colour = _score_to_colour(score)
        popup_html = (
            f"<b>{seg.get('name', 'Waypoint')}</b><br>"
            f"Safety: <span style='color:{colour}'>{_score_to_label(score)} ({score})</span><br>"
            f"Lighting: {seg.get('lighting', '—')}<br>"
            f"Crowd: {seg.get('crowd_density', '—')}<br>"
            f"<i>{seg.get('notes', '')}</i>"
        )
        folium.CircleMarker(
            location=[seg["lat"], seg["lon"]],
            radius=8,
            color=colour,
            fill=True,
            fill_color=colour,
            fill_opacity=0.7,
            popup=folium.Popup(popup_html, max_width=240),
            tooltip=f"{seg.get('name', 'Waypoint')} — {_score_to_label(score)}",
        ).add_to(fmap)


def add_police_station_marker(fmap: folium.Map, station: dict[str, Any]) -> None:
    """Add a blue police-station marker."""
    folium.Marker(
        location=[station["lat"], station["lon"]],
        popup=folium.Popup(
            f"<b>🚔 {station['name']}</b><br>{station['address']}<br>📞 {station['phone']}",
            max_width=240,
        ),
        tooltip=f"Police: {station['name']}",
        icon=folium.Icon(color="blue", icon="shield", prefix="fa"),
    ).add_to(fmap)


# ── Route lines ───────────────────────────────────────────────────────────────

def draw_primary_route(
    fmap: folium.Map,
    segments: list[dict[str, Any]],
    overall_score: int,
) -> None:
    """Draw the primary recommended route with an animated safety-coloured line."""
    coords = [[s["lat"], s["lon"]] for s in segments]
    colour = _score_to_colour(overall_score)

    # Animated ant-path for primary route
    AntPath(
        locations=coords,
        color=colour,
        weight=5,
        opacity=0.85,
        delay=800,
        tooltip=f"Recommended route — {_score_to_label(overall_score)} (score {overall_score})",
    ).add_to(fmap)


def draw_alternative_route(
    fmap: folium.Map,
    segments: list[dict[str, Any]],
    overall_score: int,
) -> None:
    """Draw an alternative route as a dashed grey line."""
    coords = [[s["lat"], s["lon"]] for s in segments]
    folium.PolyLine(
        locations=coords,
        color="#888888",
        weight=3,
        opacity=0.55,
        dash_array="8 6",
        tooltip=f"Alternative route — {_score_to_label(overall_score)} (score {overall_score})",
    ).add_to(fmap)


# ── Safety zone overlays ──────────────────────────────────────────────────────

def add_zone_circles(fmap: folium.Map, zones: list[dict[str, Any]]) -> None:
    """Draw translucent safety-zone circles on the map."""
    for zone in zones:
        score = zone.get("safety_score", 70)
        colour = _score_to_colour(score)
        folium.Circle(
            location=[zone["lat"], zone["lon"]],
            radius=zone.get("radius_km", 1.0) * 1000,   # metres
            color=colour,
            fill=True,
            fill_color=colour,
            fill_opacity=0.12,
            weight=1.5,
            popup=folium.Popup(
                f"<b>{zone['name']}</b><br>"
                f"Score: <span style='color:{colour}'>{score}</span><br>"
                f"Lighting: {zone.get('lighting', '—')}<br>"
                f"Roads: {zone.get('road_type', '—')}<br>"
                f"Crowd: {zone.get('crowd_density', '—')}",
                max_width=220,
            ),
            tooltip=zone["name"],
        ).add_to(fmap)


# ── Full route map composer ───────────────────────────────────────────────────

def build_route_map(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    start_label: str,
    end_label: str,
    primary_segments: list[dict[str, Any]],
    primary_score: int,
    alt_segments: list[dict[str, Any]] | None = None,
    alt_score: int = 0,
    zones: list[dict[str, Any]] | None = None,
    police_station: dict[str, Any] | None = None,
) -> folium.Map:
    """Compose the full interactive route map for display in Streamlit."""
    centre_lat = (start_lat + end_lat) / 2
    centre_lon = (start_lon + end_lon) / 2

    fmap = create_base_map(centre_lat, centre_lon, zoom=12)

    # Zone circles (background layer)
    if zones:
        add_zone_circles(fmap, zones)

    # Alternative route (drawn first so primary sits on top)
    if alt_segments:
        draw_alternative_route(fmap, alt_segments, alt_score)

    # Primary route
    draw_primary_route(fmap, primary_segments, primary_score)

    # Waypoint safety dots
    add_waypoint_markers(fmap, primary_segments)

    # Start / end markers
    add_start_marker(fmap, start_lat, start_lon, start_label)
    add_end_marker(fmap, end_lat, end_lon, end_label)

    # Police station
    if police_station:
        add_police_station_marker(fmap, police_station)

    # Legend
    _add_legend(fmap)

    return fmap


def _add_legend(fmap: folium.Map) -> None:
    """Inject a small HTML legend into the map."""
    legend_html = """
    <div style="
        position: fixed; bottom: 30px; left: 30px; z-index: 1000;
        background: white; padding: 10px 14px; border-radius: 8px;
        border: 1px solid #ccc; font-size: 12px; font-family: sans-serif;
        box-shadow: 2px 2px 6px rgba(0,0,0,0.2);
    ">
        <b style="font-size:13px;">Safety Score</b><br>
        <span style="color:#1E8449;">&#9632;</span> Safe (80–100)<br>
        <span style="color:#F39C12;">&#9632;</span> Moderate (60–79)<br>
        <span style="color:#C0392B;">&#9632;</span> Avoid (&lt;60)<br>
        <span style="color:#888;">&#9135;&#9135;</span> Alternative route
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(legend_html))
