<div align="center">

# AEGIS: AI-Powered Multimodal Satellite Flood Detection & Autonomous Disaster Response System

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Expo](https://img.shields.io/badge/Expo-v57.0-000020.svg?style=flat&logo=expo)](https://expo.dev)
[![React Native](https://img.shields.io/badge/React%20Native-0.86-61DAFB.svg?style=flat&logo=react)](https://reactnative.dev)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?style=flat&logo=python)](https://python.org)
[![MCP](https://img.shields.io/badge/MCP-Formal%20Server-8A2BE2.svg?style=flat)](https://modelcontextprotocol.io)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

</div>

<b>Aegis is an autonomous disaster response platform bridging large language models, satellite Earth observation, and spatiotemporal deep learning with real-time physical world infrastructure data. Powered by Google Gemini 2.5 Flash, the MirEye Earth API, and a dual-encoder SegFormer MiT-B2 architecture, Aegis handles open-ended disaster tasks while dynamically routing location-sensitive queries to verified spatial, hydrological, and environmental hazard tools.


Emergency managers, field responders, and residents often lack instant verified physical-world context during extreme weather events, forcing them to manually consult disjointed federal GIS portals. By fusing dual-encoder satellite Earth observation (SAR + Optical) with sub-meter physical intelligence, continuous Topographic Wetness Index (TWI) hydrology, 4D ConvGRU depth nowcasting, and an in-flight human-in-the-loop decision engine, Aegis identifies imminent flash flood zones, dynamically routes evacuees away from submersed corridors, and empowers incident commanders in real time.</b>

---

## 📋 Executive Overview

During major flood disasters, emergency response operations suffer from two fatal blind spots:

1. **The "Flat Map" Blind Spot:** Standard satellite segmentation only reveals where surface water was when the satellite passed overhead. It cannot predict ground elevation, soil saturation, building heights, population counts, or which dry roads will submerge in the next 6 hours.
2. **The "Naive Routing" Blind Spot:** Standard evacuation navigation systems route evacuees based on shortest straight-line distance, leading civilians directly into low-elevation terrain depressions and flooded road basins.

Aegis bridges this gap by injecting physical telemetry from the MirEye API (USGS 3DEP DEM elevation, slope, FEMA 100/500 yr floodplains, USGS NHD hydrography, and Overture building footprints) along with 4D spatiotemporal nowcasting into every routing, triage, and emergency dispatch decision.

---

## 🔬 Deep Learning Architecture & Pipeline

Aegis implements a custom **Dual-Encoder Multimodal SegFormer architecture** specifically optimized for high-precision flood boundary delineation in challenging weather and all-terrain scenarios, paired with a **4D Multi-Scale ConvGRU spatiotemporal nowcaster**.

![AEGIS Deep Learning Architecture & Pipeline](assets/architecture_pipeline.png)

### System Architecture Flow

```
 [Satellite SAR + Optical] ──► [NDWI Filter] ──► [Clean GeoJSON Inundation Mask]
                                                        │
                                                        ▼
                                            [Mireye Physical API]
                                    (DEM Elev, Slope, Floodplains, POIs)
                                                        │
                         ┌──────────────────────────────┴──────────────────────────────┐
                         ▼                                                             ▼
         [Predictive TWI Hydrology Layer]                            [DBSCAN Population Clustering]
              Flash-Flood Pooling Basins                                      │
                         │                                                             ▼
                         └──────────────────────────────┬──────────────────────────────┘
                                                        ▼
                                    [Elevation-Weighted Road Graph]
                                      (NetworkX / Dijkstra Routing)
                                                        │
                                                        ▼
                                       [Multi Criteria Triage Engine]
                                   Priority = Pop × (1 + Exp) / Elev_Safety
                                                        │
                                                        ▼
                                   [In Flight Feedback Interceptor]
                                (LangGraph: SHELTER_FULL / ROAD_CLOSED)
                                                        │
                         ┌──────────────────────────────┴──────────────────────────────┐
                         ▼                                                             ▼
         [Incident Commander Dashboard & SITREP]                      [Geo Targeted Citizen SMS / Twilio Voice]
```

**Core Innovation: What Aegis Solves**

<img width="331" height="302" alt="image" src="https://github.com/user-attachments/assets/675f372e-c163-436f-878d-a582e7b2e31a" />   

---

## 📊 Empirical Validation: Does Physical Context Matter?

To prove that the physical coordinate round-trip performs critical life-safety work rather than visual decoration, Aegis runs an empirical benchmark comparing a **Naive Straight-Line Strategy** against the **Context-Aware Strategy** across 33 real disaster clusters:

```
[SUMMARY RESULTS] 
  - Total Evaluated Clusters    : 33
  - Diverged Recommendations    : 2 clusters (6.1%)
  - Avg Extra Distance Accepted : +1.15 km (Safety Detour)
  - Sensitivity Projection      : 9.1% (Widened TWI Variance)
```

Context-aware routing altered the primary shelter recommendation in 6.1% of disaster clusters, accepting an average of +1.15 km of travel to steer evacuees away from high-risk, flood-compromised access corridors.

---

## ⚡ Core Platform Capabilities

- **🛰️ Multimodal Dual-Encoder Segmentation:** Fuses all-weather Sentinel-1 SAR C-band backscatter with Sentinel-2 multispectral optical imagery via a custom SegFormer MiT-B2 architecture, outputting clean georeferenced inundation masks even through dense cloud cover.
- **⏱️ 4D Spatiotemporal Depth Nowcasting:** Multi-scale 3-level ConvGRU network predicting flood depth progression, water flow velocity vectors, and peak inundation timestamps across upcoming 1 to 6-hour forecast horizons.
- **🤖 Autonomous 6-Agent LangGraph Pipeline:** Orchestrates ingestion, segmentation, predictive hydrology, DBSCAN population clustering, elevation-penalized Dijkstra routing, and advisory synthesis with live audit logs and human-in-the-loop control.
- **🔌 Formal Model Context Protocol (MCP) Server:** Exposes standardized AI tools (`fetch_radar_data`, `run_segformer_detection`, `run_nowcast_simulation`, `calculate_evacuation_routes`, `trigger_emergency_alert`) directly for LLM assistants at `/api/mcp/tools`.
- **📢 Automated Multi-Channel Emergency Dispatch:** Automated Twilio Voice call and SMS broadcasts with localized English and Hindi speech synthesis for field teams and impacted communities.
- **📱 Real-Time Citizen Ground Reporting:** Offline-first ground report logging with local AsyncStorage queuing, automated categorization, and real-time synchronization with emergency log feeds.
- **🗺️ Cross-Platform Mobile & Web Interface:** High-contrast tactical UI built on Expo / React Native featuring instant location presets (Patna, Houston, Charleston, Athens County), live radar layers, and safe shelter navigators.

---

## 📁 Repository Structure

```
Aegis/
├── assets/                                 # Architecture diagrams, banners, and schematics
│   ├── architecture_pipeline.png           # Deep learning SegFormer + nowcaster pipeline diagram
│   └── dashboard-hero-banner.jpg           # Dashboard visual assets
│
├── dell-flood-backend/                     # FastAPI Backend & AI Pipeline
│   ├── app/
│   │   ├── aegis/                          # Core Hydrology, Routing & Detection
│   │   │   ├── api/                        # MirEye & Elevation API Clients
│   │   │   ├── decision_engine/            # Triage & In-flight feedback interceptors
│   │   │   ├── pipeline/                   # TWI hydrology & DBSCAN clustering
│   │   │   ├── routing/                    # Elevation-penalized Dijkstra route engine
│   │   │   └── shelters/                   # Safe shelter discovery & ranking
│   │   ├── agent/                          # Autonomous 6-Agent LangGraph System
│   │   │   ├── graph.py                    # LangGraph workflow definition
│   │   │   └── tools.py                    # Dispatch, SMS, and Twilio voice call tools
│   │   ├── api/                            # REST Endpoints
│   │   │   └── endpoints.py                # Pipeline, nowcast, alerts, complaints
│   │   ├── mcp/                            # Formal Model Context Protocol (MCP)
│   │   │   └── aegis_mcp_server.py         # FastMCP server tool definitions
│   │   └── ml/                             # Deep Learning Models
│   │       ├── segformer_inference.py      # Dual-encoder SAR+Optical segmentation
│   │       └── urnn_nowcaster.py           # 4D ConvGRU spatiotemporal nowcasting
│   ├── main.py                             # Backend entrypoint (port 8000)
│   ├── requirements.txt                    # Python dependencies
│   └── .env.example                        # Backend environment variable template
│
├── dell-flood-app/                         # Cross-Platform React Native (Expo) App
│   ├── src/
│   │   ├── components/                     # Tactical UI Components
│   │   │   ├── NowcastPanel.tsx            # 4D Nowcasting player & location presets
│   │   │   ├── ReportForm.tsx              # Citizen ground issue reporting form
│   │   │   ├── SatelliteDetectionView.tsx  # Dual-encoder satellite radar inspection
│   │   │   ├── EvacuationRoutesView.tsx    # Interactive evacuation corridors
│   │   │   ├── AgenticPipelineView.tsx     # Live agent execution logs & SITREP
│   │   │   └── SettingsModal.tsx           # Bilingual toggle & API endpoint config
│   │   ├── services/
│   │   │   └── api.ts                      # Backend REST client & offline sync queue
│   │   ├── types/                          # TypeScript schemas
│   │   └── utils/
│   │       └── i18n.ts                     # Bilingual (English & Hindi) dictionary
│   ├── App.tsx                             # Application root & dashboard layout
│   ├── package.json                        # Node dependencies & Expo scripts
│   └── app.json                            # Expo app configuration
│
└── README.md                               # Project documentation
```

---

## 🚀 Installation & Quickstart Guide

### 1. Clone the Repository

```bash
git clone https://github.com/ShahzebAli9826/aws_hack.git
cd aws_hack
```

---

### 2. Backend Setup (`dell-flood-backend`)

1. **Navigate to backend folder:**
   ```bash
   cd dell-flood-backend
   ```
2. **Create & activate a virtual environment:**
   ```bash
   python -m venv venv
   # On Windows (PowerShell):
   .\venv\Scripts\activate
   # On Linux / macOS:
   source venv/bin/activate
   ```
3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Configure Environment Variables (`.env`):**
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
   *Fill in optional API keys (OpenAI, Gemini, Sentinel Hub, Twilio, Mapbox) as needed.*

5. **Start the FastAPI Backend Server:**
   ```bash
   python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```
   - **Backend API:** `http://localhost:8000` or `http://<YOUR_LOCAL_IP>:8000`
   - **Interactive API Docs:** `http://localhost:8000/docs`
   - **MCP Tool Catalog:** `http://localhost:8000/api/mcp/tools`

---

### 3. Frontend Web Setup (`dell-flood-app`)

1. **Open a new terminal & navigate to app folder:**
   ```bash
   cd dell-flood-app
   ```
2. **Install Node.js dependencies:**
   ```bash
   npm install
   ```
3. **Start on Website (React Native Web):**
   ```bash
   npm run web
   # Or:
   npx expo start --web
   ```
   - Access the live web app in browser at: `http://localhost:8081`

---

### 4. Running on Mobile Phone using Expo Go 📱

To run the mobile app on an actual Android or iOS device using **Expo Go**:

1. **Connect to Same Wi-Fi:** Ensure your phone and development computer are connected to the **same local Wi-Fi network**.
2. **Find Local IP Address:**
   - **Windows:** Run `ipconfig` in CMD/PowerShell (look for IPv4 Address under Wireless LAN/Ethernet, e.g., `192.168.1.7`).
   - **macOS / Linux:** Run `ifconfig` or `ip a`.
3. **Configure API Endpoint:**
   - By default, `dell-flood-app/src/services/api.ts` targets `http://192.168.1.7:8000/api`.
   - Update `DEFAULT_API_URL` in `src/services/api.ts` or change it dynamically inside the **App Settings Panel** within the app UI.
4. **Start Expo LAN Server:**
   ```bash
   npx expo start --lan
   ```
5. **Open in Expo Go:**
   - **Android:** Open the **Expo Go** app, tap **Scan QR Code**, and scan the QR code printed in your terminal (or type `exp://<YOUR_LOCAL_IP>:8081`).
   - **iOS:** Open the default **Camera App**, scan the QR code, and open in Expo Go.

---

### 5. Building Standalone Android APK (EAS Build)

To build a standalone installable `.apk` file for Android:

1. Install EAS CLI (if not installed):
   ```bash
   npm install -g eas-cli
   ```
2. Run EAS Preview Build:
   ```bash
   npx eas-cli build --platform android --profile preview
   ```
3. Once completed on Expo Cloud, download and install the resulting `.apk` file directly on any Android phone.

---

## 🗺️ Tactical Disaster Map Visualizations

Aegis renders **100% watermark-free, high-contrast Folium HTML maps** built for emergency management operations. Every map includes an interactive Disaster HUD legend and multi-layer toggles:

* **Active Inundation Footprint:** High-contrast danger polygon extracted via dual-encoder SAR/Optical satellite imagery.
* **Critical Runoff Nodes:** Glowing magenta markers identifying concave terrain basins with high TWI scores prone to flash pooling.
* **Affected Neighborhood Centroids:** High-contrast targets displaying population estimates and building counts from DBSCAN clustering.
* **Safe Emergency Shelters:** Emerald pins indicating safe facilities tagged with ground DEM elevation.
* **Elevation-Weighted Evacuation Paths:** Cyan polyline corridors steering clear of flood-prone road segments.

---

## 🛡️ Security & Privacy
- Sensitive keys (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `GEMINI_API_KEY`) are kept strictly inside `.env` files and excluded from source control.
- Citizen ground reports are handled locally and can operate in an offline-cached queue mode before synchronization.

---

## 📄 License

This project is licensed under the **MIT License**. Built with physical intelligence powered by **Mireye**.
