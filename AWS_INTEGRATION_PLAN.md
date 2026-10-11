# Final Implementation Plan: AWS Free Tier & AWS Agent Toolkit (MCP) Integration for Aegis

## Goal Description
Integrate a complete suite of **100% Free Tier AWS Cloud Services** into the **Aegis** flood detection and autonomous disaster response platform. 

This comprehensive plan covers:
1. **Amazon S3** — Durable cloud storage for SITREP PDF reports, 4D nowcast heatmaps, and frontend web hosting.
2. **Amazon SNS** — Mass broadcast emergency SMS and push alerts for civilians and NDRF/SDRF teams.
3. **Amazon Cognito** — Cryptographic JWT authentication with role-based access (`IncidentCommander` vs. `Citizen`).
4. **Amazon CloudWatch** — Real-time telemetry, flood severity metrics, and operational judge dashboards.
5. **Amazon DynamoDB** — Serverless, zero-lock NoSQL storage for real-time citizen ground reports and shelter availability.
6. **Amazon Polly** — Broadcast-quality bilingual (Hindi & English) emergency audio voice generation.
7. **Amazon CloudFront** — Global, sub-second CDN delivery for the Expo web application.
8. **AWS Agent Toolkit & AWS MCP Server** — Standardized MCP tooling bridge with IAM guardrails and CloudWatch audit logs.

All components are configured with **zero-crash dual-mode architecture** (active AWS execution when credentials exist, seamless graceful local simulation fallback when offline).

---

## User Review Required

> [!IMPORTANT]
> **No Paid AWS Services Required:**
> Every service in this plan operates strictly within the **AWS Always Free Tier** (DynamoDB, SNS, Cognito, CloudWatch, SSM) or the **AWS 12-Month Free Tier** (S3, Polly, CloudFront).
> 
> **Zero Cost Guarantee:**
> - Amazon DynamoDB: 25 GB storage + 25 RCU/WCU (Forever Free)
> - Amazon SNS: 1,000,000 publishes/month (Forever Free)
> - Amazon Cognito: 50,000 Monthly Active Users (Forever Free)
> - Amazon CloudWatch: 3 Dashboards, 10 Metrics, 5 GB logs (Forever Free)
> - Amazon S3: 5 GB Standard Storage (12-Mo Free)
> - Amazon Polly: 5,000,000 characters/month (12-Mo Free)
> - Amazon CloudFront: 1 TB data transfer + 10M requests/month (12-Mo Free)

---

## Master Architecture Diagram

```
                                [Citizens & Incident Commanders]
                             (Expo Mobile App / CloudFront Web PWA)
                                               │
                                ┌──────────────┴──────────────┐
                                │                             │
                 [1. Auth via Cognito JWT]       [2. CloudFront CDN + S3 Web]
                                │                             │
                                ▼                             ▼
                    [Amazon Cognito User Pool]        [Amazon CloudFront CDN]
                    (Citizen & Commander Groups)     (Global Fast Edge Delivery)
                                                              │
                                                              ▼
                                                   [FastAPI Backend :8000]
                                                  (Dual-Mode AWS Controller)
                                                              │
                                               [Autonomous 6-Agent Pipeline]
                                              (Ingest➔Seg➔Hydro➔Triage➔Route➔Alert)
                                                              │
       ┌───────────────────┬───────────────────┼───────────────────┬───────────────────┐
       ▼                   ▼                   ▼                   ▼                   ▼
 [3. Amazon S3]     [4. DynamoDB]       [5. Amazon SNS]     [6. Amazon Polly]   [7. CloudWatch]
 - SITREP PDFs      - Ground Reports    - Evacuation SMS    - Hindi Siren Audio - Live Severity
 - 4D Heatmaps      - Safe Shelters     - First Responders  - English Broadcast - Latency Metrics
 - Pre-signed URLs  - No Lock Contention- Mass Broadcast    - Neural Voices     - Judge Dashboards
       │                   │                   │                   │                   │
       └───────────────────┴───────────────────┼───────────────────┴───────────────────┘
                                               │
                                               ▼
                             [8. AWS Agent Toolkit & AWS MCP Server]
                             - FastMCP Tool Bridge at /api/mcp/tools
                             - Sandboxed Execution with IAM Guardrails
                             - Automatic CloudWatch Audit Logging
```

---

## Detailed Component Specifications

### Component 1: Amazon S3 (Storage & Distribution)
* **Target Files:**
  - `[NEW] dell-flood-backend/app/aws/s3_service.py`
  - `[MODIFY] dell-flood-backend/app/agent/flood_agent.py`
  - `[MODIFY] dell-flood-backend/app/api/endpoints.py`
* **Features:**
  - `upload_sitrep_pdf(file_path, report_id)`: Vaults PDF reports to S3 bucket `aegis-disaster-vault`.
  - `upload_nowcast_raster(png_bytes, location, timestamp)`: Stores 4D ConvGRU depth heatmaps.
  - `get_presigned_url(s3_key, expires_in=86400)`: Generates secure 24-hour links for alert messages.

---

### Component 2: Amazon DynamoDB (Serverless Ground Telemetry)
* **Target Files:**
  - `[NEW] dell-flood-backend/app/aws/dynamodb_service.py`
  - `[MODIFY] dell-flood-backend/app/api/endpoints.py` (`/api/complaints`)
* **Features:**
  - Table 1: `Aegis-Citizen-Reports` (Partition Key: `report_id`, Sort Key: `timestamp`)
    - Ingests water depth, coordinates, severity, status, and citizen handle.
  - Table 2: `Aegis-Emergency-Shelters` (Partition Key: `shelter_id`)
    - Tracks live shelter occupancy, capacity, DEM elevation, and contact numbers.
  - Fallback: Local JSON/SQLite storage when AWS credentials are not set.

---

### Component 3: Amazon SNS (Mass Disaster Alert Broadcast)
* **Target Files:**
  - `[NEW] dell-flood-backend/app/aws/sns_service.py`
  - `[MODIFY] dell-flood-backend/app/agent/tools.py` (`trigger_emergency_alert`, `send_sms_alert`)
  - `[MODIFY] dell-flood-backend/app/api/endpoints.py` (`/api/alerts/broadcast-sns`)
* **Features:**
  - Publishes to `Aegis-Flash-Flood-Alerts` Topic with geolocation, projected depth, and safe evacuation URLs.
  - Broadcasts simultaneously to all registered phones and SMS endpoints.

---

### Component 4: Amazon Polly (Neural Bilingual Audio Dispatch)
* **Target Files:**
  - `[NEW] dell-flood-backend/app/aws/polly_service.py`
  - `[MODIFY] dell-flood-backend/app/agent/tools.py`
  - `[MODIFY] dell-flood-backend/app/api/endpoints.py` (`/api/alerts/voice-audio`)
* **Features:**
  - Uses neural engine:
    - Hindi: Voice `Aditi` or `Kajal` for clear North/East India disaster bulletins.
    - Indian English: Voice `Raveena` for bilingual clarity.
  - Synthesizes MP3 streams directly saved to S3 or returned to the mobile app for immediate playback.

---

### Component 5: Amazon CloudFront & S3 Web Distribution
* **Target Deployment:**
  - Build script in `dell-flood-app/package.json` (`npm run export:web`).
  - S3 static web hosting bucket (`aegis-web-portal`).
  - CloudFront distribution providing global SSL HTTPS access (`https://dXXXXXXXX.cloudfront.net`).
  - Eliminates laptop dependency; judges can open the dashboard on any device.

---

### Component 6: Amazon Cognito (Role-Based JWT Security)
* **Target Files:**
  - `[NEW] dell-flood-backend/app/aws/cognito_service.py`
  - `[MODIFY] dell-flood-backend/app/api/auth_deps.py`
  - `[MODIFY] dell-flood-backend/app/api/endpoints.py` (`/api/auth/*`)
* **Features:**
  - Validates cryptographically signed RSA tokens using Cognito's public JWKS.
  - Enforces roles:
    - `IncidentCommander`: Authorized to run agent cycles and trigger mass alerts.
    - `Citizen`: Authorized to submit ground reports and query safe routes.

---

### Component 7: Amazon CloudWatch (Live Observability & Dashboards)
* **Target Files:**
  - `[NEW] dell-flood-backend/app/aws/cloudwatch_service.py`
  - `[MODIFY] dell-flood-backend/app/agent/incident_orchestrator.py`
  - `[MODIFY] dell-flood-backend/app/ml/urnn_nowcaster.py`
* **Features:**
  - Emits real-time metrics:
    - `Aegis/FloodSeverityIndex`
    - `Aegis/ActiveEvacuationRoutes`
    - `Aegis/CitizenReportsIngested`
    - `Aegis/NowcastInferenceLatencyMs`
  - Provides a pre-configured dashboard ready to show during the hackathon pitch.

---

### Component 8: AWS Agent Toolkit & AWS MCP Server Bridge
* **Target Files:**
  - `[MODIFY] dell-flood-backend/app/mcp/aegis_mcp_server.py`
* **Features:**
  - Exposes AWS disaster tools through our existing FastMCP server at `/api/mcp/tools`:
    - `aws_upload_report_s3(report_id, filename)`
    - `aws_record_ground_report_dynamodb(report_json)`
    - `aws_broadcast_alert_sns(location, severity)`
    - `aws_synthesize_voice_polly(text, language)`
    - `aws_get_cloudwatch_metrics()`
  - Full compatibility with Claude Code, Kiro, Codex, and Aegis LangGraph agents.

---

## Proposed Project Directory Layout After Integration

```
dell-flood-backend/
├── app/
│   ├── aws/                                # [NEW] Centralized AWS Service Clients
│   │   ├── __init__.py                     # Package init
│   │   ├── s3_service.py                   # Amazon S3 storage & presigned URLs
│   │   ├── dynamodb_service.py             # Amazon DynamoDB citizen reports & shelters
│   │   ├── sns_service.py                  # Amazon SNS mass SMS broadcast
│   │   ├── polly_service.py                # Amazon Polly Hindi/English neural TTS
│   │   ├── cognito_service.py              # Amazon Cognito JWT verification
│   │   └── cloudwatch_service.py           # Amazon CloudWatch metrics telemetry
│   ├── agent/
│   │   ├── tools.py                        # Updated with SNS & Polly dispatch
│   │   └── incident_orchestrator.py        # Updated with CloudWatch metric emissions
│   ├── api/
│   │   ├── auth_deps.py                    # Updated with Cognito JWT verification
│   │   └── endpoints.py                    # Updated with S3, DynamoDB, SNS routes
│   └── mcp/
│       └── aegis_mcp_server.py             # Updated with AWS MCP Bridge tools
```

---

## Environment Variables Configuration (`.env.example`)

```ini
# ==========================================
# AEGIS AWS CLOUD CONFIGURATION (FREE TIER)
# ==========================================
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_DEFAULT_REGION=ap-south-1

# Amazon S3
AWS_S3_BUCKET=aegis-disaster-vault

# Amazon DynamoDB
AWS_DYNAMODB_REPORTS_TABLE=Aegis-Citizen-Reports
AWS_DYNAMODB_SHELTERS_TABLE=Aegis-Emergency-Shelters

# Amazon SNS
AWS_SNS_TOPIC_ARN=arn:aws:sns:ap-south-1:123456789012:Aegis-Flash-Flood-Alerts

# Amazon Cognito
AWS_COGNITO_USER_POOL_ID=ap-south-1_xxxxxxxxx
AWS_COGNITO_APP_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## Step-by-Step Implementation Sequence

1. **Step 1: Install AWS SDK (`boto3`)** in `dell-flood-backend/.venv-local`.
2. **Step 2: Create `dell-flood-backend/app/aws/` package** with 6 modular, dual-mode service handlers (`s3_service.py`, `dynamodb_service.py`, `sns_service.py`, `polly_service.py`, `cognito_service.py`, `cloudwatch_service.py`).
3. **Step 3: Connect S3 & DynamoDB** into `flood_agent.py` and `endpoints.py` for persistent reports and citizen telemetry.
4. **Step 4: Connect SNS & Polly** into `tools.py` for automated bilingual mass voice/SMS alerting.
5. **Step 5: Connect CloudWatch** into `incident_orchestrator.py` for live judge dashboard metrics.
6. **Step 6: Expose AWS Tools in FastMCP Server** (`aegis_mcp_server.py`) for AWS Agent Toolkit compatibility.
7. **Step 7: Automated Verification & Regression Testing** to ensure 100% build health with and without AWS credentials.

---

## Verification Plan

### Automated Verification
```powershell
# 1. Verify boto3 installation
& "dell-flood-backend\.venv-local\Scripts\python.exe" -c "import boto3; print('boto3 OK')"

# 2. Test AWS Service Module Fallbacks (Zero crash test)
& "dell-flood-backend\.venv-local\Scripts\python.exe" -c "from app.aws.s3_service import s3_service; from app.aws.dynamodb_service import dynamodb_service; from app.aws.sns_service import sns_service; from app.aws.polly_service import polly_service; from app.aws.cloudwatch_service import cloudwatch_service; print('All AWS services loaded cleanly with fallback!')"

# 3. Test API Endpoints & MCP Tools
& "dell-flood-backend\.venv-local\Scripts\python.exe" -c "from app.mcp.aegis_mcp_server import mcp; print(f'MCP Tools Count: {len(mcp.list_tools())}')"
```

### Manual Verification
1. Run backend (`python -m uvicorn main:app`) and frontend (`npx expo start --web`).
2. Submit a ground report and verify it is logged in DynamoDB (or simulated offline queue).
3. Trigger an agent cycle and verify SITREP PDF is vaulted to S3 and metrics appear in CloudWatch.
4. Trigger an emergency alert and verify Polly audio synthesis and SNS topic dispatch.
