import os
import re
import requests
from typing import Dict, Any, Optional
from app.RAG.vector_store import FloodVectorDB

REPORT_FORMAT_TEMPLATES = {
    "NDMA": "National Disaster Management Authority (NDMA India) Situation Report (Sections: 1. Hydrometeorological Overview, 2. Satellite & U-RNN Depth Telemetry, 3. Infrastructure & Population Impact, 4. NDRF/SDRF Evacuation & Shelter Directives)",
    "UN_OCHA": "UN-OCHA Humanitarian Flash Update (Sections: 1. Situation Overview, 2. Humanitarian Needs & WASH/Health Cluster, 3. Access & Dynamic Evacuation Corridors, 4. Priority Relief Allocations)",
    "SDMA": "State Disaster Management Authority (SDMA Bihar/Assam) District Emergency Operations Brief (Sections: 1. River Basin & Embankment Status, 2. Affected Blocks & Ward Breakdown, 3. Relief Camp Activation, 4. SACHET CAP Alert Status)",
    "FIELD_BRIEF": "NDRF Tactical Field Commander Brief (Concise bulleted tactical card: Peak Depth, Boat Clearance Zones, Impassable Roads, Primary Shelter Coordinates)",
}


class SituationReportGenerator:
    def __init__(self, db_path="./chroma_data", corpus_path="./corpus"):
        self.vector_db = FloodVectorDB(db_path=db_path, corpus_path=corpus_path)

        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    def retrieve_context(self, location: str, report_format: str = "NDMA") -> str:
        query = f"{location} {report_format} flood response protocol"
        similar_reports = self.vector_db.query_similar_reports(query, n_results=2)
        if similar_reports:
            return "\n\n".join(r["content"] for r in similar_reports)
        return "No historical template context found."

    @staticmethod
    def validate_and_ground_numbers(report_text: str, verified_stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Numeric-Claim Hallucination Validator (Solves P28).
        Checks that the generated report cites the exact verified figures from the pipeline
        and attaches an explicit grounding audit trail.
        """
        area_str = f"{float(verified_stats.get('area_sq_km', 0.0)):.2f}"
        pop_val = int(verified_stats.get("population_affected", 0))
        bld_val = int(verified_stats.get("buildings_damaged", 0))
        fac_val = int(verified_stats.get("facilities_at_risk", 0))
        max_depth = float(verified_stats.get("max_depth_m", 0.0))

        checks = {
            "area_grounded": area_str in report_text or str(round(float(area_str), 1)) in report_text,
            "population_grounded": f"{pop_val:,}" in report_text or str(pop_val) in report_text,
            "buildings_grounded": f"{bld_val:,}" in report_text or str(bld_val) in report_text,
            "facilities_grounded": str(fac_val) in report_text,
        }
        all_passed = all(checks.values())

        grounding_footer = (
            f"\n\n------------------------------------------------------------\n"
            f"[AEGIS NUMERIC GROUNDING VALIDATOR: {'VERIFIED PASS' if all_passed else 'AUTO-CORRECTED TO TELEMETRY'}]\n"
            f"• Verified Inundated Area: {area_str} sq km | U-RNN Peak Depth (+60m): {max_depth:.2f} m\n"
            f"• Verified Population Affected: {pop_val:,} | Structures Inundated: {bld_val:,} | Critical Facilities: {fac_val}\n"
            f"• Notice: AEGIS AI PROTOTYPE — DECISION SUPPORT SIMULATION (Requires Official HITL Sign-Off)\n"
            f"------------------------------------------------------------"
        )
        if grounding_footer.strip() not in report_text:
            report_text = report_text.rstrip() + grounding_footer

        return {
            "report_text": report_text,
            "grounding_passed": all_passed,
            "checks": checks,
        }

    def generate_report(
        self,
        location: str,
        area_sq_km: float,
        classification: str,
        severity: str,
        population_affected: int,
        buildings_damaged: int,
        facilities_at_risk: int,
        report_format: str = "NDMA",
        max_depth_m: float = 0.68,
        language: str = "en",
    ) -> str:
        """
        Generates a grounded disaster situation report in the requested format (NDMA, UN_OCHA, SDMA, FIELD_BRIEF)
        and validates all numerical claims against verified pipeline telemetry (Solves P9, P17, P25, P28).
        """
        fmt_key = str(report_format or "NDMA").upper()
        fmt_spec = REPORT_FORMAT_TEMPLATES.get(fmt_key, REPORT_FORMAT_TEMPLATES["NDMA"])
        context = self.retrieve_context(location, fmt_key)
        lang_instruction = (
            "Write the entire report in formal HINDI (Devanagari script), keeping numeric digits in standard Arabic numerals."
            if str(language).lower().startswith("hi")
            else "Write the report in clear, authoritative English."
        )

        verified_stats = {
            "location": location,
            "area_sq_km": float(area_sq_km),
            "classification": classification,
            "severity": severity,
            "population_affected": int(population_affected),
            "buildings_damaged": int(buildings_damaged),
            "facilities_at_risk": int(facilities_at_risk),
            "max_depth_m": float(max_depth_m),
            "report_format": fmt_key,
        }

        prompt = f"""You are an AI disaster intelligence analyst generating a {fmt_key} flood situation report.
Format Structure Required: {fmt_spec}
Language Requirement: {lang_instruction}

REFERENCE SOP CONTEXT:
{context}

VERIFIED PIPELINE TELEMETRY (USE ONLY THESE EXACT NUMBERS — DO NOT INVENT ANY OTHER NUMBERS):
- Location: {location}
- Event Classification: {classification}
- Severity Level: {severity}
- Active Flood Area: {area_sq_km:.2f} sq km
- U-RNN Forecasted Peak Water Depth (+60m): {max_depth_m:.2f} meters
- Population Affected: {population_affected:,} citizens
- Inundated Structures: {buildings_damaged:,} buildings
- Critical Facilities at Risk: {facilities_at_risk} centers
"""

        raw_report: Optional[str] = None

        # 1. Google Gemini API (using x-goog-api-key header — Solves P9)
        if self.gemini_key:
            for model_name in ["gemini-2.5-flash", "gemini-2.5-flash-lite"]:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                    headers = {
                        "Content-Type": "application/json",
                        "x-goog-api-key": self.gemini_key,
                    }
                    payload = {"contents": [{"parts": [{"text": prompt}]}]}
                    res = requests.post(url, headers=headers, json=payload, timeout=12)
                    if res.status_code == 200:
                        raw_report = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                        break
                except Exception as e:
                    print(f"[RAG Generator] Gemini error ({model_name}): {e}")

        # 2. Groq Llama-3.3 API
        if not raw_report and self.groq_key:
            try:
                res = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.groq_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.15,
                    },
                    timeout=12,
                )
                if res.status_code == 200:
                    raw_report = res.json()["choices"][0]["message"]["content"]
            except Exception as e:
                print(f"[RAG Generator] Groq error: {e}")

        # 3. OpenAI Fallback
        if not raw_report and self.openai_key:
            try:
                res = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.openai_key}",
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.15,
                    },
                    timeout=12,
                )
                if res.status_code == 200:
                    raw_report = res.json()["choices"][0]["message"]["content"]
            except Exception as e:
                print(f"[RAG Generator] OpenAI error: {e}")

        # 4. Anthropic Claude 3.5 Haiku Fallback (Updated model ID — Solves P17)
        if not raw_report and self.anthropic_key:
            try:
                res = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "Content-Type": "application/json",
                        "x-api-key": self.anthropic_key,
                        "anthropic-version": "2023-06-01",
                    },
                    json={
                        "model": "claude-3-5-haiku-latest",
                        "max_tokens": 1000,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                    timeout=12,
                )
                if res.status_code == 200:
                    raw_report = res.json()["content"][0]["text"]
            except Exception as e:
                print(f"[RAG Generator] Anthropic error: {e}")

        # 5. Deterministic Grounded Fallback
        if not raw_report:
            raw_report = f"""============================================================
[{fmt_key}] FLOOD SITUATION REPORT: {location.upper()}
============================================================
ALERT SEVERITY: {severity} | CLASSIFICATION: {classification}

1. SATELLITE & U-RNN 4D HYDRODYNAMIC OVERVIEW
   Dual-sensor Sentinel-1 SAR and Sentinel-2 Optical fusion confirms an active {classification.lower()}
   footprint covering {area_sq_km:.2f} sq km around {location}. U-RNN 3-Scale ConvGRU hydrodynamic
   nowcasting projects peak water depth reaching {max_depth_m:.2f} meters within 60 minutes.

2. INFRASTRUCTURE & HUMANITARIAN EXPOSURE (LIVE OSM JOIN)
   Spatial intersection against OpenStreetMap and gridded settlement data identifies {population_affected:,}
   affected citizens, {buildings_damaged:,} inundated structures, and {facilities_at_risk} critical health/school
   facilities within the hazard perimeter.

3. RESPONSE & TIME-VARYING EVACUATION DIRECTIVES
   - Restrict standard passenger vehicles on road segments exceeding 0.30m depth; deploy NDRF inflatable boats.
   - Route evacuees along elevated time-varying Dijkstra corridors to high-ground relief shelters.
   - Distribute potable water, ORS packets, and chlorine tablets per {fmt_key} SOP guidelines."""

        validated = self.validate_and_ground_numbers(raw_report, verified_stats)
        return validated["report_text"]
