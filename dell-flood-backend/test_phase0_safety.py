import os
import sys
import socket
import tempfile

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(BACKEND_DIR)
SANDBOX_DIR = tempfile.mkdtemp(prefix="aegis_phase0_")

os.environ["STRICT_AUTH"] = "true"
for _secret_key in (
    "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER",
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SNS_TOPIC_ARN",
    "AWS_COGNITO_USER_POOL_ID", "AWS_COGNITO_APP_CLIENT_ID",
    "SMTP_SENDER_EMAIL", "SMTP_SENDER_PASSWORD", "ALERT_RECIPIENT_EMAIL",
    "GEMINI_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    "SENTINEL_CLIENT_ID", "SENTINEL_CLIENT_SECRET",
):
    os.environ[_secret_key] = ""

# Several modules call load_dotenv(override=True); a developer .env must not re-arm real credentials here.
import dotenv
dotenv.load_dotenv = lambda *args, **kwargs: False

_LOOPBACK = {"127.0.0.1", "::1", "localhost"}
_real_connect = socket.socket.connect
_real_getaddrinfo = socket.getaddrinfo


def _loopback_connect(sock, address):
    host = address[0] if isinstance(address, tuple) else address
    if host not in _LOOPBACK:
        raise OSError(f"network disabled in test_phase0_safety: {address}")
    return _real_connect(sock, address)


def _loopback_getaddrinfo(host, *args, **kwargs):
    if host not in _LOOPBACK:
        raise socket.gaierror(f"network disabled in test_phase0_safety: {host}")
    return _real_getaddrinfo(host, *args, **kwargs)


socket.socket.connect = _loopback_connect
socket.getaddrinfo = _loopback_getaddrinfo
sys.modules["chromadb"] = None
sys.path.insert(0, BACKEND_DIR)
os.chdir(SANDBOX_DIR)

import numpy as np
from fastapi.testclient import TestClient
import main
from app.agent import incident_orchestrator, tools
from app.api.auth_deps import normalize_and_validate_phone
from app.api import endpoints
from app.aws import sns_service
from app.ml.inference import get_shared_model

sys.modules["app.aws.dynamodb_service"].LOCAL_FALLBACK_FILE = os.path.join(SANDBOX_DIR, "dynamodb_local_cache.json")
incident_orchestrator.DB_PATH = os.path.join(SANDBOX_DIR, "flood_app.db")
incident_orchestrator._init_orchestrator_tables()

client = TestClient(main.app)

AGENT_CYCLE_BODY = {"location": "Patna District", "lat": 25.6124, "lon": 85.1376}
GATED_ROUTES = [
    ("post", "/api/hitl/approve", {"item_id": "hitl_00000000"}),
    ("get", "/api/hitl/queue", None),
    ("post", "/api/agent-cycle", AGENT_CYCLE_BODY),
    ("post", "/api/agent/trigger-cycle", AGENT_CYCLE_BODY),
    ("post", "/api/aws/provision", None),
    ("post", "/api/aws/test-mcp-suite", None),
    ("post", "/api/mcp/execute", {"tool_name": "get_rainfall_telemetry", "arguments": {"lat": 25.6, "lon": 85.1}}),
    ("post", "/api/alerts/voice", {"phone_number": "+15555550123"}),
    ("post", "/api/alerts/email", {"subject": "s", "message": "m"}),
    ("post", "/api/alerts/email-report", {
        "to_email": "a@example.com", "location": "Patna", "lat": 25.6, "lon": 85.1, "area_sq_km": 1.0,
        "classification": "Flood", "severity": "HIGH", "population_affected": 1, "buildings_damaged": 1,
        "facilities_at_risk": 1,
    }),
    ("post", "/api/notifications/broadcast", {"location": "Patna", "severity": "HIGH", "area_sq_km": 1.0}),
    ("post", "/api/alerts/broadcast-sns", {}),
    ("post", "/api/alerts/voice-polly", {}),
]


def _call(method, path, body=None, headers=None):
    if method == "get":
        return client.get(path, headers=headers)
    return client.post(path, json=body, headers=headers)


def _login(username, password="123"):
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return res.json()


def _official_headers():
    return {"Authorization": f"Bearer {_login('saif')['token']}"}


class _ModelProbability:
    """No trained checkpoint ships with the repo, so tests pin the SegFormer probability map."""

    def __init__(self, value):
        self.value = value
        self.model = get_shared_model()

    def __enter__(self):
        self.model.run_inference = lambda *args, **kwargs: np.full((512, 512), self.value, dtype=np.float32)

    def __exit__(self, *exc):
        del self.model.run_inference


class _SnsRecorder:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        sns_service.broadcast_flood_warning = lambda **kwargs: self.calls.append(kwargs) or {"status": "RECORDED"}
        return self

    def __exit__(self, *exc):
        del sns_service.broadcast_flood_warning


def _pending_draft_ids(headers):
    res = client.get("/api/hitl/queue", headers=headers)
    assert res.status_code == 200, res.text
    return {item["draft_id"]: item for item in res.json()["items"]}


def test_gated_routes_reject_anonymous_callers():
    statuses = {path: _call(method, path, body).status_code for method, path, body in GATED_ROUTES}
    assert statuses == {path: 401 for _, path, _ in GATED_ROUTES}, statuses


def test_registration_cannot_self_assign_official_and_citizens_are_refused():
    reg = client.post(
        "/api/auth/register",
        json={"username": "phase0_citizen", "password": "pw-phase0", "role": "official", "phone": ""},
    )
    assert reg.status_code == 200, reg.text
    login = _login("phase0_citizen", "pw-phase0")
    assert login["role"] == "citizen"
    headers = {"Authorization": f"Bearer {login['token']}"}
    statuses = {path: _call(method, path, body, headers).status_code for method, path, body in GATED_ROUTES}
    assert statuses == {path: 403 for _, path, _ in GATED_ROUTES}, statuses


def test_seeded_official_passes_the_gate():
    res = client.get("/api/hitl/queue", headers=_official_headers())
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "SUCCESS"


def test_forged_token_is_rejected():
    res = client.get("/api/hitl/queue", headers={"Authorization": "Bearer not.a.token"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid or expired Cognito JWT token"


def test_provisioning_is_post_only():
    assert client.get("/api/aws/provision", headers=_official_headers()).status_code == 405


def test_mcp_execute_refuses_dispatch_tools_even_for_officials():
    headers = _official_headers()
    refused = client.post(
        "/api/mcp/execute",
        json={"tool_name": "dispatch_approved_alert", "arguments": {"phone_number": "+15555550123", "location": "Patna", "severity": "CRITICAL"}},
        headers=headers,
    )
    assert refused.status_code == 403
    assert refused.json()["detail"] == "dispatch tools run only through HITL approval"
    sns = client.post(
        "/api/mcp/execute",
        json={"tool_name": "aws_broadcast_alert_sns", "arguments": {"location": "Patna", "severity_level": "CRITICAL"}},
        headers=headers,
    )
    assert sns.status_code == 403
    allowed = client.post(
        "/api/mcp/execute",
        json={"tool_name": "get_rainfall_telemetry", "arguments": {"lat": 25.6, "lon": 85.1}},
        headers=headers,
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["tool_name"] == "get_rainfall_telemetry"
    assert allowed.json()["data"]["antecedent_rain_5d_mm"] == 0.0


def test_hitl_approve_unknown_draft_is_404():
    res = client.post("/api/hitl/approve", json={"item_id": "hitl_doesnotexist"}, headers=_official_headers())
    assert res.status_code == 404
    assert res.json()["detail"] == "HITL draft hitl_doesnotexist does not exist"


def test_agent_cycle_drafts_without_broadcasting_and_approval_dispatches_once():
    headers = _official_headers()
    with _ModelProbability(0.95), _SnsRecorder() as sns:
        result = endpoints.agent.run_cycle(
            location="Phase0 Wet Ward",
            lat=25.6124,
            lon=85.1376,
            phones=["+15555550123"],
            language="en",
        )
        draft_id = result["hitl_draft_id"]
        assert sns.calls == []
        assert result["voice_dispatched"] == {}
        assert _pending_draft_ids(headers)[draft_id]["status"] == "PENDING"

        approved = client.post("/api/hitl/approve", json={"item_id": draft_id, "language": "en"}, headers=headers)
        assert approved.status_code == 200, approved.text
        body = approved.json()
        assert (body["status"], body["approved_by"], body["draft"]["location"]) == ("APPROVED_AND_DISPATCHED", "saif", "Phase0 Wet Ward")
        assert (body["dispatch_receipt"]["mode"], body["dispatch_receipt"]["target"]) == ("simulated_gateway", "+15555550123")
        assert [(c["location"], c["severity_level"]) for c in sns.calls] == [("Phase0 Wet Ward", "CRITICAL")]

        again = client.post("/api/hitl/approve", json={"item_id": draft_id}, headers=headers)
        assert again.status_code == 409
        assert again.json()["detail"] == f"HITL draft {draft_id} is APPROVED_AND_DISPATCHED, not PENDING_OFFICIAL_APPROVAL"
        assert len(sns.calls) == 1
        assert draft_id not in _pending_draft_ids(headers)


def test_skipping_hitl_requires_a_named_official():
    try:
        endpoints.agent.run_cycle(location="Nowhere", lat=0.0, lon=0.0, require_hitl_for_calls=False)
    except ValueError as exc:
        assert str(exc) == "Skipping the HITL queue needs the requesting official as requested_by."
    else:
        raise AssertionError("run_cycle accepted an anonymous auto-approval")


def test_complaint_cluster_creates_a_pending_draft_only():
    headers = _official_headers()
    before = set(_pending_draft_ids(headers))
    with _ModelProbability(0.95), _SnsRecorder() as sns:
        triggered = []
        for i in range(3):
            res = client.post("/api/report-flood", json={
                "username": f"phase0_reporter_{i}", "lat": 26.2001 + i * 0.001, "lon": 84.3001,
                "severity": "HIGH", "description": "water entering homes", "location_name": "Phase0 Cluster Ward",
            })
            assert res.status_code == 200, res.text
            triggered.append(res.json()["agent_auto_triggered"])
        assert triggered == [False, False, True]
        assert sns.calls == []
    new_drafts = [d for draft_id, d in _pending_draft_ids(headers).items() if draft_id not in before]
    assert [(d["location"], d["status"]) for d in new_drafts] == [("Phase0 Cluster Ward", "PENDING")]


def test_diagnostic_suite_never_publishes_to_sns():
    class RecordingSnsClient:
        def __init__(self):
            self.published = []

        def publish(self, **kwargs):
            self.published.append(kwargs)
            return {"MessageId": "fake-message"}

    fake = RecordingSnsClient()
    saved = (sns_service.enabled, sns_service._sns, sns_service.topic_arn)
    sns_service.enabled, sns_service._sns, sns_service.topic_arn = True, fake, "arn:aws:sns:ap-south-1:111111111111:phase0"
    try:
        res = client.post("/api/aws/test-mcp-suite", headers=_official_headers())
        assert res.status_code == 200, res.text
        sns_rows = [r for r in res.json()["data"]["results"] if r["mcp_tool"] == "aws_broadcast_alert_sns"]
        assert [r["service"] for r in sns_rows] == ["Amazon SNS (dry run, nothing published)"]
        assert fake.published == []
        live = sns_service.broadcast_flood_warning(location="Phase0 Live Check")
        assert live["status"] == "BROADCAST_DISPATCHED_LIVE"
        assert [p["Subject"] for p in fake.published] == ["AEGIS FLASH FLOOD ALERT: PHASE0 LIVE CHECK (CRITICAL)"]
    finally:
        sns_service.enabled, sns_service._sns, sns_service.topic_arn = saved


def test_phone_normalization_has_no_fallback_recipient():
    assert [normalize_and_validate_phone(p) for p in ("98765 43210", "+1 (555) 555-0123", "", None, "12", "call me")] == [
        "+919876543210", "+15555550123", None, None, None, None,
    ]


def test_invalid_recipient_places_no_call():
    assert tools.trigger_voice_call("12", location="Patna")["status"] == "NO_RECIPIENT"
    assert tools.trigger_voice_call("+15555550123", location="Patna", message="test")["target"] == "+15555550123"
    assert tools.send_sms_alert("", "test") is False

    headers = _official_headers()
    voice = client.post("/api/alerts/voice", json={"phone_number": "12"}, headers=headers)
    assert voice.status_code == 400
    assert voice.json()["detail"] == "phone_number is missing or not a valid E.164 number; no call was placed."

    with _ModelProbability(0.95), _SnsRecorder():
        draft_id = endpoints.agent.run_cycle(
            location="Phase0 No Recipient Ward", lat=25.6124, lon=85.1376, phones=["not-a-phone"], language="en",
        )["hitl_draft_id"]
        assert _pending_draft_ids(headers)[draft_id]["target_phones"] == []
        approved = client.post("/api/hitl/approve", json={"item_id": draft_id}, headers=headers)
    assert approved.status_code == 200, approved.text
    assert (approved.json()["status"], approved.json()["dispatch_receipt"]["status"]) == ("APPROVED_NO_RECIPIENT", "NO_RECIPIENT")


def _source_files_containing(top, needle):
    skip_dirs = {"node_modules", "venv", ".venv", ".git", ".claude", "__pycache__", ".expo"}
    found = []
    for root, dirs, files in os.walk(top):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for name in files:
            if name.endswith((".py", ".ts", ".tsx")):
                path = os.path.join(root, name)
                with open(path, encoding="utf-8", errors="ignore") as fh:
                    if needle in fh.read():
                        found.append(os.path.relpath(path, top).replace(os.sep, "/"))
    return sorted(found)


def test_hard_coded_recipient_is_gone_from_source():
    needle = "+91" + "7678656930"
    fixture_dir = os.path.join(SANDBOX_DIR, "scan_fixture")
    os.makedirs(os.path.join(fixture_dir, "node_modules"), exist_ok=True)
    for rel in ("planted.tsx", "node_modules/ignored.ts", "notes.md"):
        with open(os.path.join(fixture_dir, rel), "w", encoding="utf-8") as fh:
            fh.write(f'const phone = "{needle}";')
    assert _source_files_containing(fixture_dir, needle) == ["planted.tsx"]
    assert _source_files_containing(REPO_ROOT, needle) == []


def test_cors_default_has_no_wildcard():
    res = client.options(
        "/api/hitl/queue",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in res.headers


if __name__ == "__main__":
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            _fn()
            print(f"PASS {_name}")
