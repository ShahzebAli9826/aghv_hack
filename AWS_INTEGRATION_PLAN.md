# Master AWS Free Tier & AWS MCP Server Integration Guide for Aegis

## Executive Summary
Aegis integrates **12 AWS Free Tier Cloud Services** exposed through **15 formal Model Context Protocol (MCP) tools** (`aegis-flood-mcp-server` v2.0.0) over both **JSON-RPC 2.0 `stdio` transport** and **FastAPI REST (`/api/mcp/*`)**. Every service is engineered with a **Dual-Mode Architecture** (live `boto3` AWS cloud execution when credentials are configured, and zero-crash local simulation fallback when offline).

---

## Complete AWS Free Tier Services Matrix (12 Services)

| # | AWS Service | Free Tier Allowance | Module | MCP Tool Name(s) | Role in Aegis Flood Platform |
|---|---|---|---|---|---|
| 1 | **Amazon S3** | 5 GB Standard Storage, 20K GET, 2K PUT/mo (12-Mo Free) | [`s3_service.py`](file:///e:/hackthon/awswemakedev/dell-flood-backend/app/aws/s3_service.py) | `aws_upload_report_s3` | Vaults SITREP PDF reports, 4D ConvGRU nowcast rasters, and generates 24h pre-signed URLs |
| 2 | **Amazon DynamoDB** | 25 GB Storage + 25 RCU/25 WCU (Always Free Forever) | [`dynamodb_service.py`](file:///e:/hackthon/awswemakedev/dell-flood-backend/app/aws/dynamodb_service.py) | `aws_record_ground_report_dynamodb`, `aws_manage_shelters_dynamodb` | Persists citizen ground reports (`Aegis-Citizen-Reports`), relief shelters (`Aegis-Emergency-Shelters`), and SHA-256 MCP audit logs (`Aegis-MCP-Audit-Ledger`) |
| 3 | **Amazon SNS** | 1,000,000 Publishes/mo (Always Free Forever) | [`sns_service.py`](file:///e:/hackthon/awswemakedev/dell-flood-backend/app/aws/sns_service.py) | `aws_broadcast_alert_sns` | Publishes geofenced CAP v1.2 flash-flood emergency broadcasts to citizens & NDRF/SDRF responders |
| 4 | **Amazon Polly** | 5,000,000 Characters/mo (12-Mo Free Tier) | [`polly_service.py`](file:///e:/hackthon/awswemakedev/dell-flood-backend/app/aws/polly_service.py) | `aws_synthesize_voice_polly` | Synthesizes bilingual Hindi (`Aditi`) and Indian English (`Raveena`) neural emergency voice alerts |
| 5 | **Amazon Cognito** | 50,000 MAUs (Always Free Forever) | [`cognito_service.py`](file:///e:/hackthon/awswemakedev/dell-flood-backend/app/aws/cognito_service.py) | `aws_verify_cognito_identity` | Cryptographic OIDC/JWT token issuance & RBAC (`IncidentCommanders` vs. `Citizens`) |
| 6 | **Amazon CloudWatch** | 3 Dashboards, 10 Custom Metrics, 5 GB Logs (Always Free) | [`cloudwatch_service.py`](file:///e:/hackthon/awswemakedev/dell-flood-backend/app/aws/cloudwatch_service.py) | `aws_get_cloudwatch_metrics` | Streams `FloodSeverityIndex`, `ActiveEvacuationRoutes`, `NowcastLatencyMs`, and `CitizenReportsIngested` to `Aegis/DisasterResponse` |
| 7 | **Amazon Bedrock & Knowledge Bases** | Pay-per-token / AWS Credits (~$0.0007/report) | [`bedrock_service.py`](file:///e:/hackthon/awswemakedev/dell-flood-backend/app/aws/bedrock_service.py) | `aws_generate_sitrep_bedrock` | Generates grounded NDMA/UN-OCHA/SDMA SITREPs via Claude 3 Haiku (`anthropic.claude-3-haiku-20240307-v1:0`) & retrieves NDMA SOPs |
| 8 | **Amazon Location Service** | 10K Geocode + 10K Routes + 10K Geofences/mo (Free Tier) | [`location_service.py`](file:///e:/hackthon/awswemakedev/dell-flood-backend/app/aws/location_service.py) | `aws_location_geofence_and_route` | Geocodes Indian flood-zone villages, computes flood-avoiding evacuation routes, and evaluates polygon geofences |
| 9 | **Amazon Translate & Comprehend** | 2M Chars Translate + 50K Units Comprehend (12-Mo Free) | [`ai_language_service.py`](file:///e:/hackthon/awswemakedev/dell-flood-backend/app/aws/ai_language_service.py) | `aws_translate_emergency_bulletin`, `aws_triage_sos_comprehend` | Translates CAP alerts into 7 Indian languages (`hi`, `as`, `bn`, `or`, `mr`, `ta`, `en`) & extracts SOS trapped headcount/urgency |
| 10 | **Amazon Rekognition** | 5,000 Images/mo (12-Mo Free Tier) | [`rekognition_service.py`](file:///e:/hackthon/awswemakedev/dell-flood-backend/app/aws/rekognition_service.py) | `aws_verify_flood_photo_rekognition` | Verifies citizen flood photos via `detect_labels` and spectral water ratio anti-spoofing |
| 11 | **Amazon EventBridge & Step Functions** | 14M Events + 4,000 State Transitions/mo (Always Free) | [`events_sfn_service.py`](file:///e:/hackthon/awswemakedev/dell-flood-backend/app/aws/events_sfn_service.py) | `aws_orchestrate_step_functions` | Emits `FloodAnomalyDetected` events to `aegis-disaster-event-bus` and orchestrates the 6-Agent State Machine |
| 12 | **Amazon SQS FIFO & AWS SSM Store** | 1M SQS Requests + 10K SSM Parameters (Always Free) | [`sqs_ssm_service.py`](file:///e:/hackthon/awswemakedev/dell-flood-backend/app/aws/sqs_ssm_service.py) | `aws_queue_and_ssm_config` | Buffers flash-flood SOS bursts in `Aegis-SOS-Triage-Queue.fifo` and manages `/aegis/prod/*` dynamic thresholds |

---

## Testing Everything via AWS MCP Server

### 1. Run the Automated AWS Free Tier MCP Verification Suite
```powershell
cd dell-flood-backend
python test_aws_mcp_free_tier.py
```

### 2. Invoke via FastAPI MCP Bridge (`POST /api/mcp/execute` or `POST /api/aws/test-mcp-suite`)
```powershell
curl -X POST http://localhost:8000/api/aws/test-mcp-suite
```

### 3. Invoke via JSON-RPC 2.0 STDIO MCP Transport
Configured in [`.mcp.json`](file:///e:/hackthon/awswemakedev/.mcp.json) alongside official `awslabs` MCP servers (`awslabs.core-mcp-server`, `awslabs.aws-documentation-mcp-server`, `awslabs.dynamodb-mcp-server`, `awslabs.aws-location-mcp-server`).
