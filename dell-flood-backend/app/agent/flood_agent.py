import time
import os
import smtplib
import numpy as np
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from app.agent.tools import (
    fetch_satellite,
    check_rainfall,
    check_rainfall_detailed,
    check_gauge,
    send_sms_alert,
    trigger_voice_call,
    export_pdf,
)
from app.ml.inference import get_shared_model
from app.ml.postprocess import PostProcessor
from app.ml.urnn_nowcaster import get_shared_urnn
from app.aegis.pipeline.impact_analyzer import calculate_live_impact
from app.RAG.generator import SituationReportGenerator
from app.agent.incident_orchestrator import get_incident_orchestrator
from app.api.auth_deps import slugify_location
from app.aws import s3_service, sns_service, polly_service, cloudwatch_service


class FloodAgentState:
    def __init__(self):
        self.memory = {}
        self.activity_log = []

    def log(self, message, cycle_logs=None):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] {message}"
        try:
            print(entry)
        except Exception:
            pass
        if cycle_logs is not None:
            cycle_logs.append(entry)
        if len(self.activity_log) > 200:
            self.activity_log = self.activity_log[-100:]
        self.activity_log.append(entry)


class FloodAgent:
    def __init__(self):
        self.state = FloodAgentState()
        self.model = get_shared_model()  # Shared singleton (Solves P17)
        self.urnn = get_shared_urnn()
        self.post_processor = PostProcessor()
        self.report_generator = SituationReportGenerator()
        self.orchestrator = get_incident_orchestrator()

    def run_cycle(
        self,
        location,
        lat,
        lon,
        phone_numbers=None,
        phones=None,
        language="hi",
        report_format="NDMA",
        auto_approve_hitl=False,
        require_hitl_for_calls=None,
        **kwargs,
    ):
        """
        Autonomous FloodAgent + 6-Agent LangGraph Supervisor Cycle (Solves P7, P17, P20, P21, P27, P28).
        Uses a run-scoped cycle_logs list so concurrent invocations never leak across users.
        """
        target_phones = phones or phone_numbers or ["+917678656930"]
        if require_hitl_for_calls is not None:
            auto_approve_hitl = not bool(require_hitl_for_calls)
        cycle_logs = []
        cycle_start_t = time.time()

        def rlog(msg: str):
            self.state.log(msg, cycle_logs=cycle_logs)

        rlog("===================================================")
        rlog(f"AEGIS 6-AGENT SUPERVISOR CYCLE START - Location: {location} ({lat:.4f}N, {lon:.4f}E)")
        rlog("===================================================")

        # Execute the 6-Agent LangGraph Orchestrator with MCP Provenance & CAP v1.2
        orch_res = self.orchestrator.run_incident_graph(
            location=location,
            lat=lat,
            lon=lon,
            language=language,
            report_format=report_format,
            auto_approve_hitl=auto_approve_hitl,
        )
        for olog in orch_res.get("logs", []):
            rlog(olog)

        rain_details = check_rainfall_detailed(lat, lon)
        rainfall_5day = rain_details["total_window_rain_mm"]
        gauge_info = orch_res.get("gauge") or check_gauge(location, rainfall_5day, lat, lon)
        gauge_status = gauge_info["status"]
        gauge_level = gauge_info["current_meters"]

        last_alert_time = self.state.memory.get(location, {}).get("last_alert_timestamp", 0)
        time_since_last_alert = time.time() - last_alert_time

        eo_data = orch_res.get("eo", {})
        urnn_data = orch_res.get("urnn", {})
        impact_data = orch_res.get("impact", {})

        area_sq_km = float(eo_data.get("area_sq_km", 1.85))
        confidence = int(float(eo_data.get("confidence_pct", 86.0)))
        classification = eo_data.get("classification", "Flood Inundation")
        severity = orch_res.get("severity", "HIGH")
        population_affected = int(impact_data.get("population_affected", 1420))
        buildings_damaged = int(impact_data.get("buildings_damaged", 310))
        facilities_at_risk = int(impact_data.get("facilities_at_risk", 4))
        peak_depth_m = float(urnn_data.get("horizon_metrics", {}).get("t_60m", {}).get("max_depth_m", 0.74))
        report_text = orch_res.get("situation_report", "")

        # Export slugified PDF report & Vault to Amazon S3
        s3_report_info = {}
        try:
            safe_loc = slugify_location(location)
            pdf_filename = f"report_{safe_loc}_{int(time.time())}.pdf"
            os.makedirs("./reports", exist_ok=True)
            pdf_path = f"./reports/{pdf_filename}"
            export_pdf(pdf_path, report_text or classification, location, severity)
            s3_report_info = s3_service.upload_pdf_report(pdf_path, pdf_filename)
            rlog(f"  [AWS S3] SITREP PDF vaulted: {s3_report_info.get('s3_key')} ({s3_report_info.get('status')})")
        except Exception as pdf_err:
            rlog(f"  [WARN] PDF/S3 export notice: {pdf_err}")

        # Synthesize Bilingual Emergency Voice Alert via Amazon Polly
        polly_info = {}
        try:
            tts_lang = "hi-IN" if str(language).lower().startswith("hi") else "en-IN"
            tts_text = (
                f"सावधान! {location} में बाढ़ का गंभीर खतरा है। जल स्तर {peak_depth_m:.1f} मीटर तक पहुंच सकता है। कृपया सुरक्षित आश्रय स्थल की ओर प्रस्थान करें।"
                if tts_lang == "hi-IN"
                else f"Emergency Flood Alert for {location}. Projected water depth is {peak_depth_m:.1f} meters. Proceed to the nearest high-elevation shelter immediately."
            )
            polly_info = polly_service.synthesize_emergency_alert(tts_text, language=tts_lang)
            rlog(f"  [AWS Polly] Neural Voice synthesized ({polly_info.get('voice_id')}, {tts_lang}): {polly_info.get('s3_key')}")
        except Exception as polly_err:
            rlog(f"  [WARN] Polly synthesis notice: {polly_err}")

        # Broadcast Emergency Alert via Amazon SNS
        sns_info = {}
        try:
            sns_info = sns_service.broadcast_flood_warning(
                location=location,
                severity_level=severity,
                water_depth_m=peak_depth_m,
                evacuation_url=s3_report_info.get("cloud_url_preview", "http://localhost:8081"),
            )
            rlog(f"  [AWS SNS] Emergency Topic broadcast dispatched: MessageID={sns_info.get('message_id')}")
        except Exception as sns_err:
            rlog(f"  [WARN] SNS broadcast notice: {sns_err}")

        # Emit Telemetry Metrics to Amazon CloudWatch
        cw_info = {}
        try:
            sev_map = {"CRITICAL": 9.2, "HIGH": 7.8, "MODERATE": 5.4, "LOW": 2.5}
            sev_score = sev_map.get(str(severity).upper(), 7.5)
            elapsed_ms = (time.time() - cycle_start_t) * 1000.0
            cw_info = cloudwatch_service.emit_disaster_metrics(
                location=location,
                severity_index=sev_score,
                evacuation_routes_count=max(1, facilities_at_risk),
                nowcast_latency_ms=elapsed_ms,
                reports_ingested=1,
            )
            rlog(f"  [AWS CloudWatch] Telemetry published to {cw_info.get('namespace')} (Severity={sev_score})")
        except Exception as cw_err:
            rlog(f"  [WARN] CloudWatch metric notice: {cw_err}")

        # Bounded memory update (max 100 entries — Solves P7)
        if len(self.state.memory) >= 100:
            self.state.memory.pop(next(iter(self.state.memory)), None)
        self.state.memory[location] = {
            "last_alert_timestamp": time.time() if severity in ["HIGH", "CRITICAL"] else last_alert_time,
            "last_severity": severity,
            "last_area_sq_km": area_sq_km,
            "last_gauge_status": gauge_status,
            "last_rainfall_mm": rainfall_5day,
            "last_confidence": confidence,
        }

        hitl_pending = self.get_hitl_queue(status="PENDING")

        return {
            "run_id": orch_res.get("run_id"),
            "location": location,
            "severity": severity,
            "escalation_tier": orch_res.get("escalation_tier", "ORANGE"),
            "classification": classification,
            "area_sq_km": area_sq_km,
            "peak_depth_m": peak_depth_m,
            "gauge_status": gauge_status,
            "river_discharge_m3s": gauge_info.get("river_discharge_m3s", 850.0),
            "rainfall_5day_mm": rainfall_5day,
            "antecedent_rain_5d_mm": rain_details["antecedent_rain_5d_mm"],
            "forecast_rain_24h_mm": rain_details["forecast_rain_24h_mm"],
            "confidence": confidence,
            "population": population_affected,
            "buildings": buildings_damaged,
            "facilities": facilities_at_risk,
            "report": report_text,
            "report_format": report_format,
            "agent_nodes_status": orch_res.get("agent_nodes_status", {}),
            "agent_statuses": orch_res.get("agent_nodes_status", {}),
            "mcp_provenance": orch_res.get("mcp_provenance", []),
            "mcp_audit_log": orch_res.get("mcp_provenance", []),
            "cap_alert": orch_res.get("cap_alert", {}),
            "hitl_draft_id": orch_res.get("hitl_draft_id"),
            "hitl_pending": hitl_pending,
            "evacuation": orch_res.get("evacuation", {}),
            "urnn": urnn_data,
            "target_phones": target_phones,
            "aws_cloud": {
                "s3_report": s3_report_info,
                "sns_broadcast": sns_info,
                "polly_audio": polly_info,
                "cloudwatch_telemetry": cw_info,
            },
            "logs": cycle_logs,
        }

    def get_hitl_queue(self, status="PENDING"):
        """Returns HITL approval queue items formatted for both UI and API consumers."""
        items = self.orchestrator.list_hitl_queue()
        formatted = []
        for item in items:
            st = item.get("status", "PENDING_APPROVAL")
            if status and status.upper() == "PENDING" and "PENDING" not in st.upper():
                continue
            cap = item.get("cap_alert", {})
            formatted.append({
                "item_id": item.get("draft_id"),
                "draft_id": item.get("draft_id"),
                "action_type": "CAP_ALERT_AND_VOICE_DISPATCH",
                "location": item.get("location", "Patna, Bihar"),
                "severity": item.get("severity", "CRITICAL"),
                "target_phones": [cap.get("target_demo_phone", "+917678656930")],
                "language": "hi",
                "created_at": item.get("created_at"),
                "status": "PENDING" if "PENDING" in st.upper() else st,
                "cap_alert": cap,
            })
        return formatted

    def approve_hitl_action(self, item_id: str, language: str = "hi"):
        """Approves a pending HITL draft and dispatches CAP Voice + AWS SNS + AWS Polly."""
        res = self.orchestrator.approve_and_dispatch_hitl(draft_id=item_id, language=language)
        loc = res.get("draft", {}).get("location", "Patna, Bihar")
        sev = res.get("draft", {}).get("severity", "CRITICAL")
        try:
            sns_res = sns_service.broadcast_flood_warning(location=loc, severity_level=sev, water_depth_m=0.82)
            polly_res = polly_service.synthesize_emergency_alert(
                f"HITL Approved Emergency Alert for {loc}. Severity: {sev}.",
                language="hi-IN" if str(language).lower().startswith("hi") else "en-IN",
            )
            res["aws_dispatch"] = {"sns": sns_res, "polly": polly_res}
        except Exception:
            pass
        return res


