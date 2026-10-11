import os
import json
import uuid
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional

logger = logging.getLogger("aegis.aws.dynamodb")

LOCAL_FALLBACK_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "dynamodb_local_cache.json",
)


def _has_real_aws_creds() -> bool:
    key = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
    secret = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
    if not key or not secret:
        return False
    if key.startswith("your_") or secret.startswith("your_") or key == "AKIAIOSFODNN7EXAMPLE":
        return False
    return True


def _convert_floats_to_decimal(obj: Any) -> Any:
    if isinstance(obj, float):
        return Decimal(str(round(obj, 6)))
    if isinstance(obj, dict):
        return {k: _convert_floats_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_floats_to_decimal(x) for x in obj]
    return obj


def _convert_decimals_to_floats(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _convert_decimals_to_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_decimals_to_floats(x) for x in obj]
    return obj


class DynamoDBTelemetryStore:
    """
    Amazon DynamoDB Integration for Aegis:
    - Stores Citizen Ground Reports in `Aegis-Citizen-Reports`
    - Stores Emergency Shelters in `Aegis-Emergency-Shelters`
    - Zero-lock serverless persistence with local JSON disk cache fallback
    """

    def __init__(self):
        self.region = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
        self.reports_table_name = os.getenv("AWS_DYNAMODB_REPORTS_TABLE", "Aegis-Citizen-Reports")
        self.shelters_table_name = os.getenv("AWS_DYNAMODB_SHELTERS_TABLE", "Aegis-Emergency-Shelters")
        self.enabled = _has_real_aws_creds()
        self._dynamodb = None
        if self.enabled:
            try:
                import boto3
                self._dynamodb = boto3.resource("dynamodb", region_name=self.region)
            except Exception as e:
                logger.warning(f"Boto3 DynamoDB initialization skipped: {e}")
                self.enabled = False

    def _load_local_cache(self) -> Dict[str, List[Dict[str, Any]]]:
        if os.path.exists(LOCAL_FALLBACK_FILE):
            try:
                with open(LOCAL_FALLBACK_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"reports": [], "shelters": []}

    def _save_local_cache(self, data: Dict[str, List[Dict[str, Any]]]):
        try:
            with open(LOCAL_FALLBACK_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not write DynamoDB local cache: {e}")

    def put_citizen_report(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Saves a citizen flood ground report to Amazon DynamoDB (and local cache)."""
        report_id = str(report_data.get("id") or f"RPT-{uuid.uuid4().hex[:8].upper()}")
        item = {
            "report_id": report_id,
            "id": report_data.get("id", report_id),
            "timestamp": report_data.get("timestamp") or datetime.utcnow().isoformat() + "Z",
            "user_id": str(report_data.get("user_id", "citizen_reporter")),
            "latitude": float(report_data.get("latitude", 25.5941)),
            "longitude": float(report_data.get("longitude", 85.1376)),
            "location_name": str(report_data.get("location_name", "Patna")),
            "severity": str(report_data.get("severity", "HIGH")),
            "water_depth": str(report_data.get("water_depth", "Knee-deep")),
            "description": str(report_data.get("description", "Ground flood hazard reported.")),
            "status": str(report_data.get("status", "OPEN")),
            "aws_storage": "DYNAMODB_LIVE" if self.enabled else "DYNAMODB_FALLBACK_CACHE",
        }

        # Always persist in local cache for instant resilience
        cache = self._load_local_cache()
        existing_ids = {str(r.get("report_id") or r.get("id")) for r in cache["reports"]}
        if report_id not in existing_ids:
            cache["reports"].insert(0, item)
            self._save_local_cache(cache)

        if self.enabled and self._dynamodb:
            try:
                table = self._dynamodb.Table(self.reports_table_name)
                table.put_item(Item=_convert_floats_to_decimal(item))
                return {"status": "SAVED_TO_DYNAMODB", "table": self.reports_table_name, "item": item}
            except Exception as e:
                logger.warning(f"DynamoDB put_item fallback triggered: {e}")

        return {"status": "SAVED_TO_LOCAL_CACHE", "table": self.reports_table_name, "item": item}

    def list_citizen_reports(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves citizen flood ground reports from Amazon DynamoDB or local cache."""
        if self.enabled and self._dynamodb:
            try:
                table = self._dynamodb.Table(self.reports_table_name)
                response = table.scan(Limit=limit)
                items = [_convert_decimals_to_floats(i) for i in response.get("Items", [])]
                if items:
                    items.sort(key=lambda x: str(x.get("timestamp", "")), reverse=True)
                    return items
            except Exception as e:
                logger.warning(f"DynamoDB scan fallback triggered: {e}")

        cache = self._load_local_cache()
        return cache.get("reports", [])[:limit]


dynamodb_service = DynamoDBTelemetryStore()
