# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Aegis is a flood detection and disaster-response prototype with two parts:

- `dell-flood-backend/`: Python FastAPI service. It runs Sentinel-1/2 imagery fetch, a SegFormer SAR+optical fusion model, post-processing, a heuristic depth "nowcast", an agent pipeline, an MCP tool server, and AWS service wrappers.
- `dell-flood-app/`: Expo (SDK 57) / React Native app for web and mobile, with citizen and official dashboards.

`dell-flood-app/CLAUDE.md` → `AGENTS.md` says: **Expo has changed. Read the versioned docs at https://docs.expo.dev/versions/v57.0.0/ before writing any frontend code.**

Root-level `*.md` files (`features.md`, `fixes.md`, `solution_implementation_doc.md`, `urnn_integration_plan.md`, `AWS_INTEGRATION_PLAN.md`, `awsplan.md`) and much of `README.md` are design specs written as if they were implemented. Verify any claim against the code before relying on it. `FloodApp_Analysis.md` is an external audit.

## Commands

Backend (run from `dell-flood-backend/`):

```bash
python -m venv venv && source venv/bin/activate     # Windows: .\venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload   # API at :8000, Swagger at /docs
python -m app.mcp.aegis_mcp_server                               # stdio MCP server (JSON-RPC over stdin/stdout)
```

Tests are plain scripts, not a pytest suite. Each has a `__main__` block, and the functions are named `test_*`, so pytest can also collect them:

```bash
python test_backend.py                 # ML inference / post-processing / RAG smoke checks
python test_aws_mcp_free_tier.py       # MCP registry + AWS diagnostic suite + stdio MCP
python verify_endpoints.py             # needs the server already running on localhost:8000
python -m pytest test_backend.py::test_post_processing   # run a single function
```

Warning: `test_aws_mcp_free_tier.py` runs `aws_run_free_tier_diagnostic_suite`. With real AWS credentials in `.env`, that sends a real SNS broadcast and provisions resources.

Frontend (run from `dell-flood-app/`):

```bash
npm install
npm run web                 # expo start --web (localhost:8081)
npx expo start --lan        # Expo Go on a phone on the same Wi-Fi
npm run export:web          # static web export
npx tsc --noEmit            # type check (there is no lint or test script)
npx eas-cli build --platform android --profile preview   # APK
```

The app finds the backend through `EXPO_PUBLIC_API_URL`. On web, `src/services/api.ts` derives it from `window.location.hostname:8000/api`. It can also be changed at runtime from the Settings panel (stored in AsyncStorage).

## Backend architecture

- **Entry:** `main.py` mounts `app/api/endpoints.py` (`router`, prefix `/api`) and `app/mcp/aegis_mcp_server.py` (`mcp_router`).
- **Import-time side effects:** importing `endpoints.py` creates the SQLite tables and seed users/shelters (`init_db()`), loads the SegFormer singleton and the U-RNN, and builds `FloodAgent` and the RAG generator (ChromaDB + `corpus/`). Any script that imports it pays that cost.
- **Two SQLite files:**
  - `flood_database.db`, relative to the working directory: users, complaints, shelters. Used by `endpoints.py`.
  - `flood_app.db`, absolute path: the `hitl_approvals` table. Used by `agent/incident_orchestrator.py`.

### There are two detection paths, and they don't share inputs

1. **`POST /api/run-detection` → `run_pipeline_task`** (background task; progress is polled through `GET /api/status/{job_id}` from an in-memory `jobs` dict).
   - Fetches real Sentinel Hub data via `download_sentinel_data`: S2 L2A RGB+NIR and S1 GRD VV/VH in dB, a 0.05° bbox, 512×512, UINT8-encoded.
   - Then: permanent-water baseline (`download_permanent_water_baseline`), DEM check, hydro tensor, U-RNN, spread polygons, OSM impact, contour polygonization, and a grid-based route.
   - Each step appends to `steps_completed`, which the UI renders as a 16-step log.
2. **Agent path: `POST /api/agent-cycle` → `FloodAgent.run_cycle` (`agent/flood_agent.py`) → `MultiAgentIncidentOrchestrator.run_incident_graph` (`agent/incident_orchestrator.py`).**
   - A fixed, sequential set of "agent" steps. It is not a LangGraph graph despite the naming.
   - Every step goes through `execute_mcp_tool(name, args)` in `app/mcp/aegis_mcp_server.py`. That function is one large `if/elif` dispatcher, and it records a SHA-256 "provenance" entry for each call.
   - The MCP `run_flood_segmentation` tool uses `agent/tools.py::fetch_satellite`, which builds Esri basemap tiles plus synthetic SAR, **not** the Sentinel Hub path above. Keep this split in mind when changing either path.

### Model and post-processing

- `app/ml/inference.py`: `SegFormerMiTB2Fusion` is two `transformers` SegFormer MiT-B2 encoders (2-channel SAR, 4-channel RGB+NIR), with gated fusion at stages 1–2, cross-attention at stages 3–4, an FPN decoder, and boundary refinement. It must match the training code in `notebook_source.ipynb` (a Kaggle `.py` export despite the extension; Sen1Floods11, S2 reflectance ÷10000, S1 in dB).
- Weights (`best_model_focal.pth`) are not in git. They are looked up via `MODEL_WEIGHTS_PATH` or several relative paths and loaded with `strict=True` (a legacy key remap is attempted). Without weights, `run_inference` raises rather than returning fake output. Use `get_shared_model()`; don't instantiate a second model.
- `app/ml/postprocess.py`: permanent-water filtering, DEM fetch (a 5×5 Open-Meteo sample, upsampled), connected components, area/severity classification.
- `app/ml/urnn_nowcaster.py` + `app/aegis/pipeline/dynamic_hydro_tensor.py`: depth "nowcast". The ConvGRU/YOLOX layers have no trained weights, so the depth comes from a hand-written formula.
- `app/aegis/`: legacy US-centric MirEye modules (TWI, triage, shelters, routing). It inserts its own directory into `sys.path` (`app/aegis/__init__.py`), so the modules import each other as top-level `api.*`, `pipeline.*`, `routing.*`, `shelters.*`. `triage_engine.py` uses the US county data in `us_counties_flood_predictions.json`.

### Alerts, approval gate, and auth

- Outbound channels: Twilio SMS/voice (`agent/tools.py`, TwiML built with `VoiceResponse`), SMTP (`send_smtp_email`, recipient forced to `ALERT_RECIPIENT_EMAIL`), Expo push, AWS SNS/Polly.
- Human approval (HITL): the orchestrator saves a CAP v1.2 draft to `hitl_approvals`. `POST /api/hitl/approve` → `approve_and_dispatch_hitl` sends it. Alerts can still go out without approval:
  - `AgentCycleRequest.require_hitl_for_calls` defaults to `False`, which auto-approves the call;
  - `run_cycle` broadcasts on SNS unconditionally.
- Auth helpers live in `app/api/auth_deps.py`: PBKDF2 hashing, an HS256 JWT, `require_official`, `escape_html`, `slugify_location`, `normalize_and_validate_phone`. `get_current_user` falls back to a demo official unless `STRICT_AUTH=true`, and **no route currently uses `require_official`**.
- The frontend stores the token (`aegis_jwt_token` in AsyncStorage) but does not send it.

### AWS layer (`app/aws/`)

There is one module per service (S3, DynamoDB, SNS, Polly, Cognito, CloudWatch, Bedrock, Location, Translate/Comprehend, Rekognition, EventBridge/Step Functions, SQS/SSM, provisioner). Each module-level singleton checks for real credentials and otherwise returns a **simulated** response, usually with a `*_SIMULATED` provider/status field. Callers generally don't distinguish simulated from real results. The provisioner entry point is `aws_provisioner.provision_all()`. `.mcp.json` points at this MCP server (with machine-specific `cwd` paths) and at several `awslabs.*` MCP servers.

### Report generation

`app/RAG/generator.py` (`SituationReportGenerator`) retrieves context from ChromaDB (`vector_store.py`, ingesting `corpus/*.txt|md|pdf` only when the collection is empty). It then tries Gemini → Groq → OpenAI → Anthropic → Bedrock → a local template, and appends a numeric "grounding" footer. PDFs are built with ReportLab in `endpoints.py` and `tools.export_pdf`.

## Frontend architecture

- `App.tsx` holds most of the app: auth screens, role-based dashboards (`citizen` / `official`), hand-rolled tab navigation (`activeTab`), notifications, and large StyleSheets.
- `src/services/api.ts` (`apiService`) is the single API client. It also contains mock data:
  - mock complaints and shelters;
  - mock users, used only when `useMock` is on;
  - a fabricated agent-cycle result returned when the backend call fails;
  - local merging of offline/mock reports into the official complaint list.
- Maps (`MapView.tsx`, `NowcastPanel.tsx`) build a full Leaflet HTML document as a template string, rendered in an `<iframe srcDoc>` on web and a `react-native-webview` on native. They communicate via `postMessage`. Any data interpolated into that HTML/script must be escaped (there is an `escapeHtml` inside the template).
- `src/utils/i18n.ts` provides en/hi strings. `src/utils/routing.ts` is unused.

## Environment

Backend keys in `dell-flood-backend/.env.example`:
- `SENTINEL_CLIENT_ID` / `SENTINEL_CLIENT_SECRET`: required for `/run-detection` and `/preview`.
- `GEMINI_API_KEY` / `GROQ_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`
- `TWILIO_*`
- `AWS_*`
- `MODEL_WEIGHTS_PATH`, `CHROMA_DB_PATH`

Read by the code but missing from `.env.example`:
- `SMTP_SENDER_EMAIL`, `SMTP_SENDER_PASSWORD`, `ALERT_RECIPIENT_EMAIL`
- `JWT_SECRET_KEY` (only in the root `.env.example`)
- `STRICT_AUTH`
- `ALLOWED_ORIGINS` (default includes `*`)
- `AWS_COGNITO_FALLBACK_SECRET`
- `MIREYE_API_TOKEN`

`CWC_API_KEY` and `SENDGRID_*` appear in the template but nothing reads them.
