# Aegis Disaster Intelligence Platform — API Reference Manual
**Version:** 2.0.0  
**Specification:** OpenAPI 3.1.0 / REST + Model Context Protocol (MCP 2025-11) + OASIS CAP v1.2  
**Service:** Multimodal 4D Flood Detection, U-RNN Nowcasting & Autonomous Disaster Response System  

---

## 1. Overview & Architecture

The **Aegis Disaster Intelligence Platform** exposes a high-throughput, secure REST and MCP interface for flood detection, depth nowcasting, emergency alert dissemination, and autonomous multi-agent response orchestration.

### Base URLs
* **Local Development:** `http://localhost:8000` (or `http://127.0.0.1:8000`)
* **Remote Secure Tunnel:** `https://<active-tunnel-subdomain>.trycloudflare.com`
* **API Route Prefix:** `/api`
* **Interactive OpenAPI Swagger Docs:** `http://localhost:8000/docs`
* **Alternative ReDoc UI:** `http://localhost:8000/redoc`

### System Highlights
1. **Multimodal Sensor Fusion:** SegFormer MiT-B2 neural network fusing Sentinel-1 SAR (VV/VH backscatter) and Sentinel-2 L2A optical (R, G, B, NIR) bands with physical cloud-cover compensation.
2. **4D Depth Nowcasting:** 3-Scale ConvGRU + YOLOX dual-head network predicting continuous water depth across 4 time horizons ($0\text{ min}$, $+15\text{ min}$, $+30\text{ min}$, $+60\text{ min}$) at $140\times$ faster execution than MIKE+ hydrodynamic simulations.
3. **Time-Varying Dijkstra Routing:** Real-time DEM-integrated graph traversal avoiding dangerous floodwaters ($>30\text{ cm}$) to route evacuees to verified elevated shelters.
4. **Multi-Agent Orchestration & HITL:** 6-agent LangGraph state machine with Human-in-the-Loop approval gates for high-impact actions (e.g. mass emergency telephony).
5. **Formal Model Context Protocol (MCP):** 15 secure disaster response tools executed within cryptographic provenance sandboxes.

---

## 2. Authentication & Authorization

Aegis uses **JSON Web Tokens (JWT)** with role-based access control (RBAC).

### Request Header
```http
Authorization: Bearer <your_access_token>
```

### User Roles
| Role | Privileges |
| :--- | :--- |
| `citizen` | Submit flood reports, view detection maps, query AI chatbot, request personal evacuation routes. |
| `official` | Access administrative dashboard, approve HITL actions, trigger Twilio calls, resolve citizen complaints, broadcast emergency bulletins. |
| `ndrf` | National Disaster Response Force level access (same as official with priority field dispatch). |
| `admin` | Full system access including resource provisioning, diagnostic suites, and audit ledger access. |

---

## 3. API Endpoints Reference

---

### Module 1: Authentication & User Accounts

#### 1. Register User
* **Method:** `POST`
* **Path:** `/api/auth/register`
* **Access:** Public
* **Description:** Creates a new citizen or official account with salted password hashing.

**Request Body:**
```json
{
  "username": "rajat_official",
  "password": "SecurePassword123!",
  "role": "official",
  "phone": "+917678656930",
  "expo_push_token": "ExponentPushToken[xxxxxxxxxxxxxx]"
}
```

**Response (`200 OK`):**
```json
{
  "status": "SUCCESS",
  "message": "User registered successfully",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "role": "official",
  "username": "rajat_official"
}
```

---

#### 2. Login User
* **Method:** `POST`
* **Path:** `/api/auth/login`
* **Access:** Public
* **Description:** Authenticates credentials and returns a signed JWT access token.

**Request Body:**
```json
{
  "username": "rajat_official",
  "password": "SecurePassword123!",
  "expo_push_token": "ExponentPushToken[xxxxxxxxxxxxxx]"
}
```

**Response (`200 OK`):**
```json
{
  "status": "SUCCESS",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "role": "official",
  "username": "rajat_official"
}
```

---

### Module 2: Multimodal 4D Flood Detection & Satellite Inference

#### 1. Run Autonomous 16-Step Detection Pipeline
* **Method:** `POST`
* **Path:** `/api/run-detection`
* **Access:** Public
* **Description:** Initiates an asynchronous 16-step detection pipeline acquiring real-time Sentinel-2 L2A optical and Sentinel-1 SAR imagery for the given geographic coordinate.

**Query Parameters:**
| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `lat` | float | Yes | — | Center latitude (e.g. `25.6124`) |
| `lon` | float | Yes | — | Center longitude (e.g. `85.1376`) |
| `cloud_cover` | float | No | `0.0` | Cloud coverage percentage. If `0`, live Open-Meteo cloud cover is retrieved. |

**Response (`200 OK`):**
```json
{
  "job_id": "c2bdb31a5c4d4eb8be981b1087c30e5a"
}
```

---

#### 2. Poll Detection Job Status
* **Method:** `GET`
* **Path:** `/api/status/{job_id}`
* **Access:** Public
* **Description:** Polls the status and extracts progressive step completions and final artifacts for a detection job.

**Response (`200 OK` - In Progress):**
```json
{
  "job_id": "c2bdb31a5c4d4eb8be981b1087c30e5a",
  "status": "running",
  "current_step": "model_inference",
  "steps_completed": [
    {"step": "geocoding", "message": "[STEP 01/16] Location locked — 25.6124°N, 85.1376°E", "done": true},
    {"step": "sentinel2_fetch", "message": "[STEP 02/16] Sentinel-2 L2A Optical acquired — cloud cover 14.2%", "done": true},
    {"step": "sentinel1_fetch", "message": "[STEP 03/16] Sentinel-1 SAR GRD fetched — VV/VH polarized backscatter", "done": true},
    {"step": "ecc_registration", "message": "[STEP 04/16] Enhanced Correlation Coefficient (ECC) sub-pixel registration aligned", "done": true}
  ],
  "partial_result": {
    "optical_b64": "data:image/png;base64,iVBORw0KGgoAAA...",
    "sar_b64": "data:image/png;base64,iVBORw0KGgoAAA..."
  },
  "result": null
}
```

**Response (`200 OK` - Completed):**
```json
{
  "job_id": "c2bdb31a5c4d4eb8be981b1087c30e5a",
  "status": "complete",
  "current_step": "dynamic_routing",
  "result": {
    "confidence_score": 91.4,
    "cloud_cover": 14.2,
    "classification": "Flood Inundation",
    "area_sq_km": 3.84,
    "severity": "CRITICAL",
    "severity_score": 96.8,
    "impact": {
      "population": 2450,
      "buildings": 312,
      "facilities": 4
    },
    "mask_geojson": { "type": "FeatureCollection", "features": [...] },
    "spread_24h_48h_geojson": { "type": "FeatureCollection", "features": [...] },
    "downhill_warnings": [
      { "location": "Low-lying basin sector", "predicted_arrival_hours": 12.5, "severity": "HIGH" }
    ],
    "optical_b64": "data:image/png;base64,...",
    "sar_b64": "data:image/png;base64,...",
    "segmentation_composite_b64": "data:image/png;base64,...",
    "probability_heatmap_b64": "data:image/png;base64,...",
    "optical_only_b64": "data:image/png;base64,...",
    "urnn_nowcast": { ... },
    "dynamic_evacuation_route": { ... }
  }
}
```

---

#### 3. Upload GeoTIFF Satellite Bundle
* **Method:** `POST`
* **Path:** `/api/upload-geotiff`
* **Access:** Public
* **Description:** Directly uploads a multi-spectral TIFF image (`.tif` / `.tiff`) for local SegFormer inference.

**Form Data:**
* `file`: Binary GeoTIFF file
* `lat`: float (default `25.6124`)
* `lon`: float (default `85.1376`)

---

#### 4. Predict Ground or Drone Image
* **Method:** `POST`
* **Path:** `/api/predict-image`
* **Access:** Public
* **Description:** Runs flood segmentation and waterlogging assessment on an RGB ground photograph or drone capture.

**Request Body:**
```json
{
  "image_b64": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
  "lat": 28.6253,
  "lon": 77.1065
}
```

---

### Module 3: U-RNN 4D Depth Nowcasting & Topographic Spread

#### 1. Get 4-Horizon Nowcast & Evacuation Bundle
* **Method:** `GET`
* **Path:** `/api/nowcast`
* **Access:** Public
* **Description:** Returns the 4-horizon water depth predictions ($0\text{m}$, $+15\text{m}$, $+30\text{m}$, $+60\text{m}$), 5-factor hydrological tensor metadata, and dynamic safe routes.

**Query Parameters:**
* `lat`: float (default `25.6124`)
* `lon`: float (default `85.1376`)
* `rain_mm_hr`: float (optional precipitation override)
* `drainage_eff`: float (default `65.0`% drainage efficiency)

**Response (`200 OK`):**
```json
{
  "status": "SUCCESS",
  "lat": 25.6124,
  "lon": 85.1376,
  "hydro_metadata": {
    "inst_rain_mm_hr": 28.4,
    "cumul_rain_24h_mm": 74.2,
    "mean_imperviousness": 0.58,
    "drainage_inlet_count": 86
  },
  "urnn_nowcast": {
    "architecture": "U-RNN (ConvGRU + YOLOX Dual-Head)",
    "horizons_min": [0, 15, 30, 60],
    "latency_ms": 42.5,
    "speedup_vs_mike_plus": "140x faster",
    "max_depth_0m": 0.42,
    "max_depth_15m": 0.58,
    "max_depth_30m": 0.74,
    "max_depth_60m": 0.89,
    "Horizon_Stats": {
      "0m": { "mean_depth": 0.22, "inundated_area_km2": 2.1 },
      "60m": { "mean_depth": 0.51, "inundated_area_km2": 4.6 }
    },
    "heatmaps_b64": {
      "0m": "data:image/png;base64,...",
      "60m": "data:image/png;base64,..."
    }
  },
  "dynamic_evacuation_route": {
    "route_geometry": [[25.6124, 85.1376], [25.6150, 85.1390], [25.6200, 85.1450]],
    "distance_km": 1.84,
    "eta_minutes": 22.5,
    "avoided_flooded_nodes_count": 14,
    "elevation_safety_score": 94.2
  },
  "infrastructure_assets": [
    { "type": "shelter", "name": "Sector 4 Safe Haven", "lat": 25.6200, "lon": 85.1450, "status": "OPERATIONAL" },
    { "type": "blocked_underpass", "lat": 25.6135, "lon": 85.1382, "status": "FLOODED_IMPASSABLE" }
  ]
}
```

---

#### 2. Simulate What-If Nowcast Scenario
* **Method:** `POST`
* **Path:** `/api/nowcast/simulate`
* **Access:** Public
* **Description:** Runs an on-demand physical parameter simulation varying rainfall intensity and storm drainage efficiency.

**Request Body:**
```json
{
  "lat": 25.6124,
  "lon": 85.1376,
  "rainfall_slider_mm_hr": 55.0,
  "drainage_efficiency_pct": 30.0
}
```

---

### Module 4: Dynamic Evacuation & Topographic Wetness Index (TWI)

#### 1. Plan Elevation-Weighted Evacuation Route
* **Method:** `POST`
* **Path:** `/api/aegis/evacuation/plan`
* **Access:** Public
* **Description:** Traverses the SRTM 30m Digital Elevation Model using Time-Varying Dijkstra pathfinding to route away from accumulating water.

**Request Body:**
```json
{
  "origin_lat": 25.6124,
  "origin_lon": 85.1376,
  "target_lat": null,
  "target_lon": null
}
```

**Response (`200 OK`):**
```json
{
  "status": "SUCCESS",
  "origin": [25.6124, 85.1376],
  "destination": [25.6320, 85.1520],
  "chosen_shelter": {
    "name": "District Elevated Community Center",
    "lat": 25.6320,
    "lng": 85.1520,
    "capacity": 250,
    "slots_available": 205,
    "distance_km": 2.45,
    "elevation_m": 42.5
  },
  "alternative_shelters": [ ... ],
  "route_geometry": [[25.6124, 85.1376], ...],
  "distance_km": 2.45,
  "eta_minutes": 29.0,
  "avoided_flooded_nodes_count": 8,
  "elevation_safety_score": 96.5,
  "elevation_gain_m": 14.0,
  "routing_mode": "ELEVATION_WEIGHTED_DIJKSTRA"
}
```

---

#### 2. Predict Topographic Wetness Index (TWI)
* **Method:** `POST`
* **Path:** `/api/aegis/twi/predict`
* **Access:** Public
* **Description:** Computes terrain slope, flow accumulation, and natural pooling susceptibility nodes.

**Request Body:**
```json
{
  "lat": 25.6124,
  "lon": 85.1376,
  "grid_size": 256
}
```

---

#### 3. Execute Multi-County Disaster Triage Run
* **Method:** `POST`
* **Path:** `/api/aegis/triage/run`
* **Access:** Official
* **Description:** Initiates an automated LangGraph multi-criteria resource allocation algorithm across regional shelters and vulnerable citizen clusters.

---

### Module 5: Citizen Crowdsourcing & Disaster Reports

#### 1. Report Flood Incident (Crowdsourcing)
* **Method:** `POST`
* **Path:** `/api/report-flood`
* **Access:** Public
* **Description:** Records a ground-truth citizen complaint, verifies it against live Open-Meteo precipitation, and flags it for official intervention.

**Request Body:**
```json
{
  "username": "shahzeb_citizen",
  "lat": 28.6253,
  "lon": 77.1065,
  "severity": "SEVERE",
  "description": "Street drainage choked after continuous cloudburst. Water entering ground-floor dwellings.",
  "location_name": "Hari Nagar Block B, West Delhi",
  "image_b64": "data:image/jpeg;base64,..."
}
```

**Response (`200 OK`):**
```json
{
  "status": "SUCCESS",
  "message": "Complaint logged successfully.",
  "complaint_id": 14,
  "model_confirmed": 1,
  "rainfall_mm": 32.5,
  "score": 85.0
}
```

---

#### 2. List & Filter Citizen Complaints
* **Method:** `GET`
* **Path:** `/api/complaints/list`
* **Access:** Public
* **Description:** Retrieves all crowdsourced complaints with optional severity, status, and coordinate filtering.

**Query Parameters:**
* `status`: string (`all`, `pending`, `resolved`)
* `severity`: string (`all`, `LOW`, `MODERATE`, `HIGH`, `CRITICAL`)
* `include_images`: boolean (default `true`)

---

#### 3. Resolve Citizen Complaint
* **Method:** `POST`
* **Path:** `/api/complaints/resolve`
* **Access:** Official (Bearer Token required)
* **Description:** Marks a flood report as resolved by an official responder.

**Request Body:**
```json
{
  "complaint_id": 14
}
```

---

### Module 6: Multi-Agent AI & Disaster RAG Chatbot

#### 1. FloodRescuer Emergency RAG Chatbot
* **Method:** `POST`
* **Path:** `/api/agent/chat`
* **Access:** Public
* **Description:** Context-aware AI assistant powered by Google Gemini 2.5 Flash (with Groq Llama-3.3 fallback) grounded in vector-indexed National Disaster Management SOPs.

**Request Body:**
```json
{
  "message": "Where is the nearest safe shelter and how do I avoid water over 1 foot deep?",
  "lastResult": {
    "location": "Patna Sector 3",
    "area_sq_km": 3.84,
    "severity": "CRITICAL",
    "impact": {
      "population": 2450,
      "buildings": 312,
      "facilities": 4
    }
  }
}
```

**Response (`200 OK`):**
```json
{
  "response": "Evacuate immediately toward the District Elevated Community Center located 2.45 km north-east. The Time-Varying Dijkstra routing engine has identified clear pathways avoiding the flooded Main Road underpass (depth: 0.74m). Keep emergency helpline 108 on speed dial. Do not walk or drive through flowing water."
}
```

---

#### 2. Conversational Agent with MirEye Tool Calling
* **Method:** `POST`
* **Path:** `/api/chat/message`
* **Access:** Public
* **Description:** Intelligent agent with automatic tool calling for reverse geocoding, flood hazard index queries, and evacuation instructions.

---

#### 3. Trigger 6-Agent LangGraph Swarm Cycle
* **Method:** `POST`
* **Path:** `/api/agent-cycle`
* **Access:** Official (Bearer Token required)
* **Description:** Triggers autonomous execution across 6 specialized agents:
  1. `Perception Agent` (Satellite acquisition)
  2. `Hydro Nowcaster Agent` (Depth calculation)
  3. `Infrastructure Impact Agent` (OSM spatial joins)
  4. `Triage Optimization Agent` (Resource allocation)
  5. `Comms & Telephony Agent` (Drafting alerts)
  6. `HITL Supervisor Agent` (Safety gate checkpoint)

---

### Module 7: Emergency Telephony, Multilingual Voice & Broadcasts

#### 1. Automated Emergency Voice Call (Twilio Voice)
* **Method:** `POST`
* **Path:** `/api/alerts/voice`
* **Access:** Official (Bearer Token required)
* **Description:** Dispatches an automated phone call using Twilio Voice API speaking Hindi or English text.

**Request Body:**
```json
{
  "phone_number": "+917678656930",
  "message": "चेतावनी! आपके क्षेत्र में जलस्तर 0.68 मीटर तक बढ़ गया है। तुरंत सुरक्षित आश्रय की ओर प्रस्थान करें।",
  "location": "Patna District",
  "severity": "CRITICAL",
  "language": "hi",
  "max_depth_m": 0.68
}
```

**Response (`200 OK`):**
```json
{
  "status": "SUCCESS",
  "call_sid": "CAe128394fbc87a2109bca76329019283",
  "recipient": "+917678656930",
  "language": "hi"
}
```

---

#### 2. Amazon Polly Neural Voice Synthesis
* **Method:** `POST`
* **Path:** `/api/alerts/voice-polly`
* **Access:** Official (Bearer Token required)
* **Description:** Synthesizes emergency broadcast audio in Hindi (`Aditi`) or English (`Kajal`) via Amazon Polly Neural Engine.

---

#### 3. Mass SMS Broadcast via Amazon SNS
* **Method:** `POST`
* **Path:** `/api/alerts/broadcast-sns`
* **Access:** Official (Bearer Token required)
* **Description:** Publishes immediate mass flood evacuation bulletins across regional cell towers via Amazon SNS Topic.

---

#### 4. Automated SITREP Email Briefing
* **Method:** `POST`
* **Path:** `/api/alerts/email-report`
* **Access:** Official (Bearer Token required)
* **Description:** Sends an automated situation briefing email with geospatial metrics, population exposure, and official PDF attachments via SMTP.

---

#### 5. OASIS Common Alerting Protocol (CAP v1.2) Feed
* **Method:** `GET`
* **Path:** `/api/alerts/cap`
* **Access:** Public
* **Description:** Returns standard OASIS CAP XML 1.2 payload consumable by national meteorological agencies and broadcast systems.

---

### Module 8: Formal Model Context Protocol (MCP) Server

#### 1. List Registered MCP Tools
* **Method:** `GET`
* **Path:** `/api/mcp/tools`
* **Access:** Public
* **Description:** Returns the complete catalog of 15 MCP disaster response tools formatted under the formal MCP 2025-11 specification.

**Response (`200 OK`):**
```json
{
  "protocol": "Model Context Protocol (MCP) 2025-11",
  "server": "aegis-flood-mcp-server",
  "version": "2.0.0",
  "tool_count": 15,
  "tools": [
    {
      "name": "fetch_satellite_water_mask",
      "description": "Acquires Sentinel-1 SAR and Sentinel-2 L2A optical imagery to generate fused flood probability masks.",
      "input_schema": { ... }
    },
    {
      "name": "compute_urnn_depth_nowcast",
      "description": "Runs 4D U-RNN ConvGRU depth nowcasting for 0m, 15m, 30m, and 60m horizons.",
      "input_schema": { ... }
    },
    {
      "name": "generate_evacuation_route",
      "description": "Calculates elevation-weighted safe evacuation route to nearest high-ground refuge.",
      "input_schema": { ... }
    }
  ]
}
```

---

#### 2. Execute MCP Tool
* **Method:** `POST`
* **Path:** `/api/mcp/execute`
* **Access:** Official (Bearer Token required)
* **Description:** Executes an approved MCP tool in a cryptographically signed sandbox environment.

**Request Body:**
```json
{
  "tool_name": "compute_urnn_depth_nowcast",
  "arguments": {
    "lat": 25.6124,
    "lon": 85.1376,
    "rainfall_mm_hr": 35.0
  },
  "idempotency_key": "mcp_nowcast_job_991823"
}
```

---

#### 3. Audit Ledger & Cryptographic Provenance
* **Method:** `GET`
* **Path:** `/api/mcp/provenance`
* **Access:** Public
* **Description:** Returns the immutable audit ledger verifying execution inputs, outputs, timestamps, and operator signatures.

---

### Module 9: Automated SITREP & PDF Reporting

#### 1. State Flood Vulnerability Preview (Assam Top 10)
* **Method:** `GET`
* **Path:** `/api/reports/assam-top10/preview`
* **Access:** Public
* **Description:** Returns real-time vulnerability rankings, river gauge levels, and population exposures for the 10 most critical flood districts in Assam.

---

#### 2. Download Official Disaster Briefing PDF
* **Method:** `GET`
* **Path:** `/api/reports/download-pdf`
* **Access:** Public
* **Description:** Dynamically generates and returns an official NDRF / SDMA formatted PDF Situation Briefing containing maps, affected infrastructure, and contact protocols.

---

### Module 10: Human-in-the-Loop (HITL) Safety Gate

#### 1. List Pending HITL Actions
* **Method:** `GET`
* **Path:** `/api/hitl/queue`
* **Access:** Official (Bearer Token required)
* **Description:** Lists all proposed autonomous agent interventions (e.g. mass siren triggers, shelter redirections) awaiting human commander authorization.

---

#### 2. Authorize or Reject HITL Action
* **Method:** `POST`
* **Path:** `/api/hitl/approve`
* **Access:** Official (Bearer Token required)
* **Description:** Authorizes execution of a draft action with commander identity verification.

**Request Body:**
```json
{
  "item_id": "draft_call_patna_sector3",
  "language": "hi"
}
```

---

## 4. Standard HTTP Status Codes & Error Handling

All responses return standard HTTP status codes. Errors include an explicit `detail` payload:

```json
{
  "detail": "Invalid credentials or server unreachable."
}
```

| HTTP Status | Reason | Description |
| :--- | :--- | :--- |
| `200 OK` | Success | Request succeeded and response payload is returned. |
| `201 Created` | Created | Resource successfully created (e.g. account registration). |
| `202 Accepted` | Processing | Asynchronous task queued (e.g. background intel runs). |
| `400 Bad Request` | Client Error | Malformed parameters or invalid coordinates. |
| `401 Unauthorized` | Auth Required | Missing or expired JWT Bearer token. |
| `403 Forbidden` | Access Denied | Insufficient role permissions (e.g. citizen calling official endpoint). |
| `404 Not Found` | Not Found | Resource or job ID does not exist. |
| `422 Unprocessable Entity` | Validation Error | Request body does not conform to Pydantic schema. |
| `500 Server Error` | Backend Failure | Internal pipeline execution exception. |

---

## 5. Client Integration Code Samples

### Python (`requests`)
```python
import requests
import time

BASE_URL = "http://localhost:8000/api"

# 1. Login to obtain JWT
login_res = requests.post(f"{BASE_URL}/auth/login", json={
    "username": "saif",
    "password": "123"
})
token = login_res.json()["token"]
headers = {"Authorization": f"Bearer {token}"}

# 2. Trigger Satellite ML Detection
job_res = requests.post(f"{BASE_URL}/run-detection", params={
    "lat": 25.6124,
    "lon": 85.1376,
    "cloud_cover": 10.0
})
job_id = job_res.json()["job_id"]
print(f"Triggered detection job: {job_id}")

# 3. Poll for completion
while True:
    status_res = requests.get(f"{BASE_URL}/status/{job_id}").json()
    print(f"Step: {status_res.get('current_step')} — Status: {status_res['status']}")
    if status_res["status"] == "complete":
        result = status_res["result"]
        print(f"Confidence: {result['confidence_score']}% | Area: {result['area_sq_km']} km² | Severity: {result['severity']}")
        break
    time.sleep(2)
```

### JavaScript / TypeScript (`fetch`)
```typescript
const BASE_URL = 'http://localhost:8000/api';

async function fetchNowcast(lat: number, lon: number) {
  const response = await fetch(`${BASE_URL}/nowcast?lat=${lat}&lon=${lon}&drainage_eff=70`);
  const data = await response.json();
  
  if (data.status === 'SUCCESS') {
    console.log(`Max depth in 60 min: ${data.urnn_nowcast.max_depth_60m} meters`);
    console.log(`Evacuation Route ETA: ${data.dynamic_evacuation_route.eta_minutes} minutes`);
    console.log(`Avoided water hazards: ${data.dynamic_evacuation_route.avoided_flooded_nodes_count} nodes`);
  }
}
```

### cURL
```bash
# Query the RAG AI Emergency Assistant
curl -X POST "http://localhost:8000/api/agent/chat" \
     -H "Content-Type: application/json" \
     -d '{
       "message": "Where is the nearest shelter and what is the current water level?"
     }'
```
