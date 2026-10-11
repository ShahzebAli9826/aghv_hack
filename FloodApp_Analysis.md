# FloodApp (Aegis) — Audit, Investigation & Improvement Plan

**Repository:** https://github.com/RajatRawal-06/FloodApp (Aegis workspace, verified against local codebase)
**Date:** 2026-10-10 (Updated post-verification against local implementation)
**Scope:** Full verification of backend (FastAPI/PyTorch), frontend (Expo/React Native), data models, agent modules, and actual codebase state.

---

## Table of contents

1. [Executive summary](#1-executive-summary)
2. [What the project is (as built)](#2-what-the-project-is-as-built)
3. [Documentation claims vs. what the code does](#3-documentation-claims-vs-what-the-code-does)
4. [Audit findings](#4-audit-findings)
   - 4.1 Security
   - 4.2 Data integrity and scientific validity
   - 4.3 Correctness bugs
   - 4.4 Architecture and code quality
   - 4.5 Legal, licensing and ethics
5. [The agentic side: current state](#5-the-agentic-side-current-state)
6. [Agentic redesign: target architecture](#6-agentic-redesign-target-architecture)
7. [New feature opportunities](#7-new-feature-opportunities)
8. [Engineering improvements](#8-engineering-improvements)
9. [Prioritized roadmap](#9-prioritized-roadmap)
10. [Appendices](#10-appendices)

---

## 1. Executive summary

**What it is.** Aegis (also branded Flux, FloodRescuer, Floor Rescuer and Anti Gravity in different files) is a flood response system. It has an Expo app with citizen and official dashboards, a Leaflet map, a chatbot, an "autonomous agent" console and a triage panel. Behind it sits a FastAPI backend that wraps a custom dual-encoder SegFormer (MiT-B2, SAR + optical fusion) trained on Sen1Floods11, connected to Sentinel Hub for Sentinel-1 GRD and Sentinel-2 L2A imagery, plus RAG, Twilio, SMTP, Expo push and a collection of "Aegis" hydrology and routing modules ported from a US-focused MirEye project.

**The verdict.** UI scope and ambition are strong, and the core ML architecture is real: the training code matches the inference code layer for layer, and weights are present. Sentinel Hub Process API is integrated for optical and SAR ingestion. However, **several critical security vulnerabilities remain unpatched**, the **"agentic" workflow is largely scripted**, and secondary hydrological/routing layers (TWI, evacuation path, triage data) rely on synthetic or US-county heuristics. Because this is a life-safety domain, resolving the remaining security vulnerabilities and upgrading to a truly autonomous, verified agent loop are the top priorities before real-world deployment.

### Top problems

| # | Problem | Why it matters |
|---|---|---|
| 1 | **No authentication or authorization on backend endpoints.** Voice calls, email, broadcast push, complaint resolution, agent cycles and triage overrides are open to anyone who can reach the server. CORS is `*` with credentials. | Anyone can trigger external calls, emails, push broadcasts, resolve complaints, or execute expensive agent cycles. |
| 2 | **TwiML injection plus unauthenticated outbound calls** ([endpoints.py:280-316](dell-flood-backend/app/api/endpoints.py#L280-L316)) and **stored XSS** from citizen reports rendered in the official map ([MapView.tsx:704-712](dell-flood-app/src/components/MapView.tsx#L704-L712)). | Risk of toll fraud on the Twilio account, harassment calls to arbitrary numbers, and script execution in the official dashboard context. |
| 3 | **Client-side authentication bypass.** If the backend is unreachable, login succeeds for known usernames with password `"123"` offline ([api.ts:207-208](dell-flood-app/src/services/api.ts#L207-L208)). The role is chosen client-side and saved in `localStorage`. | Anyone can gain official privileges by disconnecting network or spoofing local state. |
| 4 | **The "agent" is not agentic.** `FloodAgent` is a fixed procedural script, there is no autonomous scheduler, and the LLM only generates prose text. The Gemini chat path has no tool calling yet returns hard-coded citations. The LangGraph triage graph is defined in CLI but bypassed by the API. | The headline capability—autonomous agentic disaster response—remains largely scripted orchestration rather than adaptive reasoning. |
| 5 | **Synthetic secondary hydrology and US-centric data.** TWI is computed over a random Gaussian DEM seeded by coordinates; evacuation routing returns a sinusoidal curve; triage data uses a static 30-county US dataset with a hard-coded "Athens #1" calibration. | Misleading in an Indian disaster context (Bihar/Assam) and unsafe for actual navigation guidance. |

### Top opportunities

1. **Production-grade STAC & EO pipeline.** Supplement Sentinel Hub with automated STAC searching, JRC Global Surface Water permanent-water masks, and pre/post change detection.
2. **A real agent loop.** A persistent LangGraph state machine with a scheduler and event triggers, typed tools, an LLM planner inside guardrails, and human approval gates before any outbound alert.
3. **A multi-agent split** into Monitor, EO Analyst, Logistics, Comms (multilingual) and Reporter, with a shared typed incident state and an audit log.
4. **A crowd-intelligence agent** that verifies, deduplicates and clusters citizen reports (including photos), defends against prompt injection, and auto-triggers detection.
5. **Standards-based alerting.** Common Alerting Protocol (CAP) output (compatible with India's NDMA SACHET platform), geofenced push, and multilingual IVR/WhatsApp.

---

## 2. What the project is (as built)

### 2.1 Repository layout

```
Aegis/
├── best_model_focal.pth                             # Trained model weights (root)
├── us_counties_flood_predictions.json               # MirEye legacy county predictions
├── us_flood_polygons/*.json                         # 30 US county polygons (MirEye legacy)
├── dell-flood-backend/
│   ├── main.py                                      # FastAPI bootstrap (CORS *)
│   ├── app/api/endpoints.py                         # All routes + DB + Sentinel Hub ingestion + PDF
│   ├── app/ml/inference.py, postprocess.py          # SegFormer dual-encoder + strict weight loading
│   ├── app/agent/flood_agent.py, tools.py           # Procedural agent pipeline + weather/gauge tools
│   ├── app/agent/mireye_chatbot.py                  # Gemini / OpenAI+MirEye chatbot
│   ├── app/RAG/generator.py, vector_store.py        # ChromaDB + multi-LLM report writer
│   ├── app/aegis/**                                 # TWI, triage, routing, shelters (partly broken imports)
│   ├── corpus/*.txt                                 # RAG reference docs
│   ├── notebook_source.ipynb                        # Real Sen1Floods11 training code
│   └── test_backend.py, verify_endpoints.py, ...
└── dell-flood-app/
    ├── App.tsx                                      # Auth, both dashboards, tabs, styles
    ├── src/services/api.ts                          # API client + true backend error handling
    ├── src/components/MapView.tsx                   # Leaflet map + layer controls
    ├── src/components/{AgentPanel,ChatbotPanel,TriagePanel,ReportForm,ReportViewerModal,SettingsPanel}.tsx
    └── src/utils/routing.ts                         # 8-node toy Dijkstra graph (unused)
```

### 2.2 Runtime data flow (actual)

```
Expo app (web / Expo Go)
  │  fetch() — no auth header, timeout handling with explicit error messages
  ▼
FastAPI (single process, in-memory state: jobs{}, AGENT_TRACES{}, _ACTIVE_TRIAGE_SESSIONS{})
  ├─ /run-detection → BackgroundTask:
  │     Copernicus Sentinel Hub API (Sentinel-2 L2A: B04, B03, B02, B08 NIR)
  │     Copernicus Sentinel Hub API (Sentinel-1 GRD: VV, VH dB)
  │     SegFormer MiT-B2 Dual Encoder (strict=True, trained weights)
  │     Historical Sentinel-2 permanent water baseline filter (self.ndwi_threshold = 0.35)
  │     Open-Meteo DEM elevation verification & connected-component filter
  │     Area calculation & quadrant bounding box GeoJSON
  ├─ /agent-cycle → FloodAgent.run_cycle (procedural script) → Sentinel Hub + SegFormer → Gemini prose → PDF → SMTP
  ├─ /chat/message → Gemini single-shot prompt (no tools)  |  OpenAI gpt-4o + MirEye tools (fallback)
  ├─ /aegis/twi/predict → TWI over a random Gaussian DEM seeded by lat/lon
  ├─ /aegis/evacuation/plan → sinusoidal path interpolation between origin and nearest shelter
  ├─ /aegis/triage/run|override → hard-coded US county clusters ("Athens County calibration")
  └─ SQLite flood_database.db (users, complaints, shelters) — new connection per call
```

### 2.3 Tech stack

| Layer | In use | Declared but unused or missing |
|---|---|---|
| Mobile/web | Expo 57, RN 0.86, React 19, Leaflet 1.7 (inside iframe/WebView), lucide icons, AsyncStorage, expo-notifications, expo-location | `@tanstack/react-query`, `@react-navigation/*`, `react-native-screens`, `expo-file-system` (unused). `@rnmapbox/maps`, SQLite/WatermelonDB, NetInfo and image-manipulator are claimed in docs but absent. |
| Backend | FastAPI, NumPy, OpenCV, Pillow, PyTorch + `transformers`, ChromaDB, ReportLab, requests, Twilio, LangGraph (triage CLI) | **Missing from `requirements.txt`:** `openai` (imported at module load in `mireye_chatbot.py`), `scipy`, `scikit-learn`, `networkx`, `folium`, `httpx`, `Pillow`. **Listed but unused:** `onnxruntime`, `geopandas`, `shapely`, `pysheds`, `rasterio`, `langchain`, `sendgrid`, `sentence-transformers`. |
| AI/LLM | Gemini (REST), Groq Llama 3.3, OpenAI gpt-4o / gpt-4o-mini, Anthropic `claude-3-haiku-20240307` | No structured outputs, no function calling on primary (Gemini) path, no evals or tracing. |
| ML | Custom DualFloodSegFormer (2× MiT-B2, gated + cross-attention fusion, FPN, boundary refinement); trained on Sen1Floods11 | Weights present in workspace root (`best_model_focal.pth`); loaded with `strict=True` and Transformers 5.x tensor remapping. |

---

## 3. Documentation claims vs. what the code does

`features.md`, `final_implementation_doc.md`, `detailed_feature_design.md` and the README read as specifications written in the past tense. The table below evaluates each major claim against the verified codebase.

| Claim (docs) | Reality (code) | Evidence |
|---|---|---|
| ECC image alignment | A status message is appended; no actual alignment runs | [endpoints.py](dell-flood-backend/app/api/endpoints.py) |
| Cloud-aware SAR weighting via S2 QA band | Optical tensor is multiplied by `1 - cloud×0.4` using current Open-Meteo cloud cover (not satellite image cloud mask) | [inference.py:462-464](dell-flood-backend/app/ml/inference.py#L462-L464) |
| SRTM DEM + PySheds downstream warnings | 3×3 Open-Meteo elevation samples, bicubic-upsampled; no flow routing; `downhill_warnings` never produced | [postprocess.py:31-58](dell-flood-backend/app/ml/postprocess.py#L31-L58) |
| OSM Overpass + MS Building Footprints + WorldPop impact | `population = area × 1150`, `buildings = area × 40`, `facilities = area × 0.4 + 1` | [endpoints.py:1345-1347](dell-flood-backend/app/api/endpoints.py#L1345-L1347) |
| Flood spread 24/48 h polygons | Not implemented | — |
| Optical-only vs fusion toggle | Not implemented (model runs once in fusion mode) | — |
| Historical comparison / before-after slider | `dateFactor` scales mask visibility 1.0/0.5/0.0 by date label | [MapView.tsx](dell-flood-app/src/components/MapView.tsx) |
| GeoTIFF expert upload | File content ignored; always returns a Patna detection with fixed bounds | [endpoints.py:1136-1147](dell-flood-backend/app/api/endpoints.py#L1136-L1147) |
| CWC river gauge monitoring | Gauge level is a deterministic function of rainfall; no live CWC API call | [tools.py:193-214](dell-flood-backend/app/agent/tools.py#L193-L214) |
| FloodAgent: LangGraph, runs every 6 h, memory, dedup | Plain Python class; runs only on HTTP request; memory is an in-process dict lost on restart | [flood_agent.py](dell-flood-backend/app/agent/flood_agent.py) |
| Progressive Yellow → Orange → Red escalation | Not implemented; severity is recomputed each call | — |
| Crowdsource auto-trigger (3 reports / 2 km / 12 h) | Not implemented | — |
| Complaint score = 60 % user severity + 40 % model confidence | Score = severity bucket + `hash(lat, lon, ts) % 6`; "model_confirmed" = rain ≥ 35 mm or user said SEVERE/HIGH | [endpoints.py](dell-flood-backend/app/api/endpoints.py) |
| Offline complaint queue (SQLite, photo ≤150 KB, auto-sync) | Report is pushed to an in-memory JS array; lost on reload; never retried; no photo capture exists | [api.ts:279-296](dell-flood-app/src/services/api.ts#L279-L296) |
| Offline Dijkstra routing on device | 8-node hand-written graph (Patna/Muzaffarpur) and **never imported** | [routing.ts](dell-flood-app/src/utils/routing.ts) |
| Elevation-weighted NetworkX evacuation routing | API returns a sine-wave interpolation labelled `"ELEVATION_WEIGHTED_NETWORKX"`; shelter elevation = `15 + distance × 4.2` | [endpoints.py](dell-flood-backend/app/api/endpoints.py) |
| Predictive TWI hydrology | TWI computed on a random Gaussian-smoothed DEM seeded from the coordinates | [predictive_twi.py:80-98](dell-flood-backend/app/aegis/pipeline/predictive_twi.py#L80-L98) |
| LangGraph human-in-the-loop triage | Graph compiled only in CLI runner; API calls node functions directly; data is static US county list | [triage_engine.py](dell-flood-backend/app/aegis/pipeline/triage_engine.py) |
| RAG on NDMA / UN-OCHA / SDMA reports | 2 synthetic 6-line documents | [corpus/](dell-flood-backend/corpus) |
| Hallucination prevention: number validator + regeneration | Not implemented (prompt says "do not make up numbers") | [generator.py](dell-flood-backend/app/RAG/generator.py) |
| Chatbot "Gemini 2.5 Flash × MirEye Earth API" with citations | Gemini path = single prompt, **no tools**, returns hard-coded citations. MirEye is reachable only via OpenAI fallback | [mireye_chatbot.py:393-416](dell-flood-backend/app/agent/mireye_chatbot.py#L393-L416) |
| JWT + bcrypt auth | Unsalted SHA-256; "JWT" = base64 JSON + `sha256(payload + "SECRET_KEY_123")`; never verified | [endpoints.py:219-231](dell-flood-backend/app/api/endpoints.py#L219-L231) |
| README project tree (`Mireye/`, `decision_engine/`, `run_aegis_master.py`) | None of these exist; `main.py` is the FastAPI server | [README.md](README.md) |

**What is genuinely real and working:**
- **Sentinel Hub EO Ingestion:** Real Copernicus Sentinel-2 L2A (B04, B03, B02, B08 NIR) and Sentinel-1 GRD (VV/VH dB) acquisition via Sentinel Hub Process API.
- **Historical Water Baseline:** Multi-month historical Sentinel-2 L2A observation sampling via `download_permanent_water_baseline`.
- **Trained Dual-Encoder Model:** SegFormer fusion architecture and trained weights (`best_model_focal.pth`), strictly validated at load time (`strict=True`) with tensor remappings for Transformers 5.x. Refuses execution on mock.
- **Honest Client Error Propagation:** The frontend API service throws explicit HTTP and timeout errors on failure rather than producing simulated detections or agent cycles.
- **Weather & Geocoding Telemetry:** Real Open-Meteo rainfall, elevation, and Nominatim geocoding.
- **Twilio SMS/voice & SMTP Delivery:** Working external communications integration with recipient addresses loaded from environment variables.
- **ChromaDB Plumbing & ReportLab PDFs:** Functional PDF report generation and vector storage.
- **Triage Allocator:** The capacity-constrained shelter allocation algorithm in `node_allocate_shelters`.

---

## 4. Audit findings

Severity scale: **Critical** (exploitable or life-safety now), **High**, **Medium**, **Low**.

### 4.1 Security

| Sev | Finding | Location | Fix |
|---|---|---|---|
| **Critical** | **No authentication or authorization on any endpoint.** Voice calls, email, broadcast push, complaint resolution, agent cycles and triage overrides are open to anyone who can reach the server. CORS is `*` with credentials. | [main.py:26-32](dell-flood-backend/main.py#L26-L32), all of [endpoints.py](dell-flood-backend/app/api/endpoints.py) | OAuth2 password flow with real JWT (PyJWT, server-side secret from env, expiry, verification) as a FastAPI dependency; role-based dependencies (`require_official`); restrict CORS origins. |
| **Critical** | **TwiML injection and toll fraud.** `/alerts/voice` interpolates the caller-supplied `message` raw into TwiML XML and dials any caller-supplied number. Payload `</Say><Dial>+<premium number></Dial><Say>` makes the account call premium numbers. | [endpoints.py:280-316](dell-flood-backend/app/api/endpoints.py#L280-L316), [tools.py:60-64](dell-flood-backend/app/agent/tools.py#L60-L64) | Build TwiML with `twilio.twiml.voice_response.VoiceResponse().say(text)`; allowlist destination numbers; rate limit; require official role plus approval. |
| **Critical** | **Stored XSS / script injection in the official map.** Unauthenticated `/report-flood` stores `description`. The map HTML embeds `JSON.stringify(complaints)` inside `<script>` and renders `c.description` as tooltip HTML. On web the `srcDoc` iframe is same-origin with the app, so it can read and modify `localStorage` (role) and act as official. | [MapView.tsx](dell-flood-app/src/components/MapView.tsx) | Escape HTML before `bindTooltip`; serialize data safely; use `postMessage` rather than string-templating HTML documents; validate server-side. |
| **Critical** | **Client-side authentication bypass.** If the backend is unreachable, login succeeds for known usernames with password `"123"` (`password === "123"` short-circuits). The role is chosen client-side and saved in `localStorage`. | [api.ts:207-208](dell-flood-app/src/services/api.ts#L207-L208) | Remove offline auth bypass; server decides role from verified token; store token in `expo-secure-store`. |
| High | **Default seeded accounts** (`saif`, `shah`, `saif_official`, password `123`) created on fresh DB. Passwords hashed with unsalted SHA-256. | [endpoints.py:85-91](dell-flood-backend/app/api/endpoints.py#L85-L91) | Remove seeds (or gate behind `DEMO_MODE`); use argon2/bcrypt (`passlib`/`argon2-cffi`). |
| High | **Hard-coded fallback phone number.** The developer's phone `+917678656930` is hardcoded as default destination for voice calls and in mock complaint reports. (Note: Email recipient was fixed to read from `.env`). | [endpoints.py:283](dell-flood-backend/app/api/endpoints.py#L283), [api.ts:291](dell-flood-app/src/services/api.ts#L291) | Require recipient phone explicitly in payload; pull from database or config; remove hardcoded personal numbers. |
| High | **Path traversal and disk exhaustion in PDF generation.** `location` flows unsanitized into `./reports/report_{location}_{ts}.pdf` with `os.makedirs`. A GET request writes a new file each call without cleanup. | [endpoints.py:918-928](dell-flood-backend/app/api/endpoints.py#L918-L928) | Slugify (`[a-z0-9_-]`), generate in memory (`BytesIO` → `StreamingResponse`) or temp dir with TTL cleanup; require auth. |
| High | **Unbounded in-memory state.** `jobs{}` keeps base64 PNGs per detection forever; `AGENT_TRACES` and `_ACTIVE_TRIAGE_SESSIONS` grow without limit. Memory-exhaustion DoS via unauthenticated endpoints. | [endpoints.py](dell-flood-backend/app/api/endpoints.py), [flood_agent.py:23](dell-flood-backend/app/agent/flood_agent.py#L23) | Job store with TTL (Redis/DB); images in object storage referenced by URL. |
| High | **Cross-user log leak.** `FloodAgent` is a module-level singleton whose `activity_log` is never cleared. Every `/agent-cycle` response returns the logs of all previous runs. Concurrent requests interleave. | [flood_agent.py:20-32](dell-flood-backend/app/agent/flood_agent.py#L20-L32) | Create log per run (run-scoped object); persist runs keyed by `run_id` and owner. |
| Medium | **Prompt injection surface.** User chat text and conversation history are concatenated into a single prompt string with system instructions. | [endpoints.py](dell-flood-backend/app/api/endpoints.py), [mireye_chatbot.py:395-405](dell-flood-backend/app/agent/mireye_chatbot.py#L395-L405) | Use proper system/user message roles; treat user text as quoted data. |
| Medium | Gemini API key sent as a URL query parameter (`?key=`), so it appears in proxy logs and tracebacks. | [generator.py:58](dell-flood-backend/app/RAG/generator.py#L58) | Use `x-goog-api-key` header or official SDK. |
| Medium | Cleartext HTTP configured (`usesCleartextTraffic: true`), backend bound to `0.0.0.0`. | [app.json](dell-flood-app/app.json) | Enforce HTTPS; use environment variables for API URL. |
| Medium | `postMessage(..., '*')` between map iframe and app with no origin or type validation. | [MapView.tsx](dell-flood-app/src/components/MapView.tsx) | Check `event.origin`; validate message schema. |
| Low | Geocode "slang filter" uses substring matching on short tokens (`"mc"`, `"bc"`, `"kutta"`). Blocks legitimate places like **Kuttanad** and **McLeod Ganj**. | [endpoints.py:1799-1801](dell-flood-backend/app/api/endpoints.py#L1799-L1801) | Remove it, or use whole-word boundary matching with dedicated moderation. |

---

### 4.2 Data integrity and scientific validity

1. **The area constant is inconsistent.** At z14 a pixel is ~74 m² at Patna. The code uses 0.000019 km² (19 m²) per pixel in postprocessing ([postprocess.py:123](dell-flood-backend/app/ml/postprocess.py#L123)), a ~4× underestimate, while `FloodAgent` uses 0.0001 km² (100 m²) per pixel ([flood_agent.py:165](dell-flood-backend/app/agent/flood_agent.py#L165)).
2. **"Confidence" metric represents average image probability.** In `endpoints.py`, confidence is computed as `mean(prob_map)` over the entire 512×512 image (including dry pixels), and then clamped to 68–70% whenever flood is detected.
3. **The agent overrides model severity with synthetic gauge levels.** Even though pixel inundation is accurately measured, if the rainfall-estimated gauge status says `DANGER`, severity is forced to `CRITICAL` regardless of satellite inundation extent ([flood_agent.py:178](dell-flood-backend/app/agent/flood_agent.py#L178)).
4. **"5-day rainfall" has dual definitions.** With OpenWeather it represents the *next* 5 days of forecast; with Open-Meteo it represents the *past* 5 days of observations ([tools.py:153-190](dell-flood-backend/app/agent/tools.py#L153-L190)). The same thresholds are applied to both.
5. **Synthetic layers presented as real analysis:**
   - TWI calculated on a random Gaussian DEM seeded by coordinates.
   - Building clusters seeded by `np.random.seed(42)` ([cluster.py:67-82](dell-flood-backend/app/aegis/pipeline/cluster.py#L67-L82)).
   - Triage populations generated by `90 + (idx*13) % 110` with Athens hand-tuned to score 197.3.
   - Shelter elevations computed from distance.
   - Evacuation path generated by sinusoidal interpolation.
6. **Generated PDFs impersonate official government bulletins.** Headed "RESTRICTED / EMERGENCY RESPONSE ONLY" and signed "Director of Operations, State Disaster Management Agency (SDMA)" with static narrative ("NDRF units have been mobilized", "August 2026") and generic shelters ([endpoints.py:461-726](dell-flood-backend/app/api/endpoints.py#L461-L726)).

---

### 4.3 Correctness bugs

| Sev | Bug | Location | Status |
|---|---|---|---|
| High | **Backend fails on fresh install without extra dependencies.** `from openai import OpenAI` at import time in `mireye_chatbot.py` raises `ModuleNotFoundError` if `openai` is not installed. `scipy`, `scikit-learn`, `networkx`, `folium`, `httpx` and `Pillow` are also omitted from `requirements.txt`. (`transformers` is present). | [mireye_chatbot.py:16](dell-flood-backend/app/agent/mireye_chatbot.py#L16), [requirements.txt](dell-flood-backend/requirements.txt) | **Confirmed present** |
| High | **Push broadcast never sends.** `send_expo_push_notification(tok, title, body, data=...)` is called with a `data` kwarg that the function signature does not accept. Swallowed per token; returns "dispatched to 0 users". | [endpoints.py:958](dell-flood-backend/app/api/endpoints.py#L958) vs [endpoints.py:196](dell-flood-backend/app/api/endpoints.py#L196) | **Confirmed present** |
| High | **Agent evacuation step always fails.** `compute_elevation_evacuation_route` does not exist in `evacuation_engine.py`. Exception is caught and logged as `[WARN]`. | [flood_agent.py:220](dell-flood-backend/app/agent/flood_agent.py#L220) | **Confirmed present** |
| Medium | **Broken imports in Aegis modules.** `extractor.py` imports `make_batch_cache_key`, `polygon_hash`, `DISASTER_PRESETS`, `FloodDossier`, `PointDossier`, etc., none of which exist. `evacuate.py` imports `polygon_hash`. `cluster.py` accesses `polygon.name` (field is `place`). | [extractor.py:21-29](dell-flood-backend/app/aegis/pipeline/extractor.py#L21-L29), [cluster.py:94](dell-flood-backend/app/aegis/pipeline/cluster.py#L94) | **Confirmed present** |
| Medium | **Triage audit log is always empty in API responses.** `node_allocate_shelters` returns a dictionary without `override_logs` or `overrides`. | [triage_engine.py:364-369](dell-flood-backend/app/aegis/pipeline/triage_engine.py#L364-L369) | **Confirmed present** |
| Medium | **`FORCE_PRIORITY` override is a no-op via the API**: only applied in `node_compute_triage`, which the override endpoint does not re-run. `ROAD_CLOSED` only logs a message. | [triage_engine.py:235-240](dell-flood-backend/app/aegis/pipeline/triage_engine.py#L235-L240), [endpoints.py:2205-2206](dell-flood-backend/app/api/endpoints.py#L2205-L2206) | **Confirmed present** |
| Medium | **New corpus documents are never indexed.** Ingestion is skipped whenever the Chroma collection is non-empty. | [vector_store.py:99-103](dell-flood-backend/app/RAG/vector_store.py#L99-L103) | **Confirmed present** |
| Medium | **Two full SegFormer instances loaded.** Instantiated separately in `endpoints.py` and `FloodAgent`, doubling model RAM usage. | [endpoints.py:238](dell-flood-backend/app/api/endpoints.py#L238), [flood_agent.py:36](dell-flood-backend/app/agent/flood_agent.py#L36) | **Confirmed present** |
| Medium | **Broadcast ignores configured server URL.** Uses `DEFAULT_API_URL` instead of `this.apiUrl`. | [api.ts:561](dell-flood-app/src/services/api.ts#L561) | **Confirmed present** |
| Low | **Non-existent and retired model names in fallbacks.** `gemini-3.8-flash` in fallback lists; retired `claude-3-haiku-20240307`. | [endpoints.py:942](dell-flood-backend/app/api/endpoints.py#L942), [generator.py:119](dell-flood-backend/app/RAG/generator.py#L119) | **Confirmed present** |
| Low | `/upload-geotiff` reads upload into memory, then ignores it and returns fixed Patna coordinates. | [endpoints.py:1136-1147](dell-flood-backend/app/api/endpoints.py#L1136-L1147) | **Confirmed present** |
| Low | Hard-coded Windows development paths for weights (`c:\Users\rawal\Desktop\...`). | [inference.py:345](dell-flood-backend/app/ml/inference.py#L345) | **Confirmed present** |

---

### 4.4 Architecture and code quality

- **God files.** `endpoints.py` (~2,250 lines) mixes DB schemas, auth, email, push, Twilio, PDF generation, Sentinel Hub calls, ML pipeline, chat and triage. `App.tsx` (~3,670 lines) holds auth, both dashboards, and navigation. `MapView.tsx` builds an HTML document via string concatenation.
- **Direct SQLite connections.** Routes call `sqlite3.connect` directly with a new connection per request.
- **In-process heavy execution.** Model inference runs in FastAPI `BackgroundTasks` rather than dedicated worker queues (Celery/RQ).
- **Polling overhead.** Client polls `/status/{job_id}` frequently, returning base64 imagery payloads repeatedly.
- **Logging is standard `print()`.** Absence of structured JSON logging, request IDs, and distributed tracing.
- **Geographic mismatch.** Product addresses India (Bihar/Assam), yet triage, TWI, and MirEye layers use US county datasets.
- **Unused dependencies.** Several packages (`onnxruntime`, `geopandas`, `shapely`, `pysheds`, `rasterio`) are listed in `requirements.txt` but not utilized in runtime workflows.

---

### 4.5 Legal, licensing and ethics

- **Deliberately suppressed map attribution.** `.leaflet-control-attribution { display: none; }` in [MapView.tsx](dell-flood-app/src/components/MapView.tsx). OSM, Carto, and Esri licenses require visible attribution.
- **Nominatim usage policy.** Max 1 request/second with contact User-Agent; client triggers geocoding requests without rate throttling.
- **Impersonation risk.** Generated PDF reports represent themselves as official SDMA/NDMA bulletins signed by government directors.
- **Personal data retention.** Citizen locations and reports stored without formal data retention, encryption at rest, or privacy policies.

---

## 5. The agentic side: current state

| Component | Claimed | Actual behavior | Agentic? |
|---|---|---|---|
| `FloodAgent.run_cycle` | LangGraph autonomous Perceive→Plan→Act→Reflect loop every 6 h | Procedural Python function triggered only by `POST /agent-cycle`. Steps run sequentially; LLM generates report text. Memory is in-process dict on singleton. | **No** (scripted pipeline) |
| `/agent/chat` (FloodRescuer) | RAG chatbot | One-shot prompt with telemetry + 2 Chroma chunks. Gemini → Groq fallback. | No (single prompt) |
| `/chat/message` (MirEye chatbot) | Gemini 2.5 Flash + MirEye tools | Gemini path is single prompt without tools. OpenAI fallback has a real tool loop over 3 US-only MirEye tools. | Partially (OpenAI fallback only) |
| Triage (`triage_engine.py`) | LangGraph StateGraph + MemorySaver + HITL interrupt | LangGraph defined in CLI; API calls node functions directly in memory. No LLM decision-making. | Workflow, not agent |
| Report generator | RAG + hallucination validator | Single prompt with retrieved chunk; no numeric validator. | No |
| Notifications/voice | LLM-written alert text | Gemini generates alert copy; dispatched without mandatory human-in-the-loop sign-off. | Automated LLM without human gate |

---

## 6. Agentic redesign: target architecture

Design principle: **deterministic, verifiable tools do the science; LLM agents handle orchestration, triage, explanation and communication; humans approve anything reaching the public.**

```
                ┌────────────────────────── Triggers ──────────────────────────┐
                │ cron (per watch-region)   gauge/forecast threshold   crowd    │
                │ cluster (≥3 reports/2km/12h)   new S1 pass available   manual │
                └───────────────┬───────────────────────────────────────────────┘
                                ▼
                    ┌───────────────────────┐   persistent checkpointer (Postgres)
                    │  Incident Orchestrator │◄──── IncidentState (typed, versioned)
                    │  (LangGraph supervisor)│      escalation_level, evidence[], provenance
                    └──┬─────┬─────┬─────┬───┘
         ┌─────────────┘     │     │     └──────────────┐
         ▼                   ▼     ▼                    ▼
  ┌─────────────┐   ┌────────────┐ ┌──────────────┐ ┌──────────────┐
  │ Monitor     │   │ EO Analyst │ │ Logistics    │ │ Comms        │
  │ agent       │   │ agent      │ │ agent        │ │ agent        │
  │ rain, gauge,│   │ S1/S2 STAC │ │ shelters,    │ │ CAP, SMS,    │
  │ forecasts   │   │ search,    │ │ capacity,    │ │ push, IVR,   │
  │ (GloFAS,IMD)│   │ SegFormer, │ │ routing w/   │ │ WhatsApp,    │
  │             │   │ impact     │ │ flood avoid  │ │ multilingual │
  └─────────────┘   └────────────┘ └──────────────┘ └──────┬───────┘
         ▲                 ▲              ▲                │ interrupt()
         │                 │              │                ▼
  ┌──────┴─────────────────┴──────────────┴───┐   ┌─────────────────┐
  │ Crowd Intelligence agent (citizen reports, │   │ Official approval│
  │ photos, dedupe, verify, cluster, reply)   │   │ queue (HITL)     │
  └───────────────────────────────────────────┘   └─────────────────┘
                                ▼
                     Reporter agent → SITREP (structured JSON → template → PDF/CAP)
                     with numeric-claim validator + citations
```

### 6.1 Tool layer (MCP-enabled)

Expose tools as typed, idempotent functions with Pydantic schemas and provenance metadata, both in-process and via an **MCP server**:

| Tool | Real data source | Side effects |
|---|---|---|
| `geocode(query)` | Nominatim (cached, rate-limited) / Photon | None |
| `get_rainfall(lat, lon, window)` | Open-Meteo / IMD gridded products | None |
| `get_river_forecast(lat, lon)` | GloFAS discharge forecasts / Google Flood Hub API / CWC | None |
| `search_sar_scenes(bbox, since)` | Copernicus Data Space Ecosystem STAC / Microsoft Planetary Computer | None |
| `run_flood_segmentation(lat, lon)` | SegFormer on Sentinel-1 + Sentinel-2 via Sentinel Hub / STAC | GPU job |
| `estimate_impact(flood_geojson)` | WorldPop raster, OSM Overpass, Open Buildings | None |
| `find_shelters(bbox)` | Official SDMA lists, OSM `amenity=shelter` | None |
| `route(origin, dest, avoid_polygons)` | OSRM / Valhalla with live flood avoid polygons | None |
| `allocate_shelters(clusters, shelters)` | Capacity-constrained allocator | Writes draft plan |
| `draft_alert(incident, language)` | LLM structured output (CAP format) | None (draft) |
| `send_alert(draft_id)` | Twilio / Expo push / CAP feed / SMTP | **Requires official approval token** |
| `generate_sitrep(incident_id)` | Structured JSON → template → PDF | Generates document |

---

## 7. Prioritized roadmap

### Phase 0: Security & Critical Bug Fixes (Immediate)

| Task | Addresses |
|---|---|
| Add auth dependency (JWT + RBAC) to all mutating and dispatch endpoints; restrict CORS | §4.1 Critical |
| Sanitize TwiML input with `twilio.twiml.voice_response.VoiceResponse().say()`; restrict outbound dialing | §4.1 Critical |
| Escape complaint descriptions in map view; prevent script injection | §4.1 Critical |
| Remove client-side offline login bypass (`password === "123"`) | §4.1 Critical |
| Fix push broadcast function signature to accept `data` parameter | §4.3 High |
| Add missing Python dependencies to `requirements.txt` (`openai`, `scipy`, `networkx`, `httpx`, `Pillow`) | §4.3 High |
| Implement or stub `compute_elevation_evacuation_route` in `evacuation_engine.py` | §4.3 High |
| Restore visible attribution controls on Leaflet map | §4.5 |
| Add "Prototype Output — For Testing Only" disclaimer headers to generated PDFs | §4.2 |

### Phase 1: Robust Foundations (3–4 weeks)

- Backend modularization: routers, services, Alembic migrations, Postgres/PostGIS.
- Job queue (Celery/Redis) with WebSocket/SSE progress updates for long-running inferences.
- Real flood-aware routing via OSRM/Valhalla with dynamic avoid polygons.
- Formal MCP server exposing detection, telemetry, and shelter tools.
- Pytest suite for postprocessing math, allocation algorithms, and endpoint contracts.

### Phase 2: Agentic Core & Standards (4–6 weeks)

- Incident Orchestrator with persistent LangGraph checkpointer and escalation state machine.
- Human-in-the-loop approval dashboard for all outbound notifications and SITREPs.
- Crowd intelligence agent with deduplication, clustering triggers, and injection safety.
- Common Alerting Protocol (CAP) feed export compatible with NDMA SACHET.
- Official Copilot with unified tool-calling over incident state.

---

## 8. Appendices

### A. Endpoint inventory & current verification

| Method & path | Verified behavior | Security / Integrity Status |
|---|---|---|
| `POST /api/auth/register` | Inserts user with SHA-256 password; permits any role including `official` | Open self-registration |
| `POST /api/auth/login` | Returns unverified base64 SHA-256 JWT | Weak auth |
| `POST /api/alerts/voice` | Twilio call with caller-supplied TwiML | **Critical injection risk** |
| `POST /api/alerts/email` | Sends email to recipient configured in `.env` | Requires official role |
| `POST /api/alerts/email-report` | Generates LLM brief and emails configured recipient | Unauthenticated compute |
| `POST /api/notifications/broadcast` | Attempts push to all tokens (fails due to kwarg mismatch) | Buggy / Unauthenticated |
| `GET /api/preview` | Real Sentinel Hub preview (Sentinel-2 L2A & Sentinel-1 GRD) | Functional |
| `POST /api/run-detection` | Real Sentinel Hub ingestion + SegFormer inference (strict weights) | In-memory jobs store |
| `POST /api/report-flood` | Stores citizen complaint without sanitization | Stored XSS surface |
| `GET /api/complaints/list` | Returns all complaints | Unauthenticated data exposure |
| `POST /api/complaints/resolve` | Resolves complaint by ID | Unauthenticated mutation |
| `POST /api/agent-cycle` | Runs procedural pipeline via Sentinel Hub + SegFormer + Gemini | In-memory log growth |
| `POST /api/agent/chat` | Single-shot prompt RAG chatbot | Functional |
| `POST /api/aegis/twi/predict` | TWI on coordinate-seeded random DEM | Synthetic layer |
| `POST /api/aegis/evacuation/plan` | Sinusoidal path interpolation | Synthetic routing |
| `POST /api/aegis/triage/run` | Allocates static US county dataset | Geographic mismatch |

### B. Remaining quick wins (under 1 hour each)

1. Add `data: dict | None = None` parameter to `send_expo_push_notification` in `endpoints.py`.
2. Add `openai`, `scipy`, `scikit-learn`, `networkx`, `folium`, `httpx`, and `Pillow` to `requirements.txt`.
3. In `dell-flood-app/src/services/api.ts:561`, replace `DEFAULT_API_URL` with `this.apiUrl`.
4. In `dell-flood-backend/app/aegis/pipeline/triage_engine.py`, return `"override_logs": state.get("override_logs", [])` in `node_allocate_shelters`.
5. Remove `password === "123"` offline auth bypass from `api.ts:207-208`.
6. Enable Leaflet attribution in `MapView.tsx` by removing `.leaflet-control-attribution { display: none; }`.
7. Remove non-existent model `gemini-3.8-flash` from fallback lists.
8. Delete the substring slang filter in `/geocode`.
