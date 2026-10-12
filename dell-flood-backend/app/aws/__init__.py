"""
Aegis AWS Cloud Integration Package (100% Free Tier & AWS Agent Toolkit MCP Ready).
Provides dual-mode (Live AWS + Graceful Local Fallback) services for all 12 AWS Free Tier services:
1. Amazon S3 (SITREP PDF reports, 4D Nowcast heatmaps, pre-signed URLs)
2. Amazon DynamoDB (Citizen Ground Reports, Emergency Shelters & MCP Audit Ledger)
3. Amazon SNS (Mass Emergency SMS & CAP v1.2 Topic Broadcasts)
4. Amazon Polly (Neural Bilingual Hindi/English Voice Synthesis)
5. Amazon Cognito (Cryptographic OIDC/JWT Authentication & Role RBAC)
6. Amazon CloudWatch (Real-Time Telemetry, Custom Metrics & Disaster Dashboards)
7. Amazon Bedrock Runtime & Knowledge Bases (Claude 3 Haiku SITREP LLM & NDMA SOP RAG)
8. Amazon Location Service (Place Index Geocoding, Evacuation Routing & Flood Geofencing)
9. Amazon Translate & Amazon Comprehend (7-Language Indian Advisory Translation & SOS NLP Triage)
10. Amazon Rekognition (Crowdsourced Flood Photo Verification & Anti-Spoofing)
11. Amazon EventBridge & AWS Step Functions (Event Bus & 6-Agent State Machine Orchestration)
12. Amazon SQS & AWS SSM Parameter Store (FIFO SOS Burst Queue & Dynamic Operational Thresholds)
"""

from .s3_service import s3_service, S3DisasterStorage
from .dynamodb_service import dynamodb_service, DynamoDBTelemetryStore
from .sns_service import sns_service, SNSEmergencyBroadcaster
from .polly_service import polly_service, PollyVoiceSynthesizer
from .cognito_service import cognito_service, CognitoAuthVerifier
from .cloudwatch_service import cloudwatch_service, CloudWatchTelemetry
from .bedrock_service import bedrock_service, BedrockDisasterIntelligence
from .location_service import location_service, LocationDisasterService
from .ai_language_service import ai_language_service, AILanguageDisasterService
from .rekognition_service import rekognition_service, RekognitionFloodVerifier
from .events_sfn_service import events_sfn_service, EventBridgeStepFunctionsOrchestrator
from .sqs_ssm_service import sqs_ssm_service, SQSAndSSMConfigService

__all__ = [
    "s3_service",
    "S3DisasterStorage",
    "dynamodb_service",
    "DynamoDBTelemetryStore",
    "sns_service",
    "SNSEmergencyBroadcaster",
    "polly_service",
    "PollyVoiceSynthesizer",
    "cognito_service",
    "CognitoAuthVerifier",
    "cloudwatch_service",
    "CloudWatchTelemetry",
    "bedrock_service",
    "BedrockDisasterIntelligence",
    "location_service",
    "LocationDisasterService",
    "ai_language_service",
    "AILanguageDisasterService",
    "rekognition_service",
    "RekognitionFloodVerifier",
    "events_sfn_service",
    "EventBridgeStepFunctionsOrchestrator",
    "sqs_ssm_service",
    "SQSAndSSMConfigService",
]
