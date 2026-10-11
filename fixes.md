# AEGIS Master Fixes & Implementation Specification
## Complete Engineering, Security, Scientific & Agentic Remediation Plan

> **Authoritative Sources Unified in this Document:**
> 1. **`FloodApp_Analysis.md`** (Comprehensive Code Audit: Security Vulnerabilities, Correctness Bugs, Scientific Integrity, Agentic Redesign)
> 2. **`map_implementation.md`** (Live Sentinel Hub Detection Pipeline, Progressive 1s Status Polling, Zero-Hardcoding Impact Joins)
> 3. **`urnn_integration_plan.md`** (Journal of Hydrology 2025: U-RNN 4D Spatiotemporal Water-Depth Nowcasting & Time-Varying Evacuation)
> 
> **Target System:** Aegis (AI-Powered Multimodal Satellite Flood Detection & Autonomous Disaster Response System)  
> **Date:** October 2026

---

## Table of Contents
1. [Executive Summary & Full Fix Inventory](#1-executive-summary--full-fix-inventory)
2. [Section 1: Security Hardening & Vulnerability Remediation](#2-section-1-security-hardening--vulnerability-remediation)
3. [Section 2: High-Priority Correctness Bugs & Code Stability](#3-section-2-high-priority-correctness-bugs--code-stability)
4. [Section 3: Scientific Validity & Data Integrity Corrections](#4-section-3-scientific-validity--data-integrity-corrections)
5. [Section 4: Live Satellite Detection Pipeline Implementation](#5-section-4-live-satellite-detection-pipeline-implementation)
6. [Section 5: U-RNN 4D Spatiotemporal Water-Depth Nowcasting](#6-section-5-u-rnn-4d-spatiotemporal-water-depth-nowcasting)
7. [Section 6: Agentic Redesign & Human-in-the-Loop Architecture](#7-section-6-agentic-redesign--human-in-the-loop-architecture)
8. [Section 7: Immediate "Quick Wins" Execution Checklist (<1 Hour Each)](#8-section-7-immediate-quick-wins-execution-checklist-1-hour-each)
9. [Section 8: Verification & End-to-End Test Suite](#9-section-8-verification--end-to-end-test-suite)

---

## 1. Executive Summary & Full Fix Inventory

The audit of Aegis across `FloodApp_Analysis.md`, `map_implementation.md`, and `urnn_integration_plan.md` revealed that while the core computer vision SegFormer model is authentic and trained on Sen1Floods11, the codebase suffered from:
- **Severe security vulnerabilities** (unauthenticated telephony/email endpoints, TwiML injection, stored XSS, offline authentication bypass).
- **Runtime crashes on clean install** (unlisted dependencies like `openai`, `scipy`, `networkx`, `Pillow`, `httpx`).
- **Broken pipeline connections** (push notification kwarg mismatch, missing `compute_elevation_evacuation_route`, dead Aegis imports).
- **Synthetic heuristics & hardcoding** (arbitrary quadrant bounding boxes, fixed area multipliers `pop = area * 1150`, fake hash-based complaint scoring, synthetic sinusoidal routes).
- **A scripted agent masquerading as an autonomous LLM loop** without human-in-the-loop safety gates.
- **Static single-snapshot blindness** that detects where water was, but cannot predict continuous water depth $H(x, y, t)$ or future submersion along evacuation routes.

This document provides the exact code, architecture, and configuration to resolve **every single finding**.

---

## 2. Section 1: Security Hardening & Vulnerability Remediation

### 1.1 Backend Authentication & Role-Based Access Control (RBAC)
* **Finding (`FloodApp_Analysis.md` §4.1 Critical):** Endpoints `/alerts/voice`, `/alerts/email`, `/alerts/email-report`, `/notifications/broadcast`, `/complaints/resolve`, and `/agent-cycle` have zero authentication. CORS is wildcard `*` with credentials enabled.
* **Fix:** Implement real OAuth2 Password Bearer flow with cryptographically verified RS256/HS256 JWT tokens via `python-jose` / `PyJWT`, enforcing `require_user` and `require_official` FastAPI dependencies.
```python
# dell-flood-backend/app/api/auth_deps.py
import os
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY or SECRET_KEY == "SECRET_KEY_123":
    raise RuntimeError("CRITICAL: Production JWT_SECRET_KEY must be set in environment variables!")

ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

class TokenData(BaseModel):
    username: str
    role: str

def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub") or payload.get("username")
        role: str = payload.get("role")
        if username is None or role is None:
            raise credentials_exception
        return TokenData(username=username, role=role)
    except JWTError:
        raise credentials_exception

def require_official(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    if current_user.role != "official":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation restricted to authorized disaster management officials."
        )
    return current_user
```
Apply `Depends(require_official)` to `/alerts/voice`, `/alerts/email`, `/notifications/broadcast`, `/complaints/resolve`, and `/agent-cycle`.

### 1.2 TwiML Injection & Outbound Toll-Fraud Defense
* **Finding (`FloodApp_Analysis.md` §4.1 Critical):** Raw string interpolation in `twiml_instruction = f"<Response><Say>{payload.message}</Say></Response>"` allows an attacker to inject `</Say><Dial>+1900PREMIUM</Dial><Say>` and dial arbitrary international numbers.
* **Fix:** Use the official Twilio TwiML Builder `VoiceResponse()`, enforce destination phone allowlists, validate E.164 phone regex, and require official role authentication.
```python
# dell-flood-backend/app/api/endpoints.py
from twilio.twiml.voice_response import VoiceResponse
import re

E164_REGEX = re.compile(r'^\+[1-9]\d{1,14}$')

@router.post("/alerts/voice")
def trigger_voice_call(payload: VoiceCallRequest, current_user: TokenData = Depends(require_official)):
    target_phone = payload.phone_number.strip()
    if not E164_REGEX.match(target_phone):
        raise HTTPException(status_code=400, detail="Invalid E.164 international phone number format.")
    
    # Safe TwiML synthesis using official builder - immunizes against XML injection
    response = VoiceResponse()
    response.say(payload.message, voice='alice', language='en-IN')
    twiml_str = str(response)
    
    # Execute dispatch via Twilio Client...
```

### 1.3 Stored XSS Mitigation in Official Map
* **Finding (`FloodApp_Analysis.md` §4.1 Critical):** Unsanitized `description` in `complaints` is rendered directly into HTML inside Leaflet tooltips in `MapView.tsx`, allowing arbitrary JavaScript execution in the official dashboard context.
* **Fix:**
  1. Backend sanitization with `bleach` or HTML entity escaping on report submission.
  2. Frontend tooltip rendering using native DOM text assignment rather than HTML template interpolation:
```typescript
// dell-flood-app/src/components/MapView.tsx
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// Inside Leaflet marker generation:
marker.bindTooltip(
  `<b>${escapeHtml(c.username)}</b><br/>${escapeHtml(c.description)}`,
  { permanent: false, direction: 'top' }
);
```

### 1.4 Client-Side Authentication Bypass Removal
* **Finding (`FloodApp_Analysis.md` §4.1 Critical):** `dell-flood-app/src/services/api.ts` lines 207-208 contain `(user.password === password || password === "123")` which short-circuits any login attempt to "SUCCESS" when the backend is offline.
* **Fix:** Completely remove the client-side authentication bypass. Authentication must always be validated against the server or a cryptographically signed biometric token in `expo-secure-store`.
```typescript
// dell-flood-app/src/services/api.ts
// REMOVED: offline bypass short-circuiting with "123"
if (!res.ok) {
  const errJson = await res.json().catch(() => ({}));
  throw new Error(errJson.detail || "Invalid credentials.");
}
```

### 1.5 Secure Password Hashing (Argon2 / BCrypt)
* **Finding (`FloodApp_Analysis.md` §4.1 High):** Passwords stored using unsalted `hashlib.sha256(password.encode()).hexdigest()` with hardcoded default accounts (`saif`, `shah`, `saif_official`).
* **Fix:** Replace with `passlib.context.CryptContext(schemes=["bcrypt"])` or `argon2-cffi`. Gate default seed users strictly behind a `DEMO_MODE=true` environment variable with randomized salt hashes.

### 1.6 Hardcoded Phone Numbers Removal
* **Finding (`FloodApp_Analysis.md` §4.1 High):** Developer phone `+917678656930` is hardcoded as fallback in `endpoints.py`, `tools.py`, and `api.ts`.
* **Fix:** Require explicit recipient phone numbers in request payloads or fetch registered contact numbers from the authenticated user profile in the database.

### 1.7 Path Traversal & Disk Exhaustion in PDF Generation
* **Finding (`FloodApp_Analysis.md` §4.1 High):** `location` input flows unsanitized into `f"./reports/report_{location.lower()}_{ts}.pdf"`, permitting directory traversal (`../../etc/passwd`) and disk exhaustion DoS.
* **Fix:** Sanitize filename using strict alphanumeric regex slugification and generate PDFs in-memory via `io.BytesIO()` returned as a `StreamingResponse`:
```python
import re, io
from fastapi.responses import StreamingResponse

def generate_pdf_in_memory(report_text, location, severity) -> io.BytesIO:
    safe_location = re.sub(r'[^a-zA-Z0-9_-]', '_', location)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    # Render PDF canvas to memory buffer...
    c.save()
    buf.seek(0)
    return buf
```

### 1.8 Unbounded In-Memory State & Log Leak Isolation
* **Finding (`FloodApp_Analysis.md` §4.1 High):** `jobs = {}`, `AGENT_TRACES = {}`, and `FloodAgent.activity_log` grow indefinitely in memory. `FloodAgent` is a singleton whose activity log leaks across different users.
* **Fix:** 
  1. Add TTL cache eviction (e.g., `cachetools.TTLCache(maxsize=100, ttl=3600)`) for `jobs` and `AGENT_TRACES`.
  2. Scope `FloodAgentState` per execution cycle (`run_id = uuid.uuid4()`) rather than maintaining a shared singleton list.

---

## 3. Section 2: High-Priority Correctness Bugs & Code Stability

### 2.1 Missing Python Dependencies in `requirements.txt`
* **Finding (`FloodApp_Analysis.md` §4.3 High):** `dell-flood-backend/app/agent/mireye_chatbot.py` imports `from openai import OpenAI` at top level. A clean `pip install -r requirements.txt` crashes immediately with `ModuleNotFoundError: No module named 'openai'`. Missing packages: `openai`, `scipy`, `scikit-learn`, `networkx`, `folium`, `httpx`, `Pillow`.
* **Fix:** Update `dell-flood-backend/requirements.txt` to include all runtime dependencies:
```text
fastapi>=0.110.0
uvicorn>=0.28.0
python-dotenv>=1.0.1
numpy>=1.26.4
opencv-python-headless>=4.9.0.80
torch>=2.2.1
transformers>=4.38.0
pillow>=10.2.0
scipy>=1.12.0
scikit-learn>=1.4.1
networkx>=3.2.1
folium>=0.16.0
httpx>=0.27.0
openai>=1.14.0
rasterio>=1.3.9
geopandas>=0.14.3
shapely>=2.0.3
pysheds>=0.3.5
langchain>=0.1.12
langgraph>=0.0.26
chromadb>=0.4.24
sentence-transformers>=2.5.1
twilio>=9.0.0
sendgrid>=6.11.0
reportlab>=4.1.0
requests>=2.31.0
pydantic>=2.6.4
python-multipart>=0.0.9
pypdf>=4.0.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
cachetools>=5.3.3
```

### 2.2 Expo Push Notification Kwarg Mismatch
* **Finding (`FloodApp_Analysis.md` §4.3 High):** `endpoints.py` calls `send_expo_push_notification(tok, title, body, data=...)` with a `data` keyword argument, but the function signature is `def send_expo_push_notification(push_token: str, title: str, body: str):`. This raises a `TypeError` and prevents all broadcasts from delivering.
* **Fix:** Update function signature to accept `data: dict = None`:
```python
def send_expo_push_notification(push_token: str, title: str, body: str, data: dict = None):
    if not push_token or not push_token.startswith("ExponentPushToken"):
        return
    payload = {
        "to": push_token,
        "sound": "default",
        "title": title,
        "body": body,
        "data": data or {"status": "escalated"}
    }
    requests.post("https://exp.host/--/api/v2/push/send", json=payload, timeout=5)
```

### 2.3 Missing Evacuation Function (`compute_elevation_evacuation_route`)
* **Finding (`FloodApp_Analysis.md` §4.3 High):** `flood_agent.py` L220 calls `from app.aegis.routing.evacuation_engine import compute_elevation_evacuation_route`, which does not exist in `evacuation_engine.py`. Caught silently in a `try...except`, logging a warning and aborting routing.
* **Fix:** Implement `compute_elevation_evacuation_route(lat, lon)` in `evacuation_engine.py` connecting the target coordinate to the nearest safe shelter via the routable road graph.

### 2.4 Duplicate SegFormer Model Loading
* **Finding (`FloodApp_Analysis.md` §4.3 Medium):** `endpoints.py` initializes `model = SegFormerMiTB2Fusion()`, and `FloodAgent` in `flood_agent.py` initializes `self.model = SegFormerMiTB2Fusion()`. Two full copies of the PyTorch neural weights are loaded into system memory, doubling RAM consumption.
* **Fix:** Export a shared singleton model instance from `app.ml.inference` or inject the initialized model instance into `FloodAgent(model=shared_model)`.

### 2.5 Real GeoTIFF Upload Handling (`/api/upload-geotiff`)
* **Finding (`FloodApp_Analysis.md` §4.3 Low):** The `/api/upload-geotiff` endpoint reads uploaded bytes into memory and completely ignores them, returning a hardcoded detection result for Patna (`25.6124, 85.1376`).
* **Fix:** Use `rasterio.open(io.BytesIO(content))` to extract real spatial bounding boxes, reproject coordinates to EPSG:4326, parse SAR/Optical bands, and execute SegFormer inference on the uploaded raster.

### 2.6 Geocoding Slang Filter Substring Bug
* **Finding (`FloodApp_Analysis.md` §4.1 Low):** Substring filter contains short tokens like `"mc"`, `"bc"`, `"kutta"`, which inadvertently block legitimate geographic locations such as **Kuttanad** (Kerala flood hotspot) and **McLeod Ganj**.
* **Fix:** Replace naive substring matching with regex word boundary matching (`r'\b(slang)\b'`) or remove the filter in favor of standard geocoding validation.

---

## 4. Section 3: Scientific Validity & Data Integrity Corrections

### 3.1 Consistent Pixel-to-Area Scaling Constants
* **Finding (`FloodApp_Analysis.md` §4.2):** Postprocessing calculates area using `0.000019 km²` ($19\text{ m²}$) per pixel, while `flood_agent.py` uses `0.0001 km²` ($100\text{ m²}$) per pixel. At Zoom 14 in northern India (Patna $25.6^\circ\text{N}$), pixel ground resolution is approximately $74.5\text{ m²}$ ($0.0000745\text{ km²}$).
* **Fix:** Compute pixel area dynamically from the geographic bounding box latitude:
$$\text{Pixel Area}(\text{km}^2) = \left(\frac{40075 \cdot \cos(\text{lat})}{2^{\text{zoom}} \cdot 256}\right)^2 / 10^6$$
For $512 \times 512$ bounding box of $0.04^\circ$:
$$\text{Pixel Area} = \left(\frac{0.04 \cdot 111.32}{512}\right) \cdot \left(\frac{0.04 \cdot 111.32 \cdot \cos(\text{lat})}{512}\right)\text{ km}^2$$

### 3.2 Scientifically Valid Model Confidence Metric
* **Finding (`FloodApp_Analysis.md` §4.2):** Model confidence is currently computed as `mean(prob_map)` across the entire $512 \times 512$ image (including thousands of dry pixels), and clamped to 68–70%.
* **Fix:** Compute confidence strictly over active flood pixels ($\text{mask} > 0$):
```python
if flooded_pix > 0:
    confidence_score = float(np.mean(prob_map[flood_mask > 0]) * 100.0)
else:
    confidence_score = 0.0
```

### 3.3 Clear Rainfall Definition (Forecast vs Historical Observation)
* **Finding (`FloodApp_Analysis.md` §4.2):** OpenWeather returns next 5 days *forecast*, while Open-Meteo returns past 5 days *observed* rain. Both are treated as identical 5-day cumulative rainfall.
* **Fix:** Separate telemetry into:
  - `antecedent_rain_5d_mm`: Past 120 hours observed rainfall (soil saturation factor).
  - `forecast_rain_24h_mm`: Next 24 hours forecasted rainfall (imminent flood surge factor).

### 3.4 Removing Deceptive PDF Disclaimers
* **Finding (`FloodApp_Analysis.md` §4.2):** Generated PDFs contain "RESTRICTED / EMERGENCY RESPONSE ONLY" and signature headers impersonating the "Director of Operations, State Disaster Management Agency (SDMA)".
* **Fix:** Replace with transparent hackathon disclaimers:
  - Header: `"AEGIS DISASTER INTELLIGENCE PLATFORM — EXPERIMENTAL DISASTER SIMULATION"`
  - Footer: `"Notice: Automated AI/Satellite prototype for emergency management decision support. Validate with local disaster authorities before operational deployment."`

### 3.5 Restore Leaflet Map Attribution
* **Finding (`FloodApp_Analysis.md` §4.5):** CSS `.leaflet-control-attribution { display: none; }` in `MapView.tsx` deliberately hides attribution, violating OpenStreetMap, Carto, and Esri tile licenses.
* **Fix:** Remove the display suppression rule and properly credit Esri, OpenStreetMap, and Sentinel Hub.

---

## 5. Section 4: Live Satellite Detection Pipeline Implementation

Incorporating all requirements from `map_implementation.md`:

```
┌────────────────────────────────────────────────────────────────────────┐
│             PROGRESSIVE STEP-BY-STEP STATUS STREAM (1s Poll)           │
├────────────────────────────────────────────────────────────────────────┤
│ 🛰️  Locating coordinates for target query...                           │
│ ✅  Location found — 26.12°N, 85.39°E                                  │
│ 🛰️  Requesting Sentinel-2 optical image from satellite...             │
│ ✅  Optical image acquired — cloud cover: 22% [Panel 1 Mounts]         │
│ 📡  Requesting Sentinel-1 SAR radar image...                          │
│ ✅  SAR image acquired — VV and VH bands loaded [Panel 2 Mounts]       │
│ 🔧  Aligning SAR and optical images (OpenCV ECC)...                    │
│ ✅  Images aligned — pixel shift corrected                            │
│ 🧠  Running SegFormer MiT-B2 dual-encoder inference...                 │
│ ✅  Model inference complete — 87.3% average confidence                │
│ 🎨  Generating segmentation composite & heatmap... [Panel 3 Mounts]    │
│ 💧  Filtering permanent water bodies (NDWI baseline)...                │
│ ✅  Rivers and lakes removed from flood mask                           │
│ 🏔️  Validating with elevation data (DEM check)...                      │
│ ✅  High ground false positives cleared                                │
│ 📊  Classifying flood type (waterlogging vs flood)...                  │
│ 🏘️  Overlaying live OSM Overpass assets (buildings, roads, hospitals) │
│ 👥  Calculating affected population from WorldPop raster...            │
│ ⚠️  Severity scored: CRITICAL                                          │
│ ✅  Vector GeoJSON polygons rendered on map                            │
└────────────────────────────────────────────────────────────────────────┘
```

### 5.1 Real Sentinel Hub Process API Ingestion
* Uses official client credentials OAuth with TTL token caching.
* Extracts Sentinel-2 B04, B03, B02 + CLM cloud QA band.
* Extracts Sentinel-1 GRD VV + VH bands.
* Uses identical $4\text{km} \times 4\text{km}$ bounding boxes at $512 \times 512$ resolution.

### 5.2 Dynamic Cloud-Adaptive Fusion Gating
```python
# Attenuate optical features in high cloud conditions
cloud_fraction = min(1.0, max(0.0, cloud_cover_pct / 100.0))
optical_tensor = optical_tensor * (1.0 - cloud_fraction * 0.8)
# Passes to SegFormer Gated Fusion Block
```

### 5.3 Live OSM Overpass & WorldPop Joins (Zero Hardcoding)
* Live Overpass API queries buildings, roads, hospitals, and schools inside the bounding box.
* `rasterio.features.shapes()` extracts real polygon boundaries.
* `shapely` spatial intersection counts actual damaged structures.
* WorldPop raster mask computes true population estimates.

### 5.4 Dual-View Visual Output
* **Composite View:** 60% alpha flood overlay painted onto real satellite terrain.
* **Raw Heatmap View:** Pure RdYlBu_r matplotlib colormap (blue=dry, red=high probability).
* Toggle button on frontend switches between views without re-running inference.

---

## 6. Section 5: U-RNN 4D Spatiotemporal Water-Depth Nowcasting

Incorporating the breakthroughs from `holmescao/U-RNN` (*Journal of Hydrology 2025*):

### 6.1 5-Channel Hydrological Input Tensor Assembly
Tensor dimensions: $(B=1, T=4, C=9, H=512, W=512)$
1. $W=3$ Instantaneous Rainfall fields ($R_t, R_{t-1}, R_{t-2}$ in mm/min)
2. $W=3$ Cumulative Rainfall Volume fields ($\sum R_t$ in mm — the primary driver of ponding depth)
3. Normalized Digital Elevation Model ($Z(x, y)$ from USGS 3DEP / Mireye)
4. Surface Imperviousness Fraction ($\phi \in [0, 1]$ from building/road footprints)
5. Stormwater Drainage Inlet Density ($M \in \{0, 1\}$)

### 6.2 Multi-Scale ConvGRU U-Net with YOLOX Dual-Head
* **Encoder:** 3-stage downsampling ($1\times, \frac{1}{2}\times, \frac{1}{4}\times$) with ConvGRU recurrent cells.
* **Decoder:** 3-stage upsampling with skip-connection ConvGRUs.
* **YOLOX Dual Head:**
  - Continuous water depth regression $h \ge 0$ in millimeters/meters.
  - Wet/dry probability classification $\hat{p} \in [0, 1]$.
  - Physical correction: $\tilde{h} = h \cdot \mathbb{I}(\hat{p} \ge 0.40)$ (zeros out elevated dry ground).
* **Sliding-Window Pre-warming (SWP):** Evaluates multi-hour storm hydrographs without GPU memory exhaustion.

### 6.3 Time-Varying Dynamic Evacuation Routing
* Dijkstra router computes edge weights based on water depth at **the evacuee's arrival time**:
$$\text{Cost}(e, t_{\text{arrival}}) = \begin{cases} \infty & \text{if } \text{Depth}(e, t_{\text{arrival}}) \ge 0.30\,\text{m} \\ \text{length}(e) \cdot \left(1.0 + 4.0 \cdot \frac{\text{Depth}(e, t_{\text{arrival}})}{0.30}\right) & \text{if } \text{Depth}(e, t_{\text{arrival}}) < 0.30\,\text{m} \end{cases}$$
* Prevents civilians from driving onto roads that are dry at departure but submerged by the time they arrive.

### 6.4 Frontend 4D Time-Scrubber UI
* Scrub between `Now (0m)`, `+15m`, `+30m`, `+60m`.
* Water depths color-coded:
  - Cyan: $<0.15\text{m}$ (Passable for pedestrians)
  - Orange: $0.15 - 0.30\text{m}$ (Passenger vehicle hazard)
  - Crimson: $>0.30\text{m}$ (Impassable / submerged)

---

## 7. Section 6: Agentic Redesign & Human-in-the-Loop Architecture

Transforming the scripted `FloodAgent` into an autonomous, verified multi-agent system:

```
                          ┌───────────────────────────┐
                          │   INCIDENT ORCHESTRATOR   │
                          │   (LangGraph Supervisor)  │
                          └─────────────┬─────────────┘
                                        │
           ┌──────────────┬─────────────┼─────────────┬──────────────┐
           ▼              ▼             ▼             ▼              ▼
     ┌───────────┐  ┌───────────┐ ┌───────────┐ ┌───────────┐  ┌───────────┐
     │  MONITOR  │  │EO ANALYST │ │ LOGISTICS │ │   COMMS   │  │ CROWD INT │
     │   AGENT   │  │   AGENT   │ │   AGENT   │ │   AGENT   │  │   AGENT   │
     │ Weather & │  │ Sentinel1/2│ │ Shelters &│ │ Multilingual│ │ Deduplicate│
     │  Gauges   │  │ SegFormer │ │ Time-Route│ │ CAP Alerts│ │ & Verify  │
     └───────────┘  └───────────┘ └───────────┘ └─────┬─────┘  └───────────┘
                                                      │
                                                      ▼
                                            ┌───────────────────┐
                                            │ HUMAN-IN-THE-LOOP │
                                            │  APPROVAL QUEUE   │
                                            │ (Official Signoff)│
                                            └───────────────────┘
```

### 7.1 Multi-Agent Specialization
1. **Monitor Agent:** Continuously watches weather forecasts (OpenWeather) and river gauge stations.
2. **EO Analyst Agent:** Triggers Sentinel Hub acquisitions, executes SegFormer fusion and U-RNN nowcasting.
3. **Logistics Agent:** Manages shelter capacities and computes time-dependent evacuation corridors.
4. **Comms Agent:** Drafts Common Alerting Protocol (CAP) messages in local languages (Hindi, Assamese, English).
5. **Crowd Intelligence Agent:** Clusters citizen reports, filters noise, and auto-triggers detection sweeps when 3+ reports cluster within 2km in 12 hours.

### 7.2 Human-in-the-Loop (HITL) Gate
* All external alert dispatches (Twilio voice calls, SMS broadcasts, public push notifications) are held in an **Approval Queue** requiring an official's cryptographic signature before transmission.

---

## 8. Section 7: User-Mandated Features & Localization Implementation

### 8.1 "Raise Query" Citizen Image Evidence Upload
* **Problem:** `ReportForm.tsx` currently only allows text description and category checkboxes. Citizens cannot capture or attach photo evidence of inundation.
* **Implementation:**
  1. Add `expo-image-picker` integration to `ReportForm.tsx`.
  2. Implement an **"Attach Photo Evidence"** button supporting camera and gallery selection.
  3. Compress images client-side to $\le 150\text{KB}$ with `quality: 0.5` to ensure reliability in low-bandwidth disaster zones.
  4. Display an image thumbnail preview with a "Remove" button before submission.
  5. Send base64 / multipart data to `/api/report-flood`, persist in `complaints` table, and display in the Official Triage Panel.

### 8.2 Hardcoded Demo Phone (`+917678656930`) & Multilingual LLM Voice Call Pipeline
* **Problem & Hackathon Reality:** During judging and testing, there are no live external civilians connected to the app. Emergency alerts must reliably dial the presenter's phone.
* **Implementation:**
  1. Set default target phone explicitly to **`+917678656930`** (or `7678656930`) across the official dashboard and alert triggers.
  2. **Dynamic LLM Voice Script Generation:** The emergency speech text is generated dynamically on-the-fly by an LLM (Gemini / Bedrock / Groq) using real-time coordinates, verified flood severity, maximum predicted water depth from U-RNN, and the nearest shelter.
  3. **Multilingual Voice Support (Hindi & English):**
     - When Hindi is active, LLM produces urgent Devanagari speech:  
       *"आपातकालीन चेतावनी! आपके क्षेत्र में गंभीर बाढ़ का पानी बढ़ रहा है। कृपया तुरंत निकटतम सुरक्षित राहत शिविर की ओर निकलें।"*
     - TwiML voice synthesis configured using Indian voices: `<Say voice="Polly.Aditi" language="hi-IN">` for Hindi and `<Say voice="alice" language="en-IN">` for English.

### 8.3 Startup Language Selection Modal (Onboarding) & App-Wide Localization
* **Problem:** Disasters in India (Bihar, Assam) require accessibility in local languages; currently all UI text is hardcoded in English.
* **Implementation:**
  1. Create `dell-flood-app/src/utils/i18n.ts` defining structured translation dictionaries for **English** and **हिन्दी (Hindi)**.
  2. On app launch in `App.tsx`, check `AsyncStorage.getItem('aegis_user_language')`. If unset, render an elegant **Language Selection Modal** before navigating to the workspace.
  3. Dynamically translate all UI tabs (Map / नक्शा, Report / रिपोर्ट, Raise Query / समस्या दर्ज करें, Triage / प्राथमिकता, Agent / एजेंट, Settings / सेटिंग्स).
  4. Localize alert notification banners and TTS audio readouts (`expo-speech` with `language: 'hi-IN' | 'en-IN'`).

---

## 9. Section 8: Immediate "Quick Wins" Execution Checklist (<1 Hour Each)

These items from `FloodApp_Analysis.md` §8 can be completed immediately:

- [ ] **Quick Win 1:** Add `data: dict | None = None` parameter to `send_expo_push_notification` in `dell-flood-backend/app/api/endpoints.py` (L196).
- [ ] **Quick Win 2:** Add `openai`, `scipy`, `scikit-learn`, `networkx`, `folium`, `httpx`, and `Pillow` to `dell-flood-backend/requirements.txt`.
- [ ] **Quick Win 3:** In `dell-flood-app/src/services/api.ts` (L561), replace `DEFAULT_API_URL` with `this.apiUrl` in `broadcastNotification`.
- [ ] **Quick Win 4:** In `dell-flood-backend/app/aegis/pipeline/triage_engine.py`, return `"override_logs": state.get("override_logs", [])` in `node_allocate_shelters`.
- [ ] **Quick Win 5:** Remove `password === "123"` offline auth bypass from `dell-flood-app/src/services/api.ts` (L207-208).
- [ ] **Quick Win 6:** Enable Leaflet map attribution in `dell-flood-app/src/components/MapView.tsx` by deleting `.leaflet-control-attribution { display: none; }`.
- [ ] **Quick Win 7:** Remove non-existent model name `gemini-3.8-flash` from fallback candidate lists in `endpoints.py` and `generator.py`.
- [ ] **Quick Win 8:** Delete the substring slang filter in `/geocode` in `endpoints.py` (L1799-1801).

---

## 10. Section 9: Verification & End-to-End Test Suite

### 10.1 Automated Verification Commands
```bash
# 1. Dependency Validation
pip install -r dell-flood-backend/requirements.txt
python -c "import openai, scipy, networkx, PIL, folium, httpx; print('Dependencies verified')"

# 2. Authentication Enforcement Test
curl -X POST http://localhost:8000/api/alerts/voice \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "+917678656930", "message": "Test"}'
# Expected Output: HTTP 401 Unauthorized

# 3. Progressive Pipeline Execution Test
curl -X POST "http://localhost:8000/api/run-detection?lat=26.12&lon=85.39&cloud_cover=20"
# Returns: {"job_id": "<uuid>"}

# 4. Status Stream Polling Test
curl http://localhost:8000/api/status/<uuid>
# Returns: {"status": "running", "steps_completed": [...], "partial_result": {...}}

# 5. U-RNN Spatiotemporal Nowcast Test
curl "http://localhost:8000/api/nowcast?lat=26.12&lon=85.39&horizon_minutes=60"
# Returns: {"timesteps": [0, 15, 30, 60], "depth_grid": [...], "max_depth_m": 0.84}

# 6. Multilingual Voice Dispatch to Demo Target
curl -X POST http://localhost:8000/api/alerts/voice \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "+917678656930", "location": "Patna", "severity": "CRITICAL", "language": "hi"}'
# Expected Output: {"status": "SUCCESS", "target": "+917678656930", "speech": "आपातकालीन चेतावनी..."}
```

---
*Created for Team Aegis | AI Flood Detection & Disaster Response System*

