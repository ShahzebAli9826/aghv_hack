# Final Master Implementation Document: AEGIS
## Complete AI-Powered Satellite Detection & U-RNN Spatiotemporal Flood Response System

> **Document Version:** 3.0.0 (Unified Master)  
> **System Name:** AEGIS (AI-Powered Multimodal Satellite Flood Detection & Autonomous Disaster Response System)  
> **Core Pillars:**  
> 1. **Live Multimodal Satellite Detection** (Sentinel-1 SAR + Sentinel-2 Optical + SegFormer MiT-B2)  
> 2. **U-RNN 4D Hydrodynamic Spatiotemporal Nowcasting** (ConvGRU U-Net with YOLOX Dual-Head Depth Modeling)  
> 3. **Time-Varying Predictive Evacuation Routing** (Dynamic Arrival-Time Dijkstra)  
> 4. **Autonomous Agent & Multi-Model RAG Command Center** (LangGraph + Bedrock/Gemini)

---

## 1. System Architecture & Tech Stack

Aegis implements an end-to-end split architecture connecting an offline-first, cross-platform mobile/web client with a high-performance geospatial AI backend.

### Tech Stack Breakdown
* **Mobile / Web Client (`dell-flood-app`):**
  * **Framework:** React Native / Expo SDK 57 (React Native Web support for desktop & mobile PWA).
  * **Language:** TypeScript 5.x.
  * **Mapping & GIS Display:** Leaflet.js with Esri World Imagery (high-resolution satellite basemap) + Mapbox GL Vector Tiles.
  * **State Management:** React Query (`@tanstack/react-query`) + React Context.
  * **Progressive Pipeline Polling:** 1-second interval job status stream reading `/status/{job_id}`.
  * **Audio Alerts:** `expo-speech` (real-time alert readout via TTS).
* **Backend Server (`dell-flood-backend`):**
  * **Framework:** FastAPI (Python 3.11/3.14) + Uvicorn.
  * **Neural Networks:**
    1. **SegFormer MiT-B2 Fusion:** Custom Dual-Encoder PyTorch architecture (`best_model_focal.pth`) for synoptic flood boundary segmentation from fused SAR & Optical imagery.
    2. **U-RNN Spatiotemporal Nowcaster:** 3-Scale ConvGRU U-Net (`urnn_nowcaster.py`) predicting continuous water depths $H(x, y, t)$ across $+15, +30, +60, +120$ minutes.
  * **Image Registration:** OpenCV (`cv2.findTransformECC`) for affine sub-pixel alignment of SAR and Optical rasters.
  * **Geospatial Processing:** `rasterio` (shape contour polygonization), `geopandas`, `shapely`, `pysheds` (drainage accumulation).
  * **Live Satellite Telemetry:** Sentinel Hub Process API (Sentinel-2 L2A optical, Sentinel-1 GRD SAR) with in-memory OAuth token caching.
  * **Live Physical Telemetry:** Mireye Physical Intelligence API (USGS 3DEP DEM elevation, FEMA floodplains, Overture building footprints).
  * **Live Impact Telemetry:** OpenStreetMap Overpass API (live building, road, and hospital spatial joins) + WorldPop gridded density rasters.
  * **Generative AI & RAG:** ChromaDB / Amazon Bedrock Knowledge Bases + LangGraph autonomous agent cycle + Claude 3 Haiku / Google Gemini 2.5 Flash.
  * **Emergency Dispatchers:** Amazon SNS / Twilio (SMS alerts & IVR voice calls) + SMTP (automated SITREP PDF bulletins).

---

## 2. Directory Structure

```
Aegis/
├── best_model_focal.pth                # Trained PyTorch SegFormer Weights (245MB)
├── awsplan.md                          # AWS Cloud Architecture & Deployment Guide
├── map_implementation.md               # Live Sentinel Detection & Status Stream Specification
├── urnn_integration_plan.md            # U-RNN 4D Hydrodynamic Spatiotemporal Nowcasting Blueprint
├── fixes.md                            # Non-Hardcoded Fixes & Detailed Code Blueprint
├── final_implementation_doc.md         # [THIS FILE] Unified Master Architecture Reference
│
├── dell-flood-app/                     # React Native / Expo Client
│   ├── App.tsx                         # Master Navigation, Auth Gate, Citizen & Official Portals
│   ├── package.json                    # NPM Dependencies
│   └── src/
│       ├── components/
│       │   ├── MapView.tsx             # Interactive Map, Progressive Status Panel, S1/S2 Previews, 4D Time-Scrubber
│       │   ├── ReportForm.tsx          # Crowdsourced Citizen Reporting Interface
│       │   ├── AgentPanel.tsx          # Autonomous Agent Execution & Activity Log Viewer
│       │   ├── TriagePanel.tsx         # Neighborhood Priority Ranking & Shelter Allocation
│       │   ├── SettingsPanel.tsx       # Backend URL configuration & Offline toggles
│       │   └── ReportViewerModal.tsx   # PDF & SITREP Bulletin Viewer
│       ├── services/
│       │   └── api.ts                  # Client API Bindings & Fallback Vault
│       └── utils/
│           └── routing.ts              # Client-side Graph Navigation
│
└── dell-flood-backend/                 # FastAPI / PyTorch Backend
    ├── main.py                         # Application Entry Point & CORS Setup
    ├── requirements.txt                # Python Dependencies
    ├── corpus/                         # NDMA, FEMA & UN-OCHA Reference Documents for RAG
    ├── reports/                        # Auto-generated SITREP PDF Bulletins
    └── app/
        ├── api/
        │   ├── endpoints.py            # API Routes (/run-detection, /status/{id}, /nowcast, /alerts/*)
        │   └── schemas.py              # Pydantic Schemas
        ├── ml/
        │   ├── inference.py            # SegFormer MiT-B2 Dual-Encoder (Cloud-Gated)
        │   ├── postprocess.py          # ECC Registration, NDWI Baseline, DEM Pruning, rasterio Vectorizer
        │   └── urnn_nowcaster.py       # U-RNN ConvGRU U-Net Spatiotemporal Nowcaster
        ├── aegis/
        │   ├── pipeline/
        │   │   ├── satellite_ingest.py     # Sentinel Hub OAuth & Process API Client
        │   │   ├── dynamic_hydro_tensor.py # 5-Factor Physical Hydrological Tensor Assembler
        │   │   ├── impact_analyzer.py      # Live Overpass OSM & WorldPop Spatial Joins
        │   │   └── predictive_twi.py       # Topographic Wetness Index & Drainage Basins
        │   └── routing/
        │       ├── graph_router.py         # Routable Road Graph Builder (NetworkX)
        │       └── dynamic_router.py       # Time-Varying Dijkstra Router (Arrival-Time Penalized)
        ├── agent/
        │   ├── flood_agent.py          # Autonomous LangGraph Cron Loop (Perceive-Plan-Act-Reflect)
        │   └── tools.py                # Live Weather Telemetry & Alert Dispatchers
        └── RAG/
            ├── vector_store.py         # Vector Indexing for Flood Documents
            └── generator.py            # Multimodal Situation Report Compiler
```

---

## 3. Database Schema

Managed via SQLite (`flood_database.db`) with seamless migration to Amazon DynamoDB:

```sql
-- Users and authentication
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password_hash TEXT,
    role TEXT, -- 'citizen' or 'official'
    phone TEXT,
    expo_push_token TEXT DEFAULT NULL
);

-- Crowdsourced ground reports
CREATE TABLE complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    latitude FLOAT,
    longitude FLOAT,
    reported_severity TEXT, -- 'MINOR', 'MODERATE', 'HIGH', 'CRITICAL'
    description TEXT,
    status TEXT DEFAULT 'pending', -- 'pending', 'under review', 'resolved'
    model_confirmed INTEGER DEFAULT 0, -- Verified by satellite / U-RNN intersection
    timestamp REAL,
    location_name TEXT DEFAULT ''
);

-- Safe relief facilities and shelters
CREATE TABLE shelters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    latitude FLOAT,
    longitude FLOAT,
    capacity TEXT, -- 'green', 'yellow', 'grey'
    slots_available INTEGER,
    elevation_m FLOAT DEFAULT 0.0
);
```

---

## 4. Master Feature List & Integrated Implementations

### STAGE 1 — BACKGROUND MONITORING & SENSING
1. **Rainfall Accumulation Telemetry:** Queries OpenWeather / Open-Meteo live hourly precipitation sequences. Sums 5-day totals and builds instantaneous storm hyetographs.
2. **Hydrological Gauge Estimation:** Scales simulated river gauge levels ($<45\text{mm}$: normal, $45-90\text{mm}$: warning, $>90\text{mm}$: danger).
3. **LangGraph FloodAgent Cron Loop:** Autonomous agent cycle executing *Perceive $\rightarrow$ Plan $\rightarrow$ Ingest $\rightarrow$ Nowcast $\rightarrow$ Route $\rightarrow$ SITREP $\rightarrow$ Reflect*.

### STAGE 2 — LIVE MULTIMODAL SATELLITE ACQUISITION (`map_implementation.md`)
4. **Thread-Safe Sentinel Hub OAuth:** Manages bearer tokens with TTL caching, querying the Process API.
5. **Exact Geographic Bounding Box:** Generates identical $4\text{km} \times 4\text{km}$ bounding boxes for both Sentinel-2 and Sentinel-1 rasters at $512 \times 512$ resolution.
6. **Sentinel-2 L2A Optical Fetch:** Obtains B04 (Red), B03 (Green), B02 (Blue), and CLM (Cloud Mask) bands.
7. **Sentinel-1 GRD SAR Fetch:** Pulls VV and VH radar backscatter bands (cloud-penetrating).
8. **OpenCV ECC Image Registration:** Computes Euclidean warp affine matrices (`cv2.findTransformECC`) to eliminate inter-sensor pixel shifts.
9. **Progressive Background Job Polling:** Frontend polls `/status/{job_id}` every $1\text{s}$, appending live status messages as each step executes.
10. **Three Progressive Image Preview Panels:**
    * **Panel 1 (Optical):** Mounts as soon as Sentinel-2 finishes.
    * **Panel 2 (SAR):** Mounts as soon as Sentinel-1 finishes.
    * **Panel 3 (Model Output):** Mounts with an interactive toggle between **Composite Overlay** (60% alpha over satellite terrain) and **Raw RdYlBu_r Probability Heatmap**.

### STAGE 3 — DUAL-ENCODER AI DETECTION & FUSION
11. **Dual MiT-B2 SegFormer Architecture:** Independent Transformer encoders process SAR and Optical streams. Early stages fused via Gated Convolutions; deep stages fused via Cross-Attention.
12. **Dynamic Cloud-Adaptive Gating:** Scales optical feature tensors by $(1.0 - 0.8 \times \text{cloud\_fraction})$, forcing the model to rely on radar backscatter when clouds obscure ground visibility.
13. **Dynamic NDWI Baseline Subtraction:** Computes historical NDWI from a clear image 30 days prior to remove permanent rivers and lakes from the flood mask.
14. **Physical DEM High-Ground Pruning:** Validates flood pixels against terrain elevations to discard impossible uphill false detections.
15. **True Polygonization:** Uses `rasterio.features.shapes()` to vectorize active flood masks into GeoJSON boundary polygons without rectangular bounding box approximations.

### STAGE 4 — U-RNN 4D SPATIOTEMPORAL NOWCASTING (`urnn_integration_plan.md`)
16. **5-Channel Hydrological Tensor Assembly:** Fuses:
    * Instantaneous storm rainfall sequence ($R_t$ in $\text{mm/min}$)
    * Cumulative storm rainfall volume ($\sum R_t$ in $\text{mm}$)
    * Normalized DEM elevation raster
    * Surface imperviousness fraction ($[0, 1]$ based on Overture building/road density)
    * Stormwater drainage inlet density mask
17. **Multi-Scale ConvGRU U-Net Engine:** 3-stage encoder-decoder propagating spatial-temporal hidden states across future horizons ($+15, +30, +60, +120\text{ min}$) with $<80\text{ms}$ inference latency.
18. **Dual YOLOX Prediction Head:**
    * **Regression Branch:** Predicts continuous water depth $h \ge 0$ in millimeters.
    * **Classification Branch:** Predicts wet/dry probability $\hat{p} \in [0, 1]$.
    * **Physical Masking:** Zeroes out trace moisture in elevated dry cells: $\tilde{h} = h \cdot \mathbb{I}(\hat{p} \ge 0.40)$.
19. **Sliding-Window Pre-warming (SWP):** Evaluates multi-hour storm hydrographs without GPU memory exhaustion by warming recurrent states over sliding windows.
20. **Interactive 4D Time-Scrubber UI:** Allows users on the map to scrub across $+0\text{m}, +15\text{m}, +30\text{m}, +60\text{m}$ to visualize water accumulation over time.

### STAGE 5 — LIVE IMPACT ASSESSMENT & DEMOGRAPHICS
21. **Live OSM Overpass Spatial Joins:** Executes spatial intersections between flood polygons and real OpenStreetMap structures (buildings, roads, hospitals, schools).
22. **WorldPop Density Calculation:** Masks gridded population rasters to calculate affected civilian counts.
23. **Composite Multi-Criteria Severity Scoring:**
    $$\text{Score} = \left(\frac{\text{Pop}}{10000} \times 0.4\right) + \left(\frac{\text{Buildings}}{1000} \times 0.3\right) + \left(\frac{\text{Hospitals}}{5} \times 0.2\right) + \left(\frac{\text{Area}}{10} \times 0.1\right)$$

### STAGE 6 — TIME-VARYING EVACUATION ROUTING
24. **Arrival-Time-Aware Dijkstra Pathfinding:** For each road edge $e = (u, v)$, queries the U-RNN forecasted water depth at the **exact estimated arrival time** $t_{\text{arrival}}$ of the evacuee:
    $$\text{Weight}(e, t_{\text{arrival}}) = \begin{cases} \infty & \text{if } \text{Depth}(e, t_{\text{arrival}}) \ge 0.30\,\text{m} \\ L_e \cdot \left(1.0 + 4.0 \cdot \frac{\text{Depth}(e, t_{\text{arrival}})}{0.30}\right) & \text{if } \text{Depth}(e, t_{\text{arrival}}) < 0.30\,\text{m} \end{cases}$$
25. **Clearance-Based Passability Triage:** Categorizes road corridors for passenger cars ($<0.30\text{m}$ clearance) versus high-clearance emergency rescue trucks ($<0.50\text{m}$).

### STAGE 7 — MULTI-MODAL ALERTS & SITREP DISPATCH
26. **Automated SITREP PDF Generation:** Uses ReportLab to compile executive summaries, satellite previews, impact matrices, and shelter directories into downloadable bulletins.
27. **Amazon SNS Mass SMS Broadcast:** Delivers emergency alerts simultaneously to all registered phones in the impacted zone.
28. **Twilio IVR Voice Warning:** Outbound voice gateway delivering automated spoken warnings to endangered residents.
29. **Depth-Grounded RAG Reports:** Generates official disaster management briefs via Bedrock / Gemini with forecasted peak water depths.

---

## 5. End-to-End Verification Matrix

| Test Case | Inputs | Expected Observable Result |
|---|---|---|
| **Live Satellite Sweep** | `Muzaffarpur, Bihar` ($26.12^\circ\text{N}, 85.39^\circ\text{E}$) | Status panel logs all 12 steps sequentially; S1, S2, and Composite images load progressively; GeoJSON polygon highlights inundation. |
| **High Cloud Occlusion** | `cloud_cover = 85.0%` | Optical tensor attenuated; model logs `SAR weighting prioritized`; radar backscatter correctly drives the flood mask. |
| **U-RNN Water Depth Nowcast** | `Jorhat, Assam` ($26.75^\circ\text{N}, 94.20^\circ\text{E}$) | Returns 4-step depth tensor ($0, 15, 30, 60\text{ min}$); time-scrubber renders dynamic color-coded water depths ($<0.15\text{m}$, $0.15-0.30\text{m}$, $>0.30\text{m}$). |
| **Time-Dependent Evacuation** | Flooded arterial corridor | Standard Dijkstra fails or takes submerged road; Dynamic Router successfully detours along elevated bypasses with $0.0\text{m}$ arrival water depth. |
| **Live OSM Impact Query** | Urban polygon | Overpass API returns real building counts; values match real OpenStreetMap structures. |

---
*Created for Team Aegis | AI Flood Detection & Disaster Response System*
