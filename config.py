"""Central configuration and constants for SafeRoute."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT_DIR: Path = Path(__file__).parent
DATA_DIR: Path = ROOT_DIR / "data"
ASSETS_DIR: Path = ROOT_DIR / "assets"

# Load .env from project root (no-op if already set)
load_dotenv(ROOT_DIR / ".env")

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("saferoute")

# ── API keys (all optional — app degrades gracefully when absent) ─────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER", "")

# ── Gemini model ─────────────────────────────────────────────────────────────
GEMINI_MODEL: str = "gemini-2.5-flash-preview-04-17"
GEMINI_TEMPERATURE: float = 0.3
GEMINI_MAX_TOKENS: int = 1024

# ── Route safety scoring weights ────────────────────────────────────────────
class ScoreWeights:
    NIGHT_PENALTY: int = -20          # 20:00 – 05:00
    ISOLATED_ROAD_PENALTY: int = -15  # per isolated segment
    LOW_LIGHT_PENALTY: int = -10
    HIGH_CRIME_PENALTY: int = -25
    LONG_WALK_PENALTY: int = -5       # walking > 5 km

    MAIN_ROAD_BONUS: int = 10
    CROWDED_AREA_BONUS: int = 10
    WELL_LIT_BONUS: int = 5
    SHORT_DISTANCE_BONUS: int = 5


# ── Score thresholds ─────────────────────────────────────────────────────────
class SafetyLevel:
    SAFE_MIN: int = 80        # 80-100  → green
    MODERATE_MIN: int = 60    # 60-79   → yellow
    # below 60               → red


SAFETY_LABELS: dict[str, str] = {
    "safe":     "🟢 Safe Route",
    "moderate": "🟡 Moderate — take precautions",
    "danger":   "🔴 Avoid — find alternative",
}

# ── Journey tracker ──────────────────────────────────────────────────────────
JOURNEY_BUFFER_MINUTES: int = 15   # grace period before alert fires

# ── Distress keywords (rule-based fallback when Gemini unavailable) ──────────
DISTRESS_KEYWORDS: list[str] = [
    "following me",
    "being followed",
    "feel unsafe",
    "i am scared",
    "i'm scared",
    "help me",
    "someone is watching",
    "watching me",
    "i need help",
    "danger",
    "threatened",
    "harassed",
    "attack",
]

# ── Emergency contacts (always shown in UI) ──────────────────────────────────
EMERGENCY_NUMBERS: dict[str, str] = {
    "Police":               "100",
    "Women Helpline":       "1091",
    "Ambulance":            "108",
    "National Emergency":   "112",
}

# ── Geocoding ────────────────────────────────────────────────────────────────
NOMINATIM_USER_AGENT: str = "saferoute-women-safety-agent/1.0"
GEOCODE_TIMEOUT_SECONDS: int = 10

# ── Map defaults ─────────────────────────────────────────────────────────────
MAP_DEFAULT_ZOOM: int = 13
MAP_TILE: str = "CartoDB positron"

# ── UI ───────────────────────────────────────────────────────────────────────
APP_TITLE: str = "SafeRoute — Women Safety Navigation"
APP_TAGLINE: str = "AI-powered safety companion that finds the safest route and protects women in real time"
APP_ICON: str = "🛡️"
PRIMARY_COLOR: str = "#6C3483"   # deep purple
SECONDARY_COLOR: str = "#F8F9FA"
DANGER_COLOR: str = "#C0392B"
SUCCESS_COLOR: str = "#1E8449"
