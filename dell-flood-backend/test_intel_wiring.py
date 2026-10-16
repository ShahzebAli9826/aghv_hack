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


if __name__ == "__main__":
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            _fn()
            print(f"PASS {_name}")
