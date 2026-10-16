"""Offline tests for wiring app/intel into the API, the incident cycle, SITREP, CAP and MCP.

Run: python -m pytest test_intel_wiring.py -q    or    python test_intel_wiring.py
"""
import json
import os
import socket
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
SANDBOX_DIR = tempfile.mkdtemp(prefix="aegis_wiring_")

os.environ["STRICT_AUTH"] = "true"
os.environ.setdefault("AEGIS_APP_DB", os.path.join(SANDBOX_DIR, "flood_app.db"))
for _secret_key in (
    "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER",
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SNS_TOPIC_ARN",
    "AWS_COGNITO_USER_POOL_ID", "AWS_COGNITO_APP_CLIENT_ID",
    "SMTP_SENDER_EMAIL", "SMTP_SENDER_PASSWORD", "ALERT_RECIPIENT_EMAIL",
    "GEMINI_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    "SENTINEL_CLIENT_ID", "SENTINEL_CLIENT_SECRET", "TINYFISH_API_KEY",
):
    os.environ[_secret_key] = ""

import dotenv
dotenv.load_dotenv = lambda *args, **kwargs: False

_LOOPBACK = {"127.0.0.1", "::1", "localhost"}
_real_connect = socket.socket.connect
_real_getaddrinfo = socket.getaddrinfo


def _loopback_connect(sock, address):
    host = address[0] if isinstance(address, tuple) else address
    if host not in _LOOPBACK:
        raise OSError(f"network disabled in test_intel_wiring: {address}")
    return _real_connect(sock, address)


def _loopback_getaddrinfo(host, *args, **kwargs):
    if host not in _LOOPBACK:
        raise socket.gaierror(f"network disabled in test_intel_wiring: {host}")
    return _real_getaddrinfo(host, *args, **kwargs)


socket.socket.connect = _loopback_connect
socket.getaddrinfo = _loopback_getaddrinfo
sys.modules.setdefault("chromadb", None)
sys.path.insert(0, BACKEND_DIR)
# When another suite already imported main in this process, its cwd holds the seeded flood_database.db.
if "main" not in sys.modules:
    os.chdir(SANDBOX_DIR)

import httpx
import numpy as np
from fastapi.testclient import TestClient

import main
from app.agent import incident_orchestrator
from app.api import endpoints
from app.intel import routes as intel_routes
from app.intel.config import load_settings
from app.intel.evidence import (
    AccessMethod, Evidence, EvidenceCategory, Grade, LocationQuery, Measurement, ProductId, RunState,
    Signal, SourceType, ValidationStatus, WebIntelRun,
)
from app.intel.store import IntelStore
from app.ml.inference import get_shared_model

sys.modules["app.aws.dynamodb_service"].LOCAL_FALLBACK_FILE = os.path.join(SANDBOX_DIR, "dynamodb_local_cache.json")
client = TestClient(main.app)
PATNA = {"location": "Patna, Bihar", "lat": 25.6124, "lon": 85.1376}
_counter = {"n": 0}


def _fresh_env(mode="replay", tinyfish_http=None, api_key=""):
    """New intel store + service and a new HITL table for one test; returns the service."""
    _counter["n"] += 1
    path = os.path.join(SANDBOX_DIR, f"app_{_counter['n']}.db")
    env = {"TINYFISH_MODE": mode, "TINYFISH_API_KEY": api_key}
    service = intel_routes.build_service(load_settings(env), store=IntelStore(path), tinyfish_http=tinyfish_http)
    intel_routes._service = service
    incident_orchestrator.DB_PATH = path
    incident_orchestrator._init_orchestrator_tables()
    return service


def _official_headers():
    res = client.post("/api/auth/login", json={"username": "saif", "password": "123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


class _ModelProbability:
    def __init__(self, value):
        self.value = value
        self.model = get_shared_model()

    def __enter__(self):
        self.model.run_inference = lambda *args, **kwargs: np.full((512, 512), self.value, dtype=np.float32)

    def __exit__(self, *exc):
        del self.model.run_inference


class _ModelMissing:
    def __init__(self):
        self.model = get_shared_model()

    def __enter__(self):
        def boom(*args, **kwargs):
            raise RuntimeError("SegFormer weights not found (best_model_focal.pth)")
        self.model.run_inference = boom

    def __exit__(self, *exc):
        del self.model.run_inference


def _evidence(n, category, claim, *, url="https://ffs.india-water.gov.in/mock", status=ValidationStatus.verified,
              source_type=SourceType.official, grade=Grade.verified_official, notes=None, published_hours_ago=2,
              product=ProductId.river_levels, measurement=None, signal=Signal.unknown):
    now = datetime.now(timezone.utc)
    return Evidence(
        evidence_id=f"ev_{n}", claim=claim, category=category, product_id=product, source_id=f"src_{n}",
        source_name=f"Source {n}", source_type=source_type, source_url=url, retrieved_at=now,
        published_at=now - timedelta(hours=published_hours_ago), district="Patna",
        validation_status=status, grade=grade, signal=signal, access_method=AccessMethod.fetch,
        tinyfish_run_id=f"tf_run_{n}", notes=notes or [], measurement=measurement, mock=True,
    )


def _store_run(service, evidence, *, district="Patna", age=timedelta(0)):
    created = datetime.now(timezone.utc) - age
    run = WebIntelRun(
        run_id=f"wi_test_{_counter['n']}_{len(evidence)}", state=RunState.succeeded, mode="replay",
        products=[ProductId.river_levels], created_at=created, finished_at=created,
        location=LocationQuery(query="Patna, Bihar", latitude=25.6124, longitude=85.1376, jurisdiction="IN-BR",
                               state="Bihar", district=district),
        evidence=evidence,
    )
    service.store.save_run(run)
    return run


def test_intel_router_is_mounted_and_gated():
    _fresh_env()
    assert client.get("/api/agent/web-intelligence/config").status_code == 401
    res = client.get("/api/agent/web-intelligence/config", headers=_official_headers())
    assert res.status_code == 200, res.text
    assert (res.json()["mode"], res.json()["enabled"]) == ("replay", True)



def _patna_evidence():
    return [
        _evidence(1, EvidenceCategory.river_level, "Ganga at Gandhi Ghat 49.10 m, 0.50 m above danger level 48.60 m",
                  measurement=Measurement(station="Gandhi Ghat", river="Ganga", value=49.1, unit="m", danger_level=48.6),
                  signal=Signal.elevated),
        _evidence(2, EvidenceCategory.official_alert, "Severe flood situation on Ganga at Patna (SACHET CAP)",
                  url="https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier=1",
                  product=ProductId.official_alerts, signal=Signal.elevated),
    ]


def test_cycle_attaches_stored_evidence_to_the_hitl_draft():
    service = _fresh_env()
    run = _store_run(service, _patna_evidence())
    headers = _official_headers()
    with _ModelProbability(0.95):
        result = endpoints.agent.run_cycle(language="en", **PATNA)
    assert result["agent_nodes_status"]["WebEvidenceAgent"] == "ATTACHED"
    assert (result["web_intelligence"]["run_id"], result["web_intelligence"]["affects_escalation"]) == (run.run_id, False)
    queue = client.get("/api/hitl/queue", headers=headers).json()["items"]
    item = next(i for i in queue if i["draft_id"] == result["hitl_draft_id"])
    web = item["web_evidence"]
    assert (web["status"], web["run_id"]) == ("ATTACHED", run.run_id)
    assert [(e["claim"], e["mock"]) for e in web["evidence"]] == [
        ("Ganga at Gandhi Ghat 49.10 m, 0.50 m above danger level 48.60 m", True),
        ("Severe flood situation on Ganga at Patna (SACHET CAP)", True),
    ]


def test_stale_and_missing_evidence_are_labelled():
    service = _fresh_env()
    with _ModelProbability(0.0):
        none = incident_orchestrator.get_incident_orchestrator().run_incident_graph("Patna, Bihar", 25.6124, 85.1376, language="en")
    _store_run(service, _patna_evidence(), age=timedelta(hours=30))
    with _ModelProbability(0.0):
        stale = incident_orchestrator.get_incident_orchestrator().run_incident_graph("Patna, Bihar", 25.6124, 85.1376, language="en")
    assert (none["agent_nodes_status"]["WebEvidenceAgent"], none["web_intelligence"]["evidence"]) == ("NONE_AVAILABLE", [])
    assert stale["agent_nodes_status"]["WebEvidenceAgent"] == "STALE"
    assert len(stale["web_intelligence"]["evidence"]) == 2


def test_web_evidence_never_changes_escalation():
    orchestrator = incident_orchestrator.get_incident_orchestrator()

    def outcome(with_evidence, probability):
        service = _fresh_env()
        if with_evidence:
            _store_run(service, _patna_evidence())
        with _ModelProbability(probability):
            res = orchestrator.run_incident_graph("Patna, Bihar", 25.6124, 85.1376, language="en")
        return res["agent_nodes_status"]["WebEvidenceAgent"], (res["escalation_tier"], res["severity"], res["escalation_reasons"])

    for probability in (0.0, 0.95):
        bare_status, bare = outcome(False, probability)
        web_status, web = outcome(True, probability)
        assert (bare_status, web_status) == ("NONE_AVAILABLE", "ATTACHED")
        assert web == bare, (probability, web, bare)
    assert outcome(True, 0.0)[1][:2] == ("NONE", "LOW")


def test_agent_cycle_makes_no_tinyfish_call():
    seen = []

    def record(request):
        seen.append(str(request.url))
        return httpx.Response(500, json={"error": {"code": "UNEXPECTED"}})

    service = _fresh_env(mode="live", api_key="tf_test_key_0000000000", tinyfish_http=httpx.Client(transport=httpx.MockTransport(record)))
    _store_run(service, _patna_evidence())
    started = []
    real_start = service.runner.start
    service.runner.start = lambda request: started.append(request) or real_start(request)
    try:
        with _ModelProbability(0.0):
            res = client.post("/api/agent-cycle", json={"location": "Patna, Bihar", "lat": 25.6124, "lon": 85.1376},
                              headers=_official_headers())
    finally:
        del service.runner.start
    assert res.status_code == 200, res.text
    assert res.json()["web_intelligence"]["status"] == "ATTACHED"
    assert (seen, started) == ([], [])


if __name__ == "__main__":
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            _fn()
            print(f"PASS {_name}")
