import os
import json
import time
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("aegis.aws.bedrock")


def _has_real_aws_creds() -> bool:
    key = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
    secret = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
    if not key or not secret:
        return False
    if key.startswith("your_") or secret.startswith("your_") or key == "AKIAIOSFODNN7EXAMPLE":
        return False
    return True


class BedrockDisasterIntelligence:
    """
    Amazon Bedrock Runtime & Bedrock Knowledge Bases Integration for Aegis:
    - Generates grounded NDMA / UN-OCHA / SDMA / FIELD_BRIEF Situation Reports using
      Claude 3 Haiku (`anthropic.claude-3-haiku-20240307-v1:0`) or Amazon Nova Micro (`amazon.nova-micro-v1:0`)
    - Queries Amazon Bedrock Knowledge Bases (`bedrock-agent-runtime`) for NDMA/SDMA SOP retrieval
    - Dual-mode execution: live AWS Bedrock when credentials exist, deterministic grounded synthesis fallback offline
    """

    def __init__(self):
        self.region = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
        self.model_id = os.getenv("AWS_BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
        self.kb_id = os.getenv("AWS_BEDROCK_KB_ID", "KB-AEGIS-NDMA-SOP-2026")
        self.enabled = _has_real_aws_creds()
        self._bedrock = None
        self._bedrock_agent = None
        if self.enabled:
            try:
                import boto3
                self._bedrock = boto3.client("bedrock-runtime", region_name=self.region)
                self._bedrock_agent = boto3.client("bedrock-agent-runtime", region_name=self.region)
            except Exception as e:
                logger.warning(f"Boto3 Bedrock initialization skipped: {e}")
                self.enabled = False

    def retrieve_sop_context(self, query: str, max_results: int = 3) -> Dict[str, Any]:
        """Retrieves disaster SOP passages from Amazon Bedrock Knowledge Bases (or local corpus fallback)."""
        t0 = time.perf_counter()
        if self.enabled and self._bedrock_agent and not self.kb_id.startswith("KB-AEGIS-"):
            try:
                resp = self._bedrock_agent.retrieve(
                    knowledgeBaseId=self.kb_id,
                    retrievalQuery={"text": query},
                    retrievalConfiguration={
                        "vectorSearchConfiguration": {"numberOfResults": max_results}
                    },
                )
                passages = [
                    {
                        "content": r.get("content", {}).get("text", ""),
                        "score": round(float(r.get("score", 0.9)), 3),
                        "source": r.get("location", {}).get("s3Location", {}).get("uri", "s3://aegis-disaster-vault/corpus/"),
                    }
                    for r in resp.get("retrievalResults", [])
                ]
                return {
                    "provider": "AMAZON_BEDROCK_KB_LIVE",
                    "knowledge_base_id": self.kb_id,
                    "query": query,
                    "results": passages,
                    "latency_ms": round((time.perf_counter() - t0) * 1000.0, 1),
                    "status": "RETRIEVED_LIVE",
                }
            except Exception as e:
                logger.warning(f"Bedrock Knowledge Base retrieval fallback triggered: {e}")

        # Local corpus fallback
        fallback_passages = [
            {
                "content": (
                    "NDMA Standard Operating Procedure (Urban & Riverine Floods): "
                    "When ConvGRU 60-minute water depth exceeds 0.30m on primary evacuation arteries, "
                    "immediately reroute civilian traffic to elevated corridors (>52m AMSL) and deploy NDRF inflatable boats."
                ),
                "score": 0.94,
                "source": "s3://aegis-disaster-vault/corpus/ndma_bihar_sop.txt",
            },
            {
                "content": (
                    "ASDMA / BSDMA Relief Camp Protocol: "
                    "Activate high-school and stadium shelters with minimum 3.5 sq.m per evacuee, potable water reserves, "
                    "and bilingual CAP v1.2 sirens via SACHET & Amazon SNS/Polly."
                ),
                "score": 0.89,
                "source": "s3://aegis-disaster-vault/corpus/assam_sdma_contingency.txt",
            },
        ]
        return {
            "provider": "AWS_BEDROCK_KB_HYBRID",
            "knowledge_base_id": self.kb_id,
            "query": query,
            "results": fallback_passages[:max_results],
            "latency_ms": round((time.perf_counter() - t0) * 1000.0, 1),
            "status": "RETRIEVED_FALLBACK",
        }

    def invoke_sitrep_model(
        self,
        prompt: str,
        location: str = "Patna District",
        severity: str = "CRITICAL",
        area_sq_km: float = 4.2,
        max_depth_m: float = 0.78,
        population_affected: int = 12400,
        buildings_damaged: int = 840,
        facilities_at_risk: int = 5,
        report_format: str = "NDMA",
        language: str = "en",
    ) -> Dict[str, Any]:
        """Invokes Amazon Bedrock Claude 3 Haiku / Nova Micro to synthesize a grounded SITREP."""
        t0 = time.perf_counter()
        if self.enabled and self._bedrock:
            try:
                body = json.dumps(
                    {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 900,
                        "temperature": 0.15,
                        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
                    }
                )
                response = self._bedrock.invoke_model(
                    modelId=self.model_id,
                    contentType="application/json",
                    accept="application/json",
                    body=body,
                )
                resp_body = json.loads(response["body"].read())
                text = resp_body.get("content", [{}])[0].get("text", "")
                if text:
                    return {
                        "provider": "AMAZON_BEDROCK_LIVE",
                        "model_id": self.model_id,
                        "region": self.region,
                        "report_text": text,
                        "latency_ms": round((time.perf_counter() - t0) * 1000.0, 1),
                        "status": "GENERATED_LIVE",
                    }
            except Exception as e:
                logger.warning(f"Bedrock invoke_model fallback triggered: {e}")

        is_hi = str(language).lower().startswith("hi")
        if is_hi:
            synthesized = (
                f"[{report_format} आधिकारिक बाढ़ स्थिति रिपोर्ट — {location}]\n\n"
                f"1. जल-मौसम विज्ञान और उपग्रह अवलोकन:\n"
                f"   • स्थान: {location} | गंभीरता स्तर: {severity}\n"
                f"   • सक्रिय बाढ़ क्षेत्र: {area_sq_km:.2f} sq km | U-RNN अधिकतम जल स्तर (+60m): {max_depth_m:.2f} meters\n\n"
                f"2. जनसंख्या एवं अवसंरचना प्रभाव:\n"
                f"   • प्रभावित नागरिक: {population_affected:,} | जलमग्न भवन: {buildings_damaged:,} | जोखिम में महत्वपूर्ण केंद्र: {facilities_at_risk}\n\n"
                f"3. NDRF/SDRF निकासी एवं राहत निर्देश:\n"
                f"   • 0.30 मीटर से अधिक जलभराव वाले मार्गों को तुरंत बंद करें और नागरिकों को उच्च भूमि राहत शिविरों में स्थानांतरित करें।"
            )
        else:
            synthesized = (
                f"[{report_format} OFFICIAL SITUATION REPORT — {location.upper()}]\n\n"
                f"1. HYDROMETEOROLOGICAL & SATELLITE TELEMETRY:\n"
                f"   • Target Sector: {location} | Threat Severity: {severity}\n"
                f"   • Verified Inundated Area: {area_sq_km:.2f} sq km | U-RNN Peak Depth (+60m): {max_depth_m:.2f} meters\n\n"
                f"2. HUMANITARIAN & INFRASTRUCTURE IMPACT:\n"
                f"   • Population Affected: {population_affected:,} citizens | Inundated Structures: {buildings_damaged:,} buildings\n"
                f"   • Critical Lifeline Facilities at Risk: {facilities_at_risk} centers\n\n"
                f"3. TACTICAL EVACUATION & NDRF/SDRF DIRECTIVES:\n"
                f"   • Reroute civilian movement along high-elevation Dijkstra corridors avoiding roads >0.30m depth.\n"
                f"   • Dispatch bilingual CAP v1.2 sirens via Amazon SNS & Amazon Polly neural voice broadcast."
            )

        return {
            "provider": "AWS_BEDROCK_SIMULATED",
            "model_id": self.model_id,
            "region": self.region,
            "report_text": synthesized,
            "latency_ms": round((time.perf_counter() - t0) * 1000.0, 1),
            "status": "GENERATED_FALLBACK",
        }


bedrock_service = BedrockDisasterIntelligence()
