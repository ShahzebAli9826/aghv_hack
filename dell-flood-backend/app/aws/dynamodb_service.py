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

    def put_emergency_shelter(self, shelter_data: Dict[str, Any]) -> Dict[str, Any]:
        """Persists or updates an emergency relief shelter in Amazon DynamoDB (`Aegis-Emergency-Shelters`)."""
        shelter_id = str(shelter_data.get("shelter_id") or f"SHL-{uuid.uuid4().hex[:6].upper()}")
        item = {
            "shelter_id": shelter_id,
            "name": str(shelter_data.get("name", "Gandhi Maidan High-Ground NDRF Relief Camp")),
            "district": str(shelter_data.get("district", "Patna District")),
            "latitude": float(shelter_data.get("latitude", 25.6185)),
            "longitude": float(shelter_data.get("longitude", 85.1412)),
            "elevation_m": float(shelter_data.get("elevation_m", 58.4)),
            "capacity": int(shelter_data.get("capacity", 1200)),
            "current_occupancy": int(shelter_data.get("current_occupancy", 430)),
            "medical_unit_active": bool(shelter_data.get("medical_unit_active", True)),
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }
        cache = self._load_local_cache()
        shelters = cache.setdefault("shelters", [])
        shelters = [s for s in shelters if s.get("shelter_id") != shelter_id]
        shelters.insert(0, item)
        cache["shelters"] = shelters[:50]
        self._save_local_cache(cache)

        if self.enabled and self._dynamodb:
            try:
                table = self._dynamodb.Table(self.shelters_table_name)
                table.put_item(Item=_convert_floats_to_decimal(item))
                return {"status": "SAVED_TO_DYNAMODB", "table": self.shelters_table_name, "shelter": item}
            except Exception as e:
                logger.warning(f"DynamoDB shelter put_item fallback: {e}")

        return {"status": "SAVED_TO_LOCAL_CACHE", "table": self.shelters_table_name, "shelter": item}

    def list_emergency_shelters(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Lists emergency relief shelters from Amazon DynamoDB (`Aegis-Emergency-Shelters`)."""
        if self.enabled and self._dynamodb:
            try:
                table = self._dynamodb.Table(self.shelters_table_name)
                resp = table.scan(Limit=limit)
                items = [_convert_decimals_to_floats(i) for i in resp.get("Items", [])]
                if items:
                    return items
            except Exception as e:
                logger.warning(f"DynamoDB shelter scan fallback: {e}")

        cache = self._load_local_cache()
        shelters = cache.get("shelters", [])
        if not shelters:
            default_shelters = [
                {
                    "shelter_id": "SHL-PATNA-01",
                    "name": "Gandhi Maidan High-Ground NDRF Relief Camp",
                    "district": "Patna District",
                    "latitude": 25.6185,
                    "longitude": 85.1412,
                    "elevation_m": 58.4,
                    "capacity": 1500,
                    "current_occupancy": 620,
                    "medical_unit_active": True,
                },
                {
                    "shelter_id": "SHL-ASSAM-01",
                    "name": "Jorhat Government Stadium High-Elevation Shelter",
                    "district": "Jorhat, Assam",
                    "latitude": 26.7540,
                    "longitude": 94.2090,
                    "elevation_m": 118.2,
                    "capacity": 2000,
                    "current_occupancy": 890,
                    "medical_unit_active": True,
                },
            ]
            cache["shelters"] = default_shelters
            self._save_local_cache(cache)
            return default_shelters
        return shelters[:limit]

    def record_mcp_audit_entry(self, provenance_entry: Dict[str, Any]) -> Dict[str, Any]:
        """Persists an MCP tool execution provenance record to DynamoDB (`Aegis-MCP-Audit-Ledger`)."""
        audit_table_name = os.getenv("AWS_DYNAMODB_MCP_AUDIT_TABLE", "Aegis-MCP-Audit-Ledger")
        cache = self._load_local_cache()
        ledger = cache.setdefault("mcp_audit_ledger", [])
        ledger.insert(0, provenance_entry)
        cache["mcp_audit_ledger"] = ledger[:100]
        self._save_local_cache(cache)

        if self.enabled and self._dynamodb:
            try:
                table = self._dynamodb.Table(audit_table_name)
                table.put_item(Item=_convert_floats_to_decimal(provenance_entry))
                return {"status": "SAVED_TO_DYNAMODB", "table": audit_table_name}
            except Exception:
                pass
        return {"status": "SAVED_TO_LOCAL_CACHE", "table": audit_table_name}


dynamodb_service = DynamoDBTelemetryStore()

