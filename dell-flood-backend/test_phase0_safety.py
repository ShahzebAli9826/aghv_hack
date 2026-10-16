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

from fastapi.testclient import TestClient
import main

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
