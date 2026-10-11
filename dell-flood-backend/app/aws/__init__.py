"""
Aegis AWS Cloud Integration Package (Free Tier & AWS Agent Toolkit MCP Ready).
Provides dual-mode (Live AWS + Graceful Local Fallback) services for:
- Amazon S3 (SITREP PDF reports, 4D Nowcast heatmaps, pre-signed URLs)
- Amazon DynamoDB (Citizen Ground Reports & Emergency Shelters)
- Amazon SNS (Mass Emergency SMS & Push Broadcasts)
- Amazon Polly (Neural Bilingual Hindi/English Voice Synthesis)
- Amazon Cognito (Cryptographic OIDC/JWT Authentication & Role RBAC)
- Amazon CloudWatch (Real-Time Telemetry & Disaster Metrics)
"""

from .s3_service import s3_service, S3DisasterStorage
from .dynamodb_service import dynamodb_service, DynamoDBTelemetryStore
from .sns_service import sns_service, SNSEmergencyBroadcaster
from .polly_service import polly_service, PollyVoiceSynthesizer
from .cognito_service import cognito_service, CognitoAuthVerifier
from .cloudwatch_service import cloudwatch_service, CloudWatchTelemetry

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
]
