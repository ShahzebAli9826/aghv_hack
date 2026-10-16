import os
import json
import math
import time
import uuid
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, TypedDict

from app.mcp.aegis_mcp_server import execute_mcp_tool, build_cap_v12_payload
from app.RAG.generator import SituationReportGenerator
from app.api.auth_deps import normalize_and_validate_phone
from app.agent import web_evidence

DB_PATH = os.getenv("AEGIS_APP_DB") or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "flood_app.db")
HITL_PENDING = "PENDING_OFFICIAL_APPROVAL"
HITL_APPROVED = "APPROVED_AND_DISPATCHED"
HITL_APPROVED_NO_RECIPIENT = "APPROVED_NO_RECIPIENT"

ESCALATION_TIERS = ("NONE", "YELLOW", "ORANGE", "RED")
SEVERITY_BY_TIER = {"NONE": "LOW", "YELLOW": "MODERATE", "ORANGE": "HIGH", "RED": "CRITICAL"}
REPORT_SEVERITY_WEIGHTS = {
    "CRITICAL": 100.0,
    "SEVERE": 92.0,
    "HIGH": 80.0,
    "MODERATE": 60.0,
    "MEDIUM": 60.0,
    "LOW": 35.0,
    "MINOR": 25.0,
}
# Same relative path as endpoints.DB_PATH (citizen complaints); opened read-only.
CROWD_DB_PATH = "flood_database.db"
CROWD_RADIUS_KM = 2.0
CROWD_WINDOW_S = 12 * 3600


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    x = (lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2.0)) * 111.32
    y = (lat2 - lat1) * 110.57
    return math.hypot(x, y)


def nearby_report_severity(lat: float, lon: float) -> Dict[str, Any]:
    """Mean severity weight (0-100) of unresolved citizen reports within 2 km in the last 12 h; 0 when there are none."""
    try:
        conn = sqlite3.connect(f"file:{CROWD_DB_PATH}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                "SELECT latitude, longitude, reported_severity FROM complaints WHERE status != 'resolved' AND timestamp >= ?",
                (time.time() - CROWD_WINDOW_S,),
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return {"weight": 0.0, "report_count": 0, "provenance": f"complaints unavailable ({exc}); user severity set to 0"}
    weights = [
        REPORT_SEVERITY_WEIGHTS.get(str(sev or "").upper(), REPORT_SEVERITY_WEIGHTS["MODERATE"])
        for r_lat, r_lon, sev in rows
        if _distance_km(lat, lon, float(r_lat), float(r_lon)) <= CROWD_RADIUS_KM
    ]
    if not weights:
        return {"weight": 0.0, "report_count": 0, "provenance": "no unresolved citizen reports within 2 km in 12 h; user severity set to 0"}
    return {
        "weight": round(sum(weights) / len(weights), 1),
        "report_count": len(weights),
        "provenance": f"mean severity of {len(weights)} unresolved citizen report(s) within 2 km in 12 h",
    }


def _parse_evidence(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return {"status": "UNREADABLE", "evidence": []}


class HitlDraftNotFound(LookupError):
    def __init__(self, draft_id: str):
        super().__init__(f"HITL draft {draft_id} does not exist")
        self.draft_id = draft_id


class HitlDraftNotPending(RuntimeError):
    def __init__(self, draft_id: str, status: str):
        super().__init__(f"HITL draft {draft_id} is {status}, not {HITL_PENDING}")
        self.draft_id = draft_id
        self.status = status


HITL_ADDED_COLUMNS = (("evidence_json", "TEXT"),)


def _init_orchestrator_tables():
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS hitl_approvals (
                draft_id TEXT PRIMARY KEY,
                run_id TEXT,
                location TEXT,
                lat REAL,
                lon REAL,
                severity TEXT,
                escalation_tier TEXT,
                area_sq_km REAL,
                max_depth_m REAL,
                target_phone TEXT,
                language TEXT,
                script_hi TEXT,
                script_en TEXT,
                cap_xml TEXT,
                status TEXT DEFAULT 'PENDING_OFFICIAL_APPROVAL',
                created_at REAL,
                approved_by TEXT,
                approved_at REAL
            )
            """
        )
        columns = {row[1] for row in cur.execute("PRAGMA table_info(hitl_approvals)")}
        for name, ddl in HITL_ADDED_COLUMNS:
            if name not in columns:
                cur.execute(f"ALTER TABLE hitl_approvals ADD COLUMN {name} {ddl}")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Orchestrator DB Init Error] {e}")


_init_orchestrator_tables()


class IncidentGraphState(TypedDict):
    run_id: str
    location: str
    lat: float
    lon: float
    language: str
    report_format: str
    escalation_tier: str  # NONE -> YELLOW -> ORANGE -> RED
    agent_logs: List[str]
    agent_nodes_status: Dict[str, str]
    mcp_calls: List[Dict[str, Any]]
    weather_telemetry: Dict[str, Any]
    gauge_telemetry: Dict[str, Any]
    crowd_telemetry: Dict[str, Any]
    eo_telemetry: Dict[str, Any]
    urnn_telemetry: Dict[str, Any]
    impact_telemetry: Dict[str, Any]
    evacuation_plan: Dict[str, Any]
    situation_report: str
    cap_alert: Dict[str, Any]
    hitl_draft_id: str


class MultiAgentIncidentOrchestrator:
    """
    6-Agent LangGraph Supervisor with Progressive Escalation (NONE -> YELLOW -> ORANGE -> RED),
    Formal MCP Tool Invocation, Numeric Grounding Validation, CAP v1.2 Alerting, and
    Human-in-the-Loop (HITL) Approval Queue (Solves P27 & P28).
    """

    def __init__(self):
        self.rag_generator = SituationReportGenerator()

    def run_incident_graph(
        self,
        location: str,
        lat: float,
        lon: float,
        language: str = "hi",
        report_format: str = "NDMA",
        target_phone: Optional[str] = None,
    ) -> Dict[str, Any]:
        run_id = f"inc_{uuid.uuid4().hex[:8]}"
        logs: List[str] = []
        mcp_calls: List[Dict[str, Any]] = []
        nodes_status = {
            "MonitorAgent": "PENDING",
            "WebEvidenceAgent": "PENDING",
            "CrowdIntelligenceAgent": "PENDING",
            "EOAnalystAgent": "PENDING",
            "LogisticsAgent": "PENDING",
            "ReporterAgent": "PENDING",
            "CommsAgent": "PENDING",
        }

        def invoke_mcp(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
            env = execute_mcp_tool(tool_name, args)
            mcp_calls.append(env["provenance"])
            return env["data"]

        escalation = "NONE"
        escalation_reasons: List[str] = []
        degraded: Dict[str, str] = {}

        def escalate(tier: str, reason: str):
            nonlocal escalation
            escalation_reasons.append(f"{tier}: {reason}")
            if ESCALATION_TIERS.index(tier) > ESCALATION_TIERS.index(escalation):
                escalation = tier

        # ------------------------------------------------------------------
        # NODE 1: MonitorAgent (Weather + Live GloFAS River Discharge)
        # ------------------------------------------------------------------
        nodes_status["MonitorAgent"] = "RUNNING"
        logs.append(f"[MonitorAgent] Scanning meteorological & Copernicus GloFAS river discharge at {location} ({lat:.3f}, {lon:.3f})...")
        rain_data = invoke_mcp("get_rainfall_telemetry", {"lat": lat, "lon": lon})
        gauge_data = invoke_mcp(
            "get_river_gauge_forecast",
            {"location": location, "lat": lat, "lon": lon, "rainfall_5d_mm": rain_data["antecedent_rain_5d_mm"]},
        )

        if gauge_data["status"] == "DANGER":
            escalate("ORANGE", "GloFAS gauge status DANGER")
        elif gauge_data["status"] == "WARNING":
            escalate("YELLOW", "GloFAS gauge status WARNING")
        if rain_data["total_window_rain_mm"] >= 90.0:
            escalate("ORANGE", f"5-day + 24-h rain {rain_data['total_window_rain_mm']} mm >= 90 mm")
        nodes_status["MonitorAgent"] = "COMPLETED"
        logs.append(
            f"[MonitorAgent] Antecedent 5d Rain: {rain_data['antecedent_rain_5d_mm']}mm | "
            f"Forecast 24h: {rain_data['forecast_rain_24h_mm']}mm | "
            f"GloFAS Discharge: {gauge_data['river_discharge_m3s']} m³/s ({gauge_data['status']}) -> Escalation: {escalation}"
        )

        # ------------------------------------------------------------------
        # NODE 1b: WebEvidenceAgent (read-only: attaches stored official-source evidence, never escalates)
        # ------------------------------------------------------------------
        nodes_status["WebEvidenceAgent"] = "RUNNING"
        web_intel = web_evidence.lookup(location, lat, lon)
        nodes_status["WebEvidenceAgent"] = web_intel["status"]
        if web_intel["status"] == web_evidence.FAILED:
            degraded["WebEvidenceAgent"] = web_intel["error"]
            logs.append(f"[WebEvidenceAgent] FAILED: {web_intel['error']}. The cycle continues without web evidence.")
        else:
            logs.append(
                f"[WebEvidenceAgent] {web_intel['status']}: {len(web_intel['evidence'])} official-source item(s) "
                f"from run {web_intel['run_id'] or 'none'} attached for human review; escalation unchanged ({escalation})."
            )

        # ------------------------------------------------------------------
        # NODE 2: EOAnalystAgent (SegFormer SAR+Optical + U-RNN 4D Depth + OSM)
        # ------------------------------------------------------------------
        nodes_status["EOAnalystAgent"] = "RUNNING"
        logs.append("[EOAnalystAgent] Executing SegFormer MiT-B2 SAR+Optical Fusion & U-RNN 3-Scale ConvGRU 4D Nowcast...")
        area_km2: Optional[float] = None
        peak_depth_60m: Optional[float] = None
        try:
            eo_data = invoke_mcp("run_flood_segmentation", {"lat": lat, "lon": lon})
            urnn_data = invoke_mcp("run_urnn_nowcast", {"lat": lat, "lon": lon, "rain_mm_hr": rain_data["peak_intensity_mm_hr"]})
            area_km2 = float(eo_data["area_sq_km"])
            peak_depth_60m = float(urnn_data["horizon_metrics"]["t_60m"]["max_depth_m"])
        except Exception as exc:
            degraded["EOAnalystAgent"] = f"{type(exc).__name__}: {exc}"[:300]
            unknown = f"unknown: EO analysis failed ({degraded['EOAnalystAgent']})"
            area_km2 = peak_depth_60m = None
            eo_data = {
                "status": "FAILED", "error": degraded["EOAnalystAgent"], "classification": None, "area_sq_km": None,
                "confidence_pct": None, "input_provenance": "esri_basemap+synthetic_sar", "area_provenance": unknown,
            }
            urnn_data = {"status": "SKIPPED", "horizon_metrics": {}, "depth_provenance": unknown}

        if "EOAnalystAgent" in degraded:
            impact_data = {
                "source": "not estimated: EO analysis failed",
                "population_affected": None,
                "buildings_damaged": None,
                "facilities_at_risk": None,
            }
            nodes_status["EOAnalystAgent"] = "FAILED"
            logs.append(
                f"[EOAnalystAgent] FAILED: {degraded['EOAnalystAgent']}. Flood area and depth are unknown, OSM impact "
                f"was skipped, and escalation continues from hydrology only ({escalation})."
            )
        else:
            if area_km2 > 0:
                impact_data = invoke_mcp("estimate_osm_impact", {"lat": lat, "lon": lon, "area_sq_km": area_km2})
            else:
                impact_data = {
                    "source": "not estimated: segmentation found no flooded area",
                    "population_affected": 0,
                    "buildings_damaged": 0,
                    "facilities_at_risk": 0,
                }
            if area_km2 >= 0.80:
                escalate("RED", f"segmented flood area {area_km2:.2f} km2 >= 0.80 ({eo_data['input_provenance']} input)")
            # The depth is an untrained heuristic, so it only escalates when observed hydrology already reached ORANGE.
            if peak_depth_60m >= 0.45 and escalation == "ORANGE":
                escalate("RED", f"{urnn_data['depth_provenance']} +60 min depth {peak_depth_60m:.2f} m >= 0.45 m with ORANGE hydrology")
            nodes_status["EOAnalystAgent"] = "COMPLETED"
            logs.append(
                f"[EOAnalystAgent] Active Flood Area: {area_km2:.2f} km² ({eo_data['input_provenance']}) | "
                f"U-RNN +60m Peak Depth: {peak_depth_60m:.2f}m ({urnn_data['depth_provenance']}) | "
                f"OSM Affected: {impact_data['population_affected']:,} citizens, {impact_data['buildings_damaged']} buildings -> Escalation: {escalation}"
            )

        # ------------------------------------------------------------------
        # NODE 3: CrowdIntelligenceAgent (60/40 Citizen Cluster Verification)
        # ------------------------------------------------------------------
        nodes_status["CrowdIntelligenceAgent"] = "RUNNING"
        crowd_input = nearby_report_severity(lat, lon)
        flooded = bool(area_km2)
        model_prob_pct = float(eo_data["confidence_pct"]) if flooded else 0.0
        crowd_data = invoke_mcp(
            "verify_crowd_cluster",
            {"lat": lat, "lon": lon, "user_severity_weight": crowd_input["weight"], "model_prob_pct": model_prob_pct},
        )
        crowd_data["user_severity_provenance"] = crowd_input["provenance"]
        crowd_data["model_prob_provenance"] = (
            "segmentation confidence over flooded pixels" if flooded
            else "EO analysis failed; model probability set to 0" if "EOAnalystAgent" in degraded
            else "no flooded pixels; model probability set to 0"
        )
        if crowd_data["cluster_verified"]:
            escalate("YELLOW", f"crowd cluster verified ({crowd_data['verification_score']}%, {crowd_input['report_count']} reports)")
        nodes_status["CrowdIntelligenceAgent"] = "COMPLETED"
        logs.append(
            f"[CrowdIntelligenceAgent] 60/40 Verification Score: {crowd_data['verification_score']}% "
            f"(user severity: {crowd_input['provenance']}) (Isolated via <untrusted_citizen_report> tags)."
        )
        severity = SEVERITY_BY_TIER[escalation]

        # ------------------------------------------------------------------
        # NODE 4: LogisticsAgent (Time-Varying Dijkstra Evacuation + Shelters)
        # ------------------------------------------------------------------
        nodes_status["LogisticsAgent"] = "RUNNING"
        evac_data = invoke_mcp("compute_dynamic_evacuation", {"lat": lat, "lon": lon})
        if impact_data["population_affected"] is None:
            alloc_data = {"status": "SKIPPED", "reason": "population not estimated: EO analysis failed"}
        else:
            alloc_data = invoke_mcp("allocate_shelter_capacity", {"population_affected": impact_data["population_affected"], "location": location})
        nodes_status["LogisticsAgent"] = "COMPLETED"
        logs.append(
            f"[LogisticsAgent] Time-Varying Dijkstra Route: {evac_data['distance_km']} km (ETA {evac_data['eta_minutes']} min), "
            f"bypassed {evac_data['submerged_segments_bypassed']} submerging road segment(s)."
        )

        # ------------------------------------------------------------------
        # NODE 5: ReporterAgent (4-Format Report + Numeric Claim Validator)
        # ------------------------------------------------------------------
        nodes_status["ReporterAgent"] = "RUNNING"
        if "EOAnalystAgent" in degraded:
            report_text = (
                f"SITUATION REPORT NOT GENERATED for {location}: EO analysis failed ({degraded['EOAnalystAgent']}). "
                f"Flood area, depth and impact are unknown. Escalation {escalation} rests on hydrology only"
                + (f": {'; '.join(escalation_reasons)}." if escalation_reasons else ".")
            )
            report = {"grounding_passed": None, "checks": {}}
            nodes_status["ReporterAgent"] = "SKIPPED_EO_FAILED"
            logs.append("[ReporterAgent] Skipped: no model figures to report because EO analysis failed.")
        else:
            report = self.rag_generator.generate_report_with_validation(
                location=location,
                area_sq_km=area_km2,
                classification=eo_data.get("classification", "Flood Inundation"),
                severity=severity,
                population_affected=impact_data["population_affected"],
                buildings_damaged=impact_data["buildings_damaged"],
                facilities_at_risk=impact_data["facilities_at_risk"],
                report_format=report_format,
                max_depth_m=peak_depth_60m,
                language=language,
            )
            report_text = report["report_text"]
            uncited = [name for name, ok in report["checks"].items() if not ok]
            verdict = "PASS" if report["grounding_passed"] else f"FAIL ({', '.join(uncited)})"
            nodes_status["ReporterAgent"] = "COMPLETED"
            logs.append(f"[ReporterAgent] Generated {report_format} Situation Report — Numeric Hallucination Validator: {verdict}.")

        # ------------------------------------------------------------------
        # NODE 6: CommsAgent (CAP v1.2 Alert + HITL Approval Gate)
        # ------------------------------------------------------------------
        cap_payload: Dict[str, Any] = {}
        draft_id: Optional[str] = None
        if escalation == "NONE":
            nodes_status["CommsAgent"] = "SKIPPED_NO_ESCALATION"
            logs.append("[CommsAgent] Escalation NONE: no CAP alert drafted, nothing queued for approval.")
        else:
            nodes_status["CommsAgent"] = "RUNNING"
            cap_payload = invoke_mcp(
                "draft_cap_alert",
                {
                    "location": location,
                    "lat": lat,
                    "lon": lon,
                    "severity": severity,
                    "area_sq_km": area_km2,
                    "max_depth_m": peak_depth_60m,
                    "language": language,
                },
            )
            draft_id = f"hitl_{uuid.uuid4().hex[:8]}"
            self._save_hitl_draft(
                draft_id=draft_id,
                run_id=run_id,
                location=location,
                lat=lat,
                lon=lon,
                severity=severity,
                escalation_tier=escalation,
                area_sq_km=area_km2,
                max_depth_m=peak_depth_60m,
                language=language,
                cap_payload=cap_payload,
                target_phone=target_phone,
                web_intel=web_intel,
            )
            nodes_status["CommsAgent"] = "AWAITING_HITL_APPROVAL"
            logs.append(
                f"[CommsAgent] Drafted OASIS CAP v1.2 XML/JSON Alert ({cap_payload['identifier']}) & Bilingual Voice Script "
                f"{'for the requested recipient' if target_phone else 'with no recipient (approval will not place a call)'}. "
                f"Queued in HITL Approval Gate (Draft ID: {draft_id})."
            )

        return {
            "run_id": run_id,
            "location": location,
            "lat": lat,
            "lon": lon,
            "severity": severity,
            "escalation_tier": escalation,
            "escalation_reasons": escalation_reasons,
            "report_format": report_format,
            "agent_nodes_status": nodes_status,
            "mcp_provenance": mcp_calls,
            "logs": logs,
            "weather": rain_data,
            "gauge": gauge_data,
            "crowd": crowd_data,
            "eo": eo_data,
            "urnn": urnn_data,
            "impact": impact_data,
            "evacuation": evac_data,
            "shelter_allocation": alloc_data,
            "situation_report": report_text,
            "report_validation": {"grounding_passed": report["grounding_passed"], "checks": report["checks"]},
            "cap_alert": cap_payload,
            "hitl_draft_id": draft_id,
            "web_intelligence": web_intel,
            "degraded_nodes": degraded,
        }

    def _save_hitl_draft(
        self,
        draft_id: str,
        run_id: str,
        location: str,
        lat: float,
        lon: float,
        severity: str,
        escalation_tier: str,
        area_sq_km: float,
        max_depth_m: float,
        language: str,
        cap_payload: Dict[str, Any],
        target_phone: Optional[str],
        web_intel: Optional[Dict[str, Any]] = None,
    ):
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO hitl_approvals (
                    draft_id, run_id, location, lat, lon, severity, escalation_tier,
                    area_sq_km, max_depth_m, target_phone, language, script_hi, script_en,
                    cap_xml, status, created_at, evidence_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_id,
                    run_id,
                    location,
                    lat,
                    lon,
                    severity,
                    escalation_tier,
                    area_sq_km,
                    max_depth_m,
                    target_phone,
                    language,
                    cap_payload["script_hi"],
                    cap_payload["script_en"],
                    cap_payload["xml"],
                    HITL_PENDING,
                    time.time(),
                    json.dumps(web_intel, default=str) if web_intel else None,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[HITL Save Error] {e}")

    @staticmethod
    def list_hitl_queue() -> List[Dict[str, Any]]:
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM hitl_approvals ORDER BY created_at DESC LIMIT 20")
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            for row in rows:
                row["web_evidence"] = _parse_evidence(row.pop("evidence_json", None))
            return rows
        except Exception:
            return []

    @staticmethod
    def approve_and_dispatch_hitl(
        draft_id: str,
        approved_by: str,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Moves a pending draft to approved exactly once, then dispatches it. Raises HitlDraftNotFound / HitlDraftNotPending."""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM hitl_approvals WHERE draft_id = ?", (draft_id,))
            row = cur.fetchone()
            if row is None:
                raise HitlDraftNotFound(draft_id)
            target_phone = normalize_and_validate_phone(row["target_phone"])
            new_status = HITL_APPROVED if target_phone else HITL_APPROVED_NO_RECIPIENT
            approved_at = time.time()
            cur.execute(
                "UPDATE hitl_approvals SET status = ?, approved_by = ?, approved_at = ? WHERE draft_id = ? AND status = ?",
                (new_status, approved_by, approved_at, draft_id, HITL_PENDING),
            )
            if cur.rowcount != 1:
                raise HitlDraftNotPending(draft_id, row["status"])
            conn.commit()
        finally:
            conn.close()

        draft = {**dict(row), "status": new_status, "approved_by": approved_by, "approved_at": approved_at}
        if target_phone is None:
            print(f"[HITL] Draft {draft_id} approved by {approved_by} has no valid recipient; no call placed.")
            receipt = {"status": "NO_RECIPIENT", "detail": "Draft has no valid recipient phone number; no call was placed."}
        else:
            receipt = execute_mcp_tool(
                "dispatch_approved_alert",
                {
                    "phone_number": target_phone,
                    "location": draft["location"],
                    "severity": draft["severity"],
                    "language": language or draft["language"],
                    "max_depth_m": draft["max_depth_m"],
                },
            )["data"]
        return {
            "draft_id": draft_id,
            "status": new_status,
            "approved_by": approved_by,
            "dispatch_receipt": receipt,
            "draft": draft,
        }


_SHARED_ORCHESTRATOR: Optional[MultiAgentIncidentOrchestrator] = None


def get_incident_orchestrator() -> MultiAgentIncidentOrchestrator:
    global _SHARED_ORCHESTRATOR
    if _SHARED_ORCHESTRATOR is None:
        _SHARED_ORCHESTRATOR = MultiAgentIncidentOrchestrator()
    return _SHARED_ORCHESTRATOR
