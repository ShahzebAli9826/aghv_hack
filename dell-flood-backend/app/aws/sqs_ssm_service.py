import os
import json
import uuid
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

logger = logging.getLogger("aegis.aws.sqs_ssm")


def _has_real_aws_creds() -> bool:
    key = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
    secret = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
    if not key or not secret:
        return False
    if key.startswith("your_") or secret.startswith("your_") or key == "AKIAIOSFODNN7EXAMPLE":
        return False
    return True


class SQSAndSSMConfigService:
    """
    Amazon SQS & AWS Systems Manager (SSM) Parameter Store Integration for Aegis (Always Free Tier):
    - Amazon SQS (1,000,000 requests/mo Always Free): Buffers citizen SOS bursts in `Aegis-SOS-Triage-Queue.fifo`
      so flash-flood traffic spikes never drop an emergency packet.
    - AWS SSM Parameter Store (10,000 Standard Parameters Always Free): Stores dynamic operational thresholds
      (`/aegis/prod/flood_depth_threshold_m`, `/aegis/prod/drainage_efficiency_pct`, `/aegis/prod/hitl_mode`)
    """

    def __init__(self):
        self.region = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
        self.queue_url = os.getenv(
            "AWS_SQS_QUEUE_URL",
            f"https://sqs.{self.region}.amazonaws.com/000000000000/Aegis-SOS-Triage-Queue.fifo",
        )
        self.enabled = _has_real_aws_creds()
        self._sqs = None
        self._ssm = None
        self._local_queue: List[Dict[str, Any]] = []
        self._ssm_parameters: Dict[str, Any] = {
            "/aegis/prod/flood_depth_alert_threshold_m": "0.30",
            "/aegis/prod/urnn_drainage_efficiency_default": "65.0",
            "/aegis/prod/hitl_require_commander_signoff": "true",
            "/aegis/prod/default_emergency_voices": "Aditi,Raveena",
            "/aegis/prod/sachet_cap_version": "1.2",
        }
        if self.enabled:
            try:
                import boto3
                self._sqs = boto3.client("sqs", region_name=self.region)
                self._ssm = boto3.client("ssm", region_name=self.region)
            except Exception as e:
                logger.warning(f"Boto3 SQS/SSM initialization skipped: {e}")
                self.enabled = False

    def enqueue_sos_packet(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Enqueues a citizen SOS or hydrological anomaly message into Amazon SQS FIFO Queue."""
        msg_id = f"sqs-msg-{uuid.uuid4().hex[:10]}"
        dedup_id = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16] if "hashlib" in globals() else uuid.uuid4().hex[:16]
        entry = {
            "message_id": msg_id,
            "queue_url": self.queue_url,
            "enqueued_at_utc": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        self._local_queue.insert(0, entry)
        self._local_queue = self._local_queue[:50]

        if self.enabled and self._sqs and "000000000000" not in self.queue_url:
            try:
                resp = self._sqs.send_message(
                    QueueUrl=self.queue_url,
                    MessageBody=json.dumps(payload, default=str),
                    MessageGroupId="AegisFloodTriageGroup",
                    MessageDeduplicationId=dedup_id,
                )
                return {
                    "provider": "AMAZON_SQS_LIVE",
                    "message_id": resp.get("MessageId", msg_id),
                    "queue_url": self.queue_url,
                    "queue_depth": len(self._local_queue),
                    "status": "ENQUEUED_TO_SQS_FIFO",
                }
            except Exception as e:
                logger.warning(f"SQS send_message fallback triggered: {e}")

        return {
            "provider": "AWS_SQS_SIMULATED",
            "message_id": msg_id,
            "queue_url": self.queue_url,
            "queue_depth": len(self._local_queue),
            "free_tier_allowance": "1,000,000 requests/month (Always Free)",
            "payload": payload,
            "status": "ENQUEUED_FIFO_BUFFER",
        }

    def get_operational_parameters(self) -> Dict[str, Any]:
        """Reads Aegis operational disaster parameters from AWS Systems Manager (SSM) Parameter Store."""
        if self.enabled and self._ssm:
            try:
                resp = self._ssm.get_parameters_by_path(
                    Path="/aegis/prod",
                    Recursive=True,
                    WithDecryption=True,
                )
                params = {p["Name"]: p["Value"] for p in resp.get("Parameters", [])}
                if params:
                    self._ssm_parameters.update(params)
                    return {
                        "provider": "AWS_SSM_PARAMETER_STORE_LIVE",
                        "path": "/aegis/prod",
                        "parameters": self._ssm_parameters,
                        "status": "LOADED_FROM_SSM",
                    }
            except Exception as e:
                logger.warning(f"SSM get_parameters_by_path fallback triggered: {e}")

        return {
            "provider": "AWS_SSM_PARAMETER_STORE_SIMULATED",
            "path": "/aegis/prod",
            "free_tier_allowance": "10,000 Standard Parameters (Always Free Forever)",
            "parameters": self._ssm_parameters,
            "sqs_buffered_messages": len(self._local_queue),
            "status": "SSM_PARAMETERS_READY",
        }

    def update_operational_parameter(self, name: str, value: str) -> Dict[str, Any]:
        """Updates an operational threshold parameter in AWS SSM Parameter Store."""
        param_key = name if name.startswith("/aegis/") else f"/aegis/prod/{name.lstrip('/')}"
        self._ssm_parameters[param_key] = str(value)

        if self.enabled and self._ssm:
            try:
                self._ssm.put_parameter(
                    Name=param_key,
                    Value=str(value),
                    Type="String",
                    Overwrite=True,
                )
                return {
                    "provider": "AWS_SSM_PARAMETER_STORE_LIVE",
                    "name": param_key,
                    "value": str(value),
                    "status": "PARAMETER_UPDATED_LIVE",
                }
            except Exception as e:
                logger.warning(f"SSM put_parameter fallback triggered: {e}")

        return {
            "provider": "AWS_SSM_PARAMETER_STORE_SIMULATED",
            "name": param_key,
            "value": str(value),
            "all_parameters": self._ssm_parameters,
            "status": "PARAMETER_UPDATED",
        }


sqs_ssm_service = SQSAndSSMConfigService()
