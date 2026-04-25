# 🛡️ SafeRoute — Women Safety Navigation Agent

> **AI-powered safety companion that finds the safest route and protects women in real time**

[![SDG 5](https://img.shields.io/badge/SDG-5%20Gender%20Equality-E5243B?style=for-the-badge&logo=united-nations)](https://sdgs.un.org/goals/goal5)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-FF4B4B?style=for-the-badge&logo=streamlit)](https://streamlit.io)
[![Gemini](https://img.shields.io/badge/Gemini-2.5%20Flash-4285F4?style=for-the-badge&logo=google)](https://aistudio.google.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

---

## 💔 The Problem

Every 16 minutes, a crime against women is reported in India. Women shouldn't have to choose between going places and staying safe — they need a smarter companion that works in real time.

---

## 💡 The Solution

SafeRoute is an AI agent that analyses routes for safety, monitors journeys, detects distress in real time, and instantly alerts trusted contacts — all in one app that works even without expensive API subscriptions.

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🗺️ **Safe Route Analyser** | Scores every route 0–100 using time of day, lighting, road type, and crime data |
| 🆘 **One-Click SOS** | Sends instant SMS alerts with location to up to 3 trusted contacts via Twilio |
| 💬 **Distress Detector** | Gemini AI analyses your message for distress signals in real time |
| 💡 **Safety Tips Generator** | Personalised route-specific tips powered by Gemini 2.5 Flash |
| 🎯 **Journey Tracker** | Auto-alerts contacts if you don't confirm safe arrival within your ETA + 15 min |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Streamlit UI (app.py)                 │
│         4 pages: Route · SOS · Check In · Journey       │
└───────────────────────┬─────────────────────────────────┘
                        │
              ┌─────────▼──────────┐
              │  SafeRouteAgent    │  ← agent.py
              │  (Orchestrator)    │
              └──┬──┬──┬──┬──┬───┘
                 │  │  │  │  │
    ┌────────────┘  │  │  │  └──────────────┐
    │               │  │  └──────────┐      │
    ▼               ▼  ▼             ▼      ▼
route_analyser  distress  safety   alert  journey
    .py         _detector  _tips   _system tracker
    │            .py       .py      .py     .py
    │                │        │       │
    ▼                ▼        ▼       ▼
 mock_data       Gemini    Gemini   Twilio
 geocoding      2.5 Flash  2.5 Flash  SMS
 (OSM Nominatim)
```

**Rule:** All computation (route scoring, timer logic, contact management) uses pure Python. Gemini is used **only** for natural language understanding and generation.

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **UI** | Streamlit 1.30+ |
| **AI / LLM** | Google Gemini 2.5 Flash (free tier) |
| **Maps** | Folium + OpenStreetMap (free, no key) |
| **Geocoding** | OSM Nominatim API (free, no key) |
| **SMS Alerts** | Twilio (free trial) |
| **Language** | Python 3.11+ |
| **Safety Data** | Mock dataset (realistic Pune areas) |

---

## 🚀 Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/your-username/saferoute-women-safety-agent.git
cd saferoute-women-safety-agent
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API keys

```bash
cp .env.example .env
# Edit .env and add your keys
```

### 5. Run the app

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

> **No API keys?** The app runs in full demo mode — route scoring, maps, and distress detection all work with rule-based fallbacks. Only Gemini AI narration and real SMS are skipped.

---

## 🔑 How to Get Free API Keys

### Google Gemini API (free tier)
1. Go to [https://aistudio.google.com](https://aistudio.google.com)
2. Sign in with your Google account
3. Click **Get API Key** → **Create API key**
4. Copy the key into `.env` as `GEMINI_API_KEY`

Free tier includes generous usage limits — more than enough for demos and hackathons.

### Twilio SMS (free trial)
1. Sign up at [https://www.twilio.com/try-twilio](https://www.twilio.com/try-twilio)
2. Verify your phone number
3. From the Console Dashboard, copy:
   - **Account SID** → `TWILIO_ACCOUNT_SID`
   - **Auth Token** → `TWILIO_AUTH_TOKEN`
   - **Phone Number** → `TWILIO_PHONE_NUMBER`

Free trial gives $15.50 credit — enough for hundreds of SMS messages.

> **Without Twilio keys:** The app simulates SMS alerts with on-screen notifications. The app never crashes.

---

## 🎬 Demo Flows

### Flow 1 — Route Safety Analysis
```
From: "Koregaon Park, Pune"
To:   "Hinjewadi, Pune"
Time: Night

→ Shows red/yellow safety score card
→ Displays interactive Folium map with colour-coded route
→ AI explains risk factors in plain English
→ Personalised tips generated for the journey
```

### Flow 2 — Distress Detection
```
Check In tab → type: "I think someone is following me"

→ Gemini detects HIGH risk instantly
→ SOS automatically triggered to trusted contacts
→ Nearest police station displayed
→ Step-by-step safety instructions shown
```

### Flow 3 — SOS Alert
```
SOS & Contacts tab → click "SEND SOS ALERT NOW"

→ SMS dispatched via Twilio (or simulated)
→ All trusted contacts notified
→ Confirmation with timestamp shown on screen
```

---

## 📸 Demo Screenshots

| Route Planner | SOS Page |
|---------------|----------|
| *(screenshot placeholder)* | *(screenshot placeholder)* |

| Distress Detection | Journey Tracker |
|--------------------|-----------------|
| *(screenshot placeholder)* | *(screenshot placeholder)* |

---

## 🔒 Safety Score System

```
Starting score: 100

Deductions:
  Night travel (8PM–5AM)      → -20
  Isolated road segment       → -15 each
  Dark area                   → -10
  Dim lighting                → -5
  High-risk zone (score <60)  → -25
  Long walk (>5km)            → -5

Bonuses:
  Main road / highway         → +10
  Crowded / commercial area   → +10
  Well-lit area               → +5
  Short distance (≤2km)       → +5

Result:
  🟢 80–100  → Safe Route
  🟡 60–79   → Moderate — take precautions
  🔴 0–59    → Avoid — find alternative
```

---

## 👥 Team

| Name | Role |
|------|------|
| *(Your Name)* | AI Engineer / Full Stack |
| *(Team Member)* | Data & Safety Research |
| *(Team Member)* | UI/UX Design |

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  Built with ❤️ for women's safety · SDG 5 — Gender Equality<br>
  <b>SafeRoute · AI that walks with you</b>
</p>
