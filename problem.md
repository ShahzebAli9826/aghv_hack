# AEGIS: Comprehensive Problem Statement, Complete Audit Catalogue & User Feature Requirements
## Master Problem Catalogue (`problem.md` — All 35 Problems `P1`–`P35`)

> **Document Status:** Complete Engineering Problem Specification (100% Synced with `FloodApp_Analysis.md`, `map_implementation.md`, `urnn_integration_plan.md` & User Requirements)  
> **Solved By:** [`solution_implementation_doc.md`](file:///c:/Users/SHAHZEB%20ALI/OneDrive/Desktop/mireye/Aegis/solution_implementation_doc.md) & [`fixes.md`](file:///c:/Users/SHAHZEB%20ALI/OneDrive/Desktop/mireye/Aegis/fixes.md)  
> **Target System:** Aegis (AI-Powered Multimodal Satellite Flood Detection & Autonomous Disaster Response System)  
> **Date:** October 2026

---

## Table of Contents
1. [Executive Overview](#1-executive-overview)
2. [Part 1: Security & Vulnerability Problems (`P1`–`P10`)](#2-part-1-security--vulnerability-problems-p1p10)
3. [Part 2: Correctness Bugs, Broken Aegis Imports & Runtime Crashes (`P11`–`P17`)](#3-part-2-correctness-bugs-broken-aegis-imports--runtime-crashes-p11p17)
4. [Part 3: Scientific Validity, Hydrology & Hardcoding Problems (`P18`–`P25`)](#4-part-3-scientific-validity-hydrology--hardcoding-problems-p18p25)
5. [Part 4: Agentic Pipeline, Formal MCP Server & Safety Guardrail Problems (`P26`–`P28`)](#5-part-4-agentic-pipeline-formal-mcp-server--safety-guardrail-problems-p26p28)
6. [Part 5: Spatiotemporal 4D Hydrodynamic Nowcasting & Dynamic Routing Problems (`P29`–`P30`)](#6-part-5-spatiotemporal-4d-hydrodynamic-nowcasting--dynamic-routing-problems-p29p30)
7. [Part 6: User-Mandated Pipeline, New App Tab, Photo Upload, `+917678656930` Call & Multilingual Requirements (`P31`–`P35`)](#7-part-6-user-mandated-pipeline-new-app-tab-photo-upload-917678656930-call--multilingual-requirements-p31p35)
8. [Master 35-Problem Cross-Reference Index](#8-master-35-problem-cross-reference-index)

---

## 1. Executive Overview

This document is the definitive catalogue of **all 35 problems and feature requirements (`P1`–`P35`)** identified across the Aegis codebase:
1. **Security & Vulnerability Flaws (`P1`–`P10`):** Every critical, high, medium, and low vulnerability from `FloodApp_Analysis.md` §1.
2. **Correctness Bugs & Broken Aegis Modules (`P11`–`P17`):** Every broken import (`extractor.py`, `evacuate.py`, `cluster.py`), missing dependency, kwarg mismatch, missing routing function, triage override bug, and ChromaDB indexing flaw from `FloodApp_Analysis.md` §2.
3. **Scientific Validity, Hydrology & Ethical Attribution (`P18`–`P25`):** Fake ECC logs, missing Optical-Only vs. SAR+Optical Fusion toggle, area scaling mismatch, confidence clamping, hardcoded demographic multipliers, fake 4-quadrant GeoJSON boxes, synthetic CWC river gauges, Gaussian TWI DEM, sine-wave evacuation curves, US county triage presets, and suppressed map attribution from `FloodApp_Analysis.md` §3 & §4.
4. **Agentic Pipeline & Formal MCP Server (`P26`–`P28`):** Missing Formal MCP Server, procedural `FloodAgent` script without LangGraph multi-agent orchestration or progressive escalation, missing Human-in-the-Loop (HITL) approval gate, missing Crowd Auto-Trigger, missing CAP v1.2 standard export, and missing Numeric-Claim Hallucination Validator from `FloodApp_Analysis.md` §5 & §6.
5. **4D Spatiotemporal Depth Nowcasting (`P29`–`P30`):** Static 2D binary masks unable to forecast continuous water depth $H(x,y,t)$ in meters (`holmescao/U-RNN`) and static Dijkstra routing that traps evacuees on submerging roads.
6. **User-Mandated Features (`P31`–`P35`):**
   - **P31:** U-RNN integrated directly into the **Satellite Analysis Pipeline** with 16 progressive bilingual live console logs + Panel 4 depth scrubber in `MapView.tsx`.
   - **P32:** A dedicated 6th Bottom Navigation Tab: **`"4D Nowcast"` (`NowcastPanel.tsx`)** for interactive hydrodynamic simulation, 5-channel tensor telemetry, and Static vs. Time-Varying route comparison.
   - **P33:** **Photo Evidence Upload** in **Raise Query (`ReportForm.tsx`)** with camera/gallery picker, compression $\le 150\text{KB}$, thumbnail preview, and Official Triage display.
   - **P34:** Hardcoded default demonstration emergency call target **`+917678656930` (`7678656930`)** with dynamic LLM-generated **Hindi (`hi-IN`, `Polly.Aditi`)** and **English (`en-IN`, `alice`)** voice warning scripts.
   - **P35:** **First-Launch Language Selection Modal** (`🇬🇧 English` / `🇮🇳 हिन्दी`) before starting the app + header language toggle + full app-wide localization (`i18n.ts`).

---

## 2. Part 1: Security & Vulnerability Problems (`P1`–`P10`)

* **PROBLEM P1 (Critical — `endpoints.py`, `main.py`): Zero Backend Authentication & RBAC on Privileged Endpoints + Wildcard CORS**  
  `/alerts/voice`, `/alerts/email`, `/alerts/email-report`, `/notifications/broadcast`, `/complaints/resolve`, and `/agent-cycle` have zero authentication or role checks. `main.py` sets `allow_origins=["*"]` with `allow_credentials=True`. Any unauthenticated caller can trigger outbound calls, send mass emails, resolve citizen complaints, or trigger expensive inference cycles.
* **PROBLEM P2 (Critical — `endpoints.py:296`, `tools.py:135`): TwiML XML Injection & Arbitrary Outbound Dialing**  
  `trigger_voice_call` and `/alerts/voice` build TwiML via raw string interpolation (`f"<Response><Say>{message}</Say></Response>"`) and accept arbitrary `phone_number` strings without E.164 validation or allowlisting, allowing XML injection (`</Say><Dial>...`) and toll fraud.
* **PROBLEM P3 (Critical — `MapView.tsx:704-712`, `endpoints.py:1518`): Stored Cross-Site Scripting (XSS) in Map Complaint Tooltips**  
  Citizen complaint `username` and `description` are stored raw in `/report-flood` and concatenated directly into Leaflet HTML tooltips (`bindTooltip('<b>' + c.username + ... + c.description)`), enabling stored XSS in the official dashboard.
* **PROBLEM P4 (Critical — `api.ts:207-208`): Client-Side Offline Auth Bypass (`password === "123"`)**  
  When the backend is unreachable or slow, `api.ts` falls back to local authentication where `password === "123"` logs into any cached user account and grants `official` role access.
* **PROBLEM P5 (High — `endpoints.py:85-91`, `1677`): Unsalted SHA-256 Passwords & Hardcoded Seed Accounts**  
  User passwords are hashed with unsalted `hashlib.sha256(password.encode()).hexdigest()`, and default accounts (`saif`, `shah`, `saif_official`, `admin`) are seeded with password `"123"` in production startup code.
* **PROBLEM P6 (High — `endpoints.py:258`): Path Traversal & Unbounded Disk Write in PDF Generation**  
  `location` from the request body is interpolated directly into `filename = f"./reports/report_{location}_{ts}.pdf"`, enabling path traversal (`../../`) and disk exhaustion.
* **PROBLEM P7 (High — `endpoints.py:1148`, `1971`, `2101`, `flood_agent.py:37`): Unbounded In-Memory State & Cross-User Agent Log Leak**  
  Global dictionaries `jobs{}`, `AGENT_TRACES{}`, and `_ACTIVE_TRIAGE_SESSIONS{}` grow without TTL or max-size bounds. Furthermore, `FloodAgent` is a singleton whose `self.activity_log` accumulates across all runs and leaks prior users' runs in `/agent-cycle`.
* **PROBLEM P8 (Medium — `mireye_chatbot.py`, `generator.py`): Prompt Injection Surface**  
  Untrusted citizen complaint descriptions and user chat inputs are concatenated directly into LLM system instructions without XML isolation tags (`<untrusted_user_input>`) or role separation.
* **PROBLEM P9 (Medium — `generator.py:58`, `endpoints.py:1734`): Gemini API Key Exposed in URL Query String**  
  Gemini REST API calls append `?key={gemini_key}` to the URL instead of using the `x-goog-api-key` HTTP header, leaking the key into proxy and exception logs.
* **PROBLEM P10 (Medium/Low — `MapView.tsx:414`, `endpoints.py:1799`): Unvalidated `postMessage('*')` & Broken `/geocode` Slang Filter**  
  `MapView.tsx` posts messages with targetOrigin `'*'` without schema validation. Meanwhile, `/geocode` checks `any(w in q_clean for w in ["mc", "bc", "kutta", ...])` via substring matching, which blocks legitimate flood-prone Indian towns like **Kuttanad** (Kerala) and **McLeod Ganj** (Himachal Pradesh)!

---

## 3. Part 2: Correctness Bugs, Broken Aegis Imports & Runtime Crashes (`P11`–`P17`)

* **PROBLEM P11 (High — `requirements.txt`, `mireye_chatbot.py:12`): Missing Required Python Packages Crash Fresh Installs**  
  `mireye_chatbot.py` imports `from openai import OpenAI` at module load time, crashing the entire FastAPI app if `openai` is not installed. `scipy`, `scikit-learn`, `networkx`, `folium`, `httpx`, `Pillow`, `python-jose`, `passlib`, and `cachetools` are also missing from `requirements.txt`.
* **PROBLEM P12 (High — `endpoints.py:196` vs `958`): Push Broadcast `TypeError` Kwarg Mismatch**  
  `send_expo_push_notification(push_token, title, body)` takes 3 arguments, but `/notifications/broadcast` calls it with `data={"type": "Emergency Broadcast"}`, raising a `TypeError` on every broadcast.
* **PROBLEM P13 (High — `flood_agent.py:220`, `evacuation_engine.py`): Missing `compute_elevation_evacuation_route` Function**  
  `flood_agent.py` imports `compute_elevation_evacuation_route` from `app.aegis.routing.evacuation_engine`, which does not exist (`evacuation_engine.py` only defines `EvacuationEngine`), causing Step 4 of the agent cycle to fail every time.
* **PROBLEM P14 (Medium — `extractor.py`, `evacuate.py`, `cluster.py`): Broken Imports & Missing `app/aegis/models.py`**  
  - `app/aegis/pipeline/extractor.py` imports `make_batch_cache_key`, `polygon_hash`, `DISASTER_PRESETS`, `FloodDossier`, and `PointDossier` from `app.aegis.models` (which does not exist).
  - `app/aegis/pipeline/evacuate.py` imports `polygon_hash` from `app.aegis.models`.
  - `app/aegis/pipeline/cluster.py` accesses `polygon.name` on `GeoPolygon` (which only has `place`) and calls `np.random.seed(42)` inside `extract_Elevation_and_Landcover`, resetting global NumPy RNG state.
* **PROBLEM P15 (Medium — `triage_engine.py:249-297`, `endpoints.py:2131-2167`): Triage Overrides & Audit Logs Broken**  
  - `node_allocate_shelters` omits `override_logs` from its return dict, so the LangGraph state drops audit logs.
  - `/aegis/triage/override` only mutates `_ACTIVE_TRIAGE_SESSIONS[run_id]["overrides"]` and re-runs `node_allocate_shelters` without re-running `node_compute_triage`, making `FORCE_PRIORITY` a complete no-op and `ROAD_CLOSED` only log a text message without rerouting.
* **PROBLEM P16 (Medium — `vector_store.py:99-103`, `corpus/`): New RAG Documents Never Indexed**  
  `initialize_knowledge_base()` returns early whenever `self.collection.count() > 0`, so new or updated markdown files in `corpus/` are ignored unless the entire ChromaDB folder is deleted. Additionally, `corpus/` only contains two tiny synthetic text files.
* **PROBLEM P17 (Medium/Low — `inference.py:345`, `endpoints.py:238`, `flood_agent.py:36`, `api.ts:561`): Duplicate Model Instances, Hardcoded Laptop Path & Retired Model IDs**  
  - `SegFormerMiTB2Fusion` is instantiated twice (in `endpoints.py` and `flood_agent.py`), doubling memory consumption (~500 MB).
  - `inference.py:345` contains a hardcoded developer path `c:\Users\rawal\Desktop\FloodDetection\...`.
  - `api.ts:561` (`exportEmergencyPDF`) uses `DEFAULT_API_URL` instead of `this.apiUrl`.
  - `endpoints.py` and `generator.py` reference non-existent `gemini-3.8-flash` and retired `claude-3-haiku-20240307`.

---

## 4. Part 3: Scientific Validity, Hydrology & Hardcoding Problems (`P18`–`P25`)

* **PROBLEM P18 (`endpoints.py:1224`, `postprocess.py`): ECC Co-Registration is Only a Log String**  
  Step 4 logs `"ECC Co-registration complete — sub-pixel shift < 0.4px"` without running `cv2.findTransformECC` or `cv2.warpAffine` on the Sentinel-1 and Sentinel-2 arrays.
* **PROBLEM P19 (`inference.py:513`, `MapView.tsx`): Simplistic Cloud Weighting & No Optical-Only vs. Fusion Toggle**  
  Cloud weighting multiplies the entire probability map by `(1 - cloud*0.4)` using an external weather scalar instead of Sentinel-2 cloud masks, and judges cannot toggle between **Optical-Only** and **SAR+Optical Fusion** to visually verify radar cloud penetration.
* **PROBLEM P20 (`postprocess.py:85`, `flood_agent.py:120`): Conflicting Pixel Area Constants & Clamped Confidence**  
  `postprocess.py` uses `0.000019 km²/px` while `flood_agent.py` uses `0.0001 km²/px` (a $5.26\times$ discrepancy). Confidence is averaged over the entire $512 \times 512$ tile (including dry land) and then artificially clamped to 68–70%.
* **PROBLEM P21 (`endpoints.py:1345-1435`): Hardcoded Impact Multipliers & Fake 4-Quadrant Bounding Boxes**  
  `population_affected = int(area_sq_km * 1150)` and `buildings_damaged = int(area_sq_km * 40)` are hardcoded formulas, and flood GeoJSON polygons are 4 rectangular quadrant boxes (`np.min`/`np.max` row/col) instead of real contour polygons and live OpenStreetMap Overpass spatial joins.
* **PROBLEM P22 (`tools.py:32-99`, `193-214`): Mixed Forecast/Observed Rainfall & Synthetic CWC River Gauge**  
  `check_weather` mixes 24h forecast with 5-day historical rainfall under the same `rainfall_5d_mm` field, and `check_gauge` fabricates river levels via `level = base_level + (rain_mm * 0.08)` instead of querying live **Open-Meteo GloFAS River Discharge** (`https://flood-api.open-meteo.com/v1/flood`).
* **PROBLEM P23 (`predictive_twi.py`, `endpoints.py:2174`, `triage_engine.py`): Gaussian TWI DEM, Sine-Wave Evacuation, US Counties & Missing 24h/48h Spread Polygons**  
  - `predictive_twi.py` generates a random Gaussian DEM seeded by `int((lat+lon)*1000)`.
  - `/aegis/evacuation/plan` generates waypoints using `math.sin(frac * math.pi) * 0.008` and `elev = 15 + dist * 4.2`.
  - `triage_engine.py` uses 30 US counties (`"Athens #1"`) instead of Indian flood basins.
  - Missing **24-hour (orange)** and **48-hour (yellow)** downstream flood spread prediction polygons and `downhill_warnings`.
* **PROBLEM P24 (`endpoints.py:1534`, `1091`, `api.ts:279`, `routing.ts`): Hash-Modulus Complaint Score, Volatile Offline Queue, Unwired `routing.ts` & Fake GeoTIFF Upload**  
  - `/complaints/list` computes `match_score = 92 + int(abs(lat*17.3 + lon*29.1 + ts) % 6)` instead of the documented **60% user severity + 40% model confidence** formula.
  - `offlineComplaints` in `api.ts:279` is an in-memory JS array lost on page reload instead of persisting in `AsyncStorage`.
  - `dell-flood-app/src/utils/routing.ts` is never imported anywhere.
  - `/upload-geotiff` ignores the uploaded file bytes and returns hardcoded Patna metadata.
* **PROBLEM P25 (`MapView.tsx:429`, `endpoints.py:725`): Suppressed Map Attribution & Impersonated Official SDMA Signatures**  
  `MapView.tsx` hides `.leaflet-control-attribution` (`display: none`), violating OSM/Esri terms. Generated PDFs claim `"Approved By: Director of Operations, SDMA"` without a prototype disclaimer.

---

## 5. Part 4: Agentic Pipeline, Formal MCP Server & Safety Guardrail Problems (`P26`–`P28`)

* **PROBLEM P26 (`FloodApp_Analysis.md` §6.1): Missing Formal Model Context Protocol (MCP) Server**  
  There is no MCP server exposing typed, schema-validated, idempotent tools (`search_satellite_scenes`, `run_flood_segmentation`, `run_urnn_nowcast`, `get_river_gauge_forecast`, `estimate_osm_impact`, `compute_dynamic_evacuation`, `draft_cap_alert`, etc.) with provenance hashes over JSON-RPC stdio and FastAPI `/api/mcp/*`.
* **PROBLEM P27 (`FloodApp_Analysis.md` §5 & §6.2): Procedural `FloodAgent` Instead of Multi-Agent LangGraph Supervisor with Progressive Escalation**  
  `FloodAgent.run_cycle` is a linear Python method with no multi-agent specialization (**Monitor, Crowd Intelligence, EO Analyst, Logistics, Reporter, Comms**), no SQLite state checkpointing, and no progressive escalation (`NONE → YELLOW → ORANGE → RED`).
* **PROBLEM P28 (`FloodApp_Analysis.md` §5.3, §6.2, §6.4): Missing HITL Approval Gate, Crowd Auto-Trigger, CAP v1.2 Export, Hallucination Validator & Chatbot Tool Calling**  
  - Outbound calls/alerts fire without a **Human-in-the-Loop (HITL) Approval Queue**.
  - Citizen complaints never auto-trigger an investigation when $\ge 3$ reports cluster within $2\text{km}$ in $12\text{h}$.
  - Alerts are not exported in **NDMA SACHET Common Alerting Protocol (CAP v1.2)** XML/JSON format.
  - Situation reports have no **Numeric-Claim Hallucination Validator** and cannot switch between **NDMA, UN-OCHA, SDMA, and Field Brief** templates.
  - `mireye_chatbot.py` uses prompt stuffing instead of native Gemini tool/function calling.

---

## 6. Part 5: Spatiotemporal 4D Hydrodynamic Nowcasting & Dynamic Routing Problems (`P29`–`P30`)

* **PROBLEM P29 (`urnn_integration_plan.md`): Missing U-RNN 3-Scale ConvGRU + YOLOX Dual-Head 4D Water-Depth Nowcaster**  
  SegFormer only produces a 2D binary water mask at $t=0$. It cannot build the 5-factor physical hydrological tensor (Instantaneous Rain, Cumulative Rain Volume, Real DEM, Imperviousness, Drainage Inlets) or run a 3-Scale ConvGRU Encoder-Decoder with a decoupled YOLOX Dual-Branch Head and Sliding-Window Pre-warming (SWP) to forecast continuous water depth $H(x,y,t)$ in meters at `Now (0m)`, `+15m`, `+30m`, and `+60m`.
* **PROBLEM P30 (`urnn_integration_plan.md`): Static Evacuation Router Ignores Rising Water Depth at Vehicle Arrival Time**  
  Standard Dijkstra checks road risk at departure time $t=0$. A road with $0.08\text{m}$ of water at $t=0$ may reach $0.55\text{m}$ by the time an evacuation vehicle arrives at $t=+25\text{m}$, stalling engines ($>0.30\text{m}$ impassable threshold) and trapping evacuees.

---

## 7. Part 6: User-Mandated Pipeline, New App Tab, Photo Upload, `+917678656930` Call & Multilingual Requirements (`P31`–`P35`)

* **PROBLEM P31 (User Requirement 1): U-RNN Must Be Integrated into the Satellite Analysis Pipeline with Live Console Logs & Panel 4**  
  When `/api/run-detection` runs, it must execute the coupled **16-Step Satellite + U-RNN Pipeline**, streaming progressive bilingual logs to `/api/status/{job_id}` every 1 second and mounting **Panel 4 (U-RNN 4D Water-Depth Scrubber)** directly inside `MapView.tsx`.
* **PROBLEM P32 (User Requirement 2): Dedicated New 6th App Tab `"4D Nowcast"` (`NowcastPanel.tsx`)**  
  The app needs a dedicated 6th bottom navigation tab (`"4D Nowcast"` / `"4D पूर्वानुमान"`) providing an interactive Hydrodynamic Command Studio with a 5-channel physical tensor inspector, `0m/+15m/+30m/+60m` depth scrubber, What-If Cloudburst simulator (`50 / 90 / 140 mm/hr`), and Static vs. Time-Varying route safety proof.
* **PROBLEM P33 (User Requirement 3): "Raise Query" (`ReportForm.tsx`) Photo Evidence Upload**  
  Citizens must be able to attach/capture a photo in `ReportForm.tsx`, preview the thumbnail, compress it client-side ($\le 150\text{KB}$), persist `image_b64` in SQLite (and the offline queue), and display the photo inside the Official Triage Dashboard and Map popups.
* **PROBLEM P34 (User Requirement 4): Hardcoded Demo Target `+917678656930` (`7678656930`) with Dynamic Hindi/English LLM Voice Call**  
  Because there are no external civilian users during the hackathon demo, outbound emergency voice calls must default to **`+917678656930` (`7678656930`)** and use an LLM (Gemini / Groq) to dynamically generate urgent **Hindi (`hi-IN`, `Polly.Aditi`)** and **English (`en-IN`, `alice`)** voice warning scripts citing live location, severity, U-RNN peak depth, and nearest shelter.
* **PROBLEM P35 (User Requirement 5): First-Launch Language Selection Modal & App-Wide Localization (`English` + `हिन्दी`)**  
  Before entering the workspace on first launch, the app must display a **Language Selection Modal** (`🇬🇧 English` / `🇮🇳 हिन्दी`), persist the choice in `AsyncStorage`, provide a persistent top-bar language toggle (`🇬🇧 EN | 🇮🇳 हिं`), and translate the entire app UI, forms, pipeline logs, chatbot, and TTS readouts.

---

## 8. Master 35-Problem Cross-Reference Index

See **[`solution_implementation_doc.md`](file:///c:/Users/SHAHZEB%20ALI/OneDrive/Desktop/mireye/Aegis/solution_implementation_doc.md)** for the complete file-by-file architectural blueprint and production code solving every single problem `P1` through `P35`.
