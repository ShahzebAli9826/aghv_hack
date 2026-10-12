import os
import json
import uuid
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

logger = logging.getLogger("aegis.aws.events_sfn")


def _has_real_aws_creds() -> bool:
    key = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
    secret = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
    if not key or not secret:
        return False
    if key.startswith("your_") or secret.startswith("your_") or key == "AKIAIOSFODNN7EXAMPLE":
        return False
    return True


class EventBridgeStepFunctionsOrchestrator:
    """
    Amazon EventBridge & AWS Step Functions Integration for Aegis (Always Free Tier):
    - EventBridge (14M custom events/mo Always Free): Publishes `FloodAnomalyDetected`,
      `ConvGRUNowcastCompleted`, and `CAPAlertDispatched` events to `aegis-disaster-event-bus`
    - AWS Step Functions (4,000 state transitions/mo Always Free): Executes the 6-State
      Autonomous Disaster Response State Machine (`Aegis-6Agent-Incident-Workflow`)
    """

    def __init__(self):
        self.region = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
        self.event_bus_name = os.getenv("AWS_EVENTBRIDGE_BUS", "aegis-disaster-event-bus")
        self.state_machine_arn = os.getenv(
            "AWS_STEP_FUNCTIONS_ARN",
            f"arn:aws:states:{self.region}:000000000000:stateMachine:Aegis-6Agent-Incident-Workflow",
        )
        self.enabled = _has_real_aws_creds()
        self._events = None
        self._sfn = None
        self.recent_executions: List[Dict[str, Any]] = []
        if self.enabled:
            try:
                import boto3
                self._events = boto3.client("events", region_name=self.region)
                self._sfn = boto3.client("stepfunctions", region_name=self.region)
            except Exception as e:
                logger.warning(f"Boto3 EventBridge/StepFunctions initialization skipped: {e}")
                self.enabled = False

    def publish_disaster_event(
        self,
        detail_type: str,
        detail: Dict[str, Any],
        source: str = "aegis.flood.autonomous.engine",
    ) -> Dict[str, Any]:
        """Publishes a structured disaster event to Amazon EventBridge."""
        event_id = f"evt-{uuid.uuid4().hex[:10]}"
        if self.enabled and self._events:
            try:
                resp = self._events.put_events(
                    Entries=[
                        {
                            "Time": datetime.now(timezone.utc),
                            "Source": source,
                            "DetailType": detail_type,
                            "Detail": json.dumps(detail, default=str),
                            "EventBusName": self.event_bus_name,
                        }
                    ]
                )
                entries = resp.get("Entries", [{}])
                event_id = entries[0].get("EventId", event_id)
                return {
                    "provider": "AMAZON_EVENTBRIDGE_LIVE",
                    "event_bus": self.event_bus_name,
                    "event_id": event_id,
                    "source": source,
                    "detail_type": detail_type,
                    "detail": detail,
                    "status": "EVENT_PUBLISHED_LIVE",
                }
            except Exception as e:
                logger.warning(f"EventBridge put_events fallback triggered: {e}")

        return {
            "provider": "AWS_EVENTBRIDGE_SIMULATED",
            "event_bus": self.event_bus_name,
            "event_id": event_id,
            "source": source,
            "detail_type": detail_type,
            "detail": detail,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "status": "EVENT_PUBLISHED_SIMULATED",
        }

    def start_incident_workflow(
        self,
        location: str,
        lat: float = 25.6124,
        lon: float = 85.1376,
        severity: str = "CRITICAL",
    ) -> Dict[str, Any]:
        """Starts an AWS Step Functions execution for the 6-Agent Disaster Response State Machine."""
        exec_name = f"aegis-incident-{int(time.time())}-{uuid.uuid4().hex[:6]}"
        input_payload = {
            "location": location,
            "lat": lat,
            "lon": lon,
            "severity": severity,
            "initiated_at_utc": datetime.now(timezone.utc).isoformat(),
        }

        if self.enabled and self._sfn and "000000000000" not in self.state_machine_arn:
            try:
                resp = self._sfn.start_execution(
                    stateMachineArn=self.state_machine_arn,
                    name=exec_name,
                    input=json.dumps(input_payload),
                )
                return {
                    "provider": "AWS_STEP_FUNCTIONS_LIVE",
                    "execution_arn": resp.get("executionArn"),
                    "state_machine_arn": self.state_machine_arn,
                    "input": input_payload,
                    "status": "RUNNING_LIVE",
                }
            except Exception as e:
                logger.warning(f"Step Functions start_execution fallback triggered: {e}")

        states_trace = [
            {"state": "1_WeatherSentinel", "status": "SUCCEEDED", "duration_ms": 48},
            {"state": "2_HydrologySentinel_GloFAS", "status": "SUCCEEDED", "duration_ms": 62},
            {"state": "3_SatelliteVision_SegFormer_URNN", "status": "SUCCEEDED", "duration_ms": 134},
            {"state": "4_GISImpact_DynamicDijkstra", "status": "SUCCEEDED", "duration_ms": 85},
            {"state": "5_AlertDispatcher_CAP_SNS_Polly", "status": "SUCCEEDED", "duration_ms": 54},
            {"state": "6_RAGReportCompiler_Bedrock_S3", "status": "SUCCEEDED", "duration_ms": 91},
        ]
        record = {
            "provider": "AWS_STEP_FUNCTIONS_SIMULATED",
            "execution_arn": f"arn:aws:states:{self.region}:000000000000:execution:Aegis-6Agent-Incident-Workflow:{exec_name}",
            "state_machine_arn": self.state_machine_arn,
            "input": input_payload,
            "state_transitions_used": len(states_trace),
            "free_tier_limit": "4,000 state transitions/month (Always Free)",
            "states_trace": states_trace,
            "status": "SUCCEEDED",
        }
        self.recent_executions.insert(0, record)
        self.recent_executions = self.recent_executions[:20]
        return record


events_sfn_service = EventBridgeStepFunctionsOrchestrator()
