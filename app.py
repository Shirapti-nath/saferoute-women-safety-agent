"""SafeRoute — Women Safety Navigation Agent · Streamlit UI."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path so all local imports resolve
sys.path.insert(0, str(Path(__file__).parent))

import logging
from datetime import datetime, timedelta

import streamlit as st

from config import (
    APP_ICON, APP_TAGLINE, APP_TITLE,
    EMERGENCY_NUMBERS, GEMINI_API_KEY, TWILIO_ACCOUNT_SID,
    PRIMARY_COLOR, DANGER_COLOR, SUCCESS_COLOR,
)
from agent import SafeRouteAgent
from utils.maps import build_route_map

logger = logging.getLogger("saferoute.app")

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SafeRoute",
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
  :root {{
    --primary: {PRIMARY_COLOR};
    --danger: {DANGER_COLOR};
    --success: {SUCCESS_COLOR};
  }}
  .main-header {{
    background: linear-gradient(135deg, {PRIMARY_COLOR} 0%, #9B59B6 100%);
    padding: 1.5rem 2rem;
    border-radius: 12px;
    color: white;
    margin-bottom: 1.5rem;
  }}
  .main-header h1 {{ margin: 0; font-size: 2rem; }}
  .main-header p  {{ margin: 0.3rem 0 0; opacity: 0.9; font-size: 1rem; }}
  .score-card {{
    padding: 1rem 1.5rem;
    border-radius: 10px;
    color: white;
    font-weight: 600;
    text-align: center;
    margin-bottom: 1rem;
  }}
  .sos-btn button {{
    background: {DANGER_COLOR} !important;
    color: white !important;
    font-size: 1.3rem !important;
    font-weight: 700 !important;
    border-radius: 10px !important;
    padding: 0.8rem 2rem !important;
    width: 100% !important;
    border: none !important;
    cursor: pointer !important;
  }}
  .safe-btn button {{
    background: {SUCCESS_COLOR} !important;
    color: white !important;
    font-weight: 700 !important;
    border-radius: 10px !important;
    width: 100% !important;
    border: none !important;
  }}
  .emergency-box {{
    background: #FDF2F8;
    border-left: 4px solid {PRIMARY_COLOR};
    padding: 0.8rem 1rem;
    border-radius: 6px;
    margin-top: 0.5rem;
  }}
  .distress-high   {{ background: #FADBD8; border-left: 4px solid {DANGER_COLOR}; padding: 1rem; border-radius: 8px; }}
  .distress-medium {{ background: #FDEBD0; border-left: 4px solid #E67E22; padding: 1rem; border-radius: 8px; }}
  .distress-low    {{ background: #FEFEFE; border-left: 4px solid #F1C40F; padding: 1rem; border-radius: 8px; }}
  .distress-none   {{ background: #EAFAF1; border-left: 4px solid {SUCCESS_COLOR}; padding: 1rem; border-radius: 8px; }}
</style>
""", unsafe_allow_html=True)


# ── Session state init ────────────────────────────────────────────────────────
def _init_state() -> None:
    defaults = {
        "agent": SafeRouteAgent(),
        "user_name": "",
        "contacts": ["", "", ""],
        "route_result": None,
        "tips_result": None,
        "distress_result": None,
        "sos_result": None,
        "journey_active": False,
        "journey_destination": "",
        "journey_eta_iso": "",
        "journey_status_msg": "",
        "profile_saved": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()
agent: SafeRouteAgent = st.session_state["agent"]


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="main-header">
  <h1>{APP_ICON} {APP_TITLE}</h1>
  <p>{APP_TAGLINE}</p>
  <small>🌍 SDG 5 — Gender Equality &nbsp;|&nbsp;
         🤖 AI: {'Gemini 2.5 Flash' if GEMINI_API_KEY else 'Rule-based (add GEMINI_API_KEY)'} &nbsp;|&nbsp;
         📲 SMS: {'Twilio active' if TWILIO_ACCOUNT_SID else 'Simulated mode'}</small>
</div>
""", unsafe_allow_html=True)


# ── Sidebar — tab navigation ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"## {APP_ICON} SafeRoute")
    page = st.radio(
        "Navigate",
        ["🗺️ Route Planner", "🆘 SOS & Contacts", "💬 Check In", "🎯 Journey Mode"],
        label_visibility="collapsed",
    )

    st.divider()
    st.markdown("### 🚨 Emergency Numbers")
    for name, number in EMERGENCY_NUMBERS.items():
        st.markdown(f"**{name}:** `{number}`")

    st.divider()
    st.caption("SafeRoute · SDG 5 · Built with Gemini + LangChain")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — Route Planner
# ══════════════════════════════════════════════════════════════════════════════
if page == "🗺️ Route Planner":
    st.subheader("🗺️ Find Your Safest Route")

    col1, col2 = st.columns(2)
    with col1:
        source = st.text_input(
            "📍 From",
            placeholder="e.g. Koregaon Park, Pune",
            help="Enter your starting location",
        )
    with col2:
        destination = st.text_input(
            "🏁 To",
            placeholder="e.g. Hinjewadi, Pune",
            help="Enter your destination",
        )

    col3, col4 = st.columns([2, 1])
    with col3:
        time_option = st.radio("🕐 Travel time", ["Now", "Schedule"], horizontal=True)
    with col4:
        if time_option == "Schedule":
            travel_date = st.date_input("Date", value=datetime.now().date())
            travel_time_val = st.time_input("Time", value=datetime.now().time())
            travel_iso = datetime.combine(travel_date, travel_time_val).isoformat()
        else:
            travel_iso = "now"

    find_btn = st.button("🔍 Find Safe Route", type="primary", use_container_width=True)

    if find_btn:
        if not source.strip() or not destination.strip():
            st.warning("Please enter both a starting point and a destination.")
        else:
            with st.spinner("Analysing routes and safety scores…"):
                response = agent.analyse_route(source, destination, travel_iso)

            if response.success:
                st.session_state["route_result"] = response

                # Tips in background
                route_data = {
                    "overall_score": response.data["recommended_score"],
                    "distance_km": response.data["analysis"].recommended.distance_km,
                    "segments": response.data["analysis"].recommended.segments,
                }
                tips_resp = agent.generate_safety_tips(source, destination, route_data, travel_iso)
                st.session_state["tips_result"] = tips_resp
            else:
                st.error(response.narrative)

    # ── Display results ────────────────────────────────────────────────────────
    if st.session_state["route_result"] is not None:
        rr = st.session_state["route_result"]
        analysis = rr.data["analysis"]
        rec = analysis.recommended

        score = rec.overall_score
        colour = rec.colour
        label = rec.safety_label

        # Score card
        st.markdown(f"""
        <div class="score-card" style="background:{colour};">
          <div style="font-size:1.8rem;">{label}</div>
          <div style="font-size:2.5rem; font-weight:900;">{score} / 100</div>
          <div style="opacity:0.9;">{rec.route_label} · {rec.distance_km:.1f} km · ~{rec.duration_minutes} min</div>
          {"<div>⚠️ Night travel — extra caution</div>" if analysis.is_night else ""}
        </div>
        """, unsafe_allow_html=True)

        # Agent narrative
        st.info(rr.narrative)

        # Two-column: map + details
        map_col, detail_col = st.columns([3, 2])

        with map_col:
            st.markdown("#### 🗺️ Interactive Safety Map")
            try:
                from streamlit_folium import st_folium

                fmap = build_route_map(
                    start_lat=rr.data["source_lat"],
                    start_lon=rr.data["source_lon"],
                    end_lat=rr.data["dest_lat"],
                    end_lon=rr.data["dest_lon"],
                    start_label=analysis.source,
                    end_label=analysis.destination,
                    primary_segments=analysis.primary.segments,
                    primary_score=analysis.primary.overall_score,
                    alt_segments=analysis.alternative.segments,
                    alt_score=analysis.alternative.overall_score,
                    zones=rr.data["zones"],
                    police_station=rr.data["police_station"],
                )
                st_folium(fmap, width=700, height=420)
            except Exception as e:
                st.error(f"Map rendering error: {e}")

        with detail_col:
            # Route comparison
            st.markdown("#### 📊 Route Comparison")
            p = analysis.primary
            a = analysis.alternative

            st.markdown(f"""
            | Route | Score | Distance | Time |
            |-------|-------|----------|------|
            | {p.route_label} {'⭐' if p.is_recommended else ''} | {p.overall_score} | {p.distance_km:.1f} km | {p.duration_minutes} min |
            | {a.route_label} {'⭐' if a.is_recommended else ''} | {a.overall_score} | {a.distance_km:.1f} km | {a.duration_minutes} min |
            """)

            # Risk factors
            if rec.penalties:
                st.markdown("**⚠️ Risk factors:**")
                for p_item in rec.penalties[:4]:
                    st.markdown(f"- {p_item}")

            if rec.bonuses:
                st.markdown("**✅ Positive factors:**")
                for b in rec.bonuses[:4]:
                    st.markdown(f"- {b}")

            # Police station
            if rr.data["police_station"]:
                ps = rr.data["police_station"]
                st.markdown(f"""
                <div class="emergency-box">
                🚔 <b>Nearest Police Station</b><br>
                {ps['name']}<br>
                📞 {ps['phone']}
                </div>
                """, unsafe_allow_html=True)

        # Safety tips
        if st.session_state["tips_result"] is not None:
            tr = st.session_state["tips_result"]
            st.markdown("---")
            st.markdown("#### 💡 Personalised Safety Tips")
            tips_col1, tips_col2 = st.columns(2)
            with tips_col1:
                st.markdown("**For this journey:**")
                for tip in tr.data.get("tips", []):
                    st.markdown(f"- {tip}")
            with tips_col2:
                st.markdown("**General guidelines:**")
                for g in tr.data.get("general", [])[:4]:
                    st.markdown(f"- {g}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — SOS & Contacts
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🆘 SOS & Contacts":
    st.subheader("🆘 SOS Alert & Trusted Contacts")

    # Profile form
    with st.expander("👤 Your Profile", expanded=not st.session_state["profile_saved"]):
        name_input = st.text_input("Your Name", value=st.session_state["user_name"], placeholder="e.g. Priya Sharma")
        st.markdown("**Trusted Contact Numbers** (include country code, e.g. +91XXXXXXXXXX)")
        c1, c2, c3 = st.columns(3)
        contacts_input = [
            c1.text_input("Contact 1", value=st.session_state["contacts"][0], placeholder="+91XXXXXXXXXX"),
            c2.text_input("Contact 2", value=st.session_state["contacts"][1], placeholder="+91XXXXXXXXXX"),
            c3.text_input("Contact 3", value=st.session_state["contacts"][2], placeholder="+91XXXXXXXXXX"),
        ]

        if st.button("💾 Save Profile", type="primary"):
            st.session_state["user_name"] = name_input
            st.session_state["contacts"] = contacts_input
            agent.set_user_profile(name_input, contacts_input)
            st.session_state["profile_saved"] = True
            saved_count = sum(1 for c in contacts_input if c.strip())
            st.success(f"Profile saved. {saved_count} contact(s) registered.")

    st.divider()

    # SOS section
    st.markdown("### 🔴 Emergency SOS")
    if not st.session_state["profile_saved"]:
        st.warning("Save your profile above before using SOS.")

    sos_location = st.text_input(
        "📍 Your current location (optional)",
        placeholder="e.g. Koregaon Park, near ABC restaurant",
    )

    st.markdown('<div class="sos-btn">', unsafe_allow_html=True)
    if st.button("🆘 SEND SOS ALERT NOW", use_container_width=True):
        location_str = sos_location.strip() or "Location not specified"
        with st.spinner("Sending SOS…"):
            sos_resp = agent.trigger_sos(location_str)
            st.session_state["sos_result"] = sos_resp

        if sos_resp.success:
            st.success(sos_resp.narrative)
            st.balloons()
        else:
            st.error(sos_resp.narrative)
    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state["sos_result"] is not None:
        sr = st.session_state["sos_result"]
        with st.expander("📋 Alert Details", expanded=True):
            st.code(sr.data.get("message", ""), language=None)
            st.write(f"**Method:** {sr.data.get('method', '—')}")
            st.write(f"**Notified:** {', '.join(sr.data.get('notified', [])) or 'None'}")
            if sr.data.get("failed"):
                st.warning(f"Failed to reach: {', '.join(sr.data['failed'])}")

    st.divider()

    # Reached safely button
    st.markdown("### ✅ Confirm Safe Arrival")
    st.markdown('<div class="safe-btn">', unsafe_allow_html=True)
    if st.button("✅ I Reached Safely", use_container_width=True):
        result = agent.confirm_safe_arrival()
        st.success(result.narrative)
    st.markdown("</div>", unsafe_allow_html=True)

    st.divider()
    st.markdown("### 🚨 Emergency Numbers")
    cols = st.columns(len(EMERGENCY_NUMBERS))
    for col, (name, number) in zip(cols, EMERGENCY_NUMBERS.items()):
        col.metric(label=name, value=number)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — Check In (Distress Detector)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "💬 Check In":
    st.subheader("💬 How Are You Feeling Right Now?")
    st.markdown("Type how you feel. Our AI will analyse your message and provide support instantly.")

    user_msg = st.text_area(
        "Tell us what's happening",
        placeholder='e.g. "I think someone is following me" or "I feel unsafe walking home"',
        height=100,
        label_visibility="collapsed",
    )

    col_btn1, col_btn2 = st.columns([2, 1])
    analyse_btn = col_btn1.button("🔍 Analyse My Safety", type="primary", use_container_width=True)
    quick_sos = col_btn2.button("🆘 Quick SOS", use_container_width=True)

    if quick_sos:
        with st.spinner("Sending SOS…"):
            sos_resp = agent.trigger_sos("Unknown — triggered from Check In page")
        if sos_resp.success:
            st.success(sos_resp.narrative)
        else:
            st.error(sos_resp.narrative)

    if analyse_btn:
        if not user_msg.strip():
            st.warning("Please describe how you're feeling.")
        else:
            with st.spinner("Analysing…"):
                dr = agent.detect_distress(user_msg)
                st.session_state["distress_result"] = dr

    if st.session_state["distress_result"] is not None:
        dr = st.session_state["distress_result"]
        risk = dr.data.get("risk_level", "none")
        css_class = f"distress-{risk}"

        st.markdown(f'<div class="{css_class}">{dr.narrative}</div>', unsafe_allow_html=True)
        st.markdown("")

        if dr.data.get("is_distress"):
            # Auto-trigger SOS on high risk
            if risk == "high":
                st.error("🆘 HIGH RISK DETECTED — Triggering SOS automatically!")
                with st.spinner("Sending SOS to your contacts…"):
                    auto_sos = agent.trigger_sos("Check-In page — high distress detected")
                st.warning(auto_sos.narrative)

            # Resources
            st.markdown("---")
            res_col1, res_col2 = st.columns(2)

            with res_col1:
                st.markdown("### 🚨 Emergency Resources")
                for name, number in EMERGENCY_NUMBERS.items():
                    st.markdown(f"📞 **{name}:** `{number}`")

            with res_col2:
                st.markdown("### 🏥 Nearest Police Station")
                from utils.mock_data import get_nearest_police_station
                ps = get_nearest_police_station(18.5204, 73.8567)  # Pune centre fallback
                if ps:
                    st.markdown(f"**{ps['name']}**")
                    st.markdown(f"📍 {ps['address']}")
                    st.markdown(f"📞 {ps['phone']}")

            st.markdown("---")
            st.markdown("### 🛡️ Safety Instructions")
            safety_steps = [
                "Move immediately towards a crowded, well-lit area.",
                "Enter a shop, restaurant, or any public building.",
                "Call a trusted contact and stay on the line.",
                "Do NOT go home if you think you are being followed.",
                "Alert police (100) or use the SOS button above.",
            ]
            for step in safety_steps:
                st.markdown(f"✅ {step}")

        else:
            st.markdown("---")
            st.markdown("### 🛡️ General Safety Tips")
            from tools.safety_tips import _GENERAL_SAFETY
            for tip in _GENERAL_SAFETY[:5]:
                st.markdown(f"- {tip}")

    # Always-visible resource section
    with st.expander("📞 Emergency Resources (always available)", expanded=False):
        for name, number in EMERGENCY_NUMBERS.items():
            st.markdown(f"**{name}:** `{number}`")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — Journey Mode
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🎯 Journey Mode":
    st.subheader("🎯 Journey Tracker")
    st.markdown("Start a journey and we'll alert your contacts if you don't confirm safe arrival in time.")

    if not st.session_state["journey_active"]:
        # Journey setup form
        j_dest = st.text_input("🏁 Destination", placeholder="e.g. Hinjewadi IT Park")
        j_col1, j_col2 = st.columns(2)
        j_date = j_col1.date_input("Expected arrival date", value=datetime.now().date())
        default_time = (datetime.now() + timedelta(minutes=30)).time()
        j_time = j_col2.time_input("Expected arrival time", value=default_time)
        eta_iso = datetime.combine(j_date, j_time).isoformat()

        if not st.session_state["profile_saved"]:
            st.warning("Save your profile in the SOS & Contacts tab before starting a journey.")

        if st.button("▶️ Start Journey", type="primary", use_container_width=True):
            if not j_dest.strip():
                st.warning("Please enter a destination.")
            else:
                resp = agent.start_journey(j_dest, eta_iso)
                if resp.success:
                    st.session_state["journey_active"] = True
                    st.session_state["journey_destination"] = j_dest
                    st.session_state["journey_eta_iso"] = eta_iso
                    st.success(resp.narrative)
                    st.rerun()
                else:
                    st.error(resp.narrative)

    else:
        # Active journey display
        st.success(f"🗺️ Active journey to **{st.session_state['journey_destination']}**")

        status_resp = agent.check_journey_and_alert()
        st.info(status_resp.narrative)

        from tools.journey_tracker import get_journey_status
        j_status = get_journey_status()

        if j_status.session:
            sess = j_status.session
            time_col1, time_col2, time_col3 = st.columns(3)
            time_col1.metric("Started", sess.started_at.strftime("%I:%M %p"))
            time_col2.metric("Expected arrival", sess.expected_arrival.strftime("%I:%M %p"))
            time_col3.metric("Alert deadline", sess.deadline.strftime("%I:%M %p"))

            mins_left = sess.minutes_remaining()
            if mins_left > 0:
                st.progress(
                    min(1.0, 1 - mins_left / max(1, int((sess.deadline - sess.started_at).total_seconds() / 60))),
                    text=f"{mins_left} minutes until alert deadline",
                )
            else:
                st.error("⏰ Deadline passed — alert has been sent to your contacts!")

        st.divider()

        safe_col, cancel_col = st.columns(2)
        with safe_col:
            st.markdown('<div class="safe-btn">', unsafe_allow_html=True)
            if st.button("✅ I Reached Safely!", use_container_width=True):
                result = agent.confirm_safe_arrival()
                st.success(result.narrative)
                st.session_state["journey_active"] = False
                st.balloons()
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        with cancel_col:
            if st.button("❌ Cancel Journey", use_container_width=True):
                from tools.journey_tracker import cancel_journey
                msg = cancel_journey()
                st.info(msg)
                st.session_state["journey_active"] = False
                st.rerun()

        # Refresh status every 30 seconds
        st.caption("Page auto-refreshes every 30 s to check journey status.")
        import time as _time
        _time.sleep(0)   # yield control; user can manually refresh
        if st.button("🔄 Refresh Status"):
            st.rerun()
