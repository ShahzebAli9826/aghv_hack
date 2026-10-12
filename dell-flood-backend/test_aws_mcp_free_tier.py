import json
import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.mcp.aegis_mcp_server import MCP_TOOLS_REGISTRY, execute_mcp_tool
from app.aws import (
    s3_service,
    dynamodb_service,
    sns_service,
    polly_service,
    cognito_service,
    cloudwatch_service,
    bedrock_service,
    location_service,
    ai_language_service,
    rekognition_service,
    events_sfn_service,
    sqs_ssm_service,
)


def test_direct_mcp_tools():
    print("=" * 72)
    print("1. TESTING AEGIS AWS FREE TIER MCP REGISTRY & STATUS")
    print("=" * 72)
    aws_tools = [t["name"] for t in MCP_TOOLS_REGISTRY if t["name"].startswith("aws_")]
    print(f"Region: {s3_service.region} | Total MCP Tools: {len(MCP_TOOLS_REGISTRY)} | AWS MCP Tools: {len(aws_tools)}")
    for t in aws_tools:
        print(f"  - MCP Tool Registered: {t}")

    print("\n" + "=" * 72)
    print("2. EXECUTING MASTER AWS FREE TIER MCP DIAGNOSTIC SUITE")
    print("=" * 72)
    suite_envelope = execute_mcp_tool(
        "aws_run_free_tier_diagnostic_suite",
        {"location": "Patna District", "lat": 25.6124, "lon": 85.1376},
    )
    assert suite_envelope["status"] == "SUCCESS", f"Suite failed: {suite_envelope}"
    suite_data = suite_envelope["data"]
    for item in suite_data["results"]:
        print(
            f"  [PASS] {item['service']:<28} -> {item['mcp_tool']:<36} "
            f"| {item['latency_ms']:>5.1f} ms | sha256:{item['sha256_hash']}"
        )
    assert suite_data["all_passed"] is True
    assert suite_data["passed_count"] == suite_data["total_services_tested"]
    print(
        f"\nVerified {suite_data['passed_count']}/{suite_data['total_services_tested']} "
        f"AWS Free Tier MCP tools in {suite_data['total_suite_latency_ms']} ms!"
    )


def test_stdio_jsonrpc_mcp_server():
    print("\n" + "=" * 72)
    print("3. TESTING JSON-RPC 2.0 STDIO MCP PROTOCOL TRANSPORT")
    print("=" * 72)
    requests_payload = "\n".join(
        [
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "aws_run_free_tier_diagnostic_suite",
                        "arguments": {"location": "Jorhat, Assam", "lat": 26.7509, "lon": 94.2037},
                    },
                }
            ),
        ]
    ) + "\n"

    proc = subprocess.run(
        [sys.executable, "-m", "app.mcp.aegis_mcp_server"],
        input=requests_payload,
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.abspath(__file__)),
        timeout=30,
    )
    assert proc.returncode == 0, f"STDIO MCP exited with {proc.returncode}: {proc.stderr}"
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip().startswith("{")]
    assert len(lines) >= 3, f"Expected 3 JSON-RPC responses, got {len(lines)}: {proc.stdout}"

    init_resp = json.loads(lines[0])
    list_resp = json.loads(lines[1])
    call_resp = json.loads(lines[2])

    tools = list_resp["result"]["tools"]
    aws_tools = [t["name"] for t in tools if t["name"].startswith("aws_")]
    call_payload = json.loads(call_resp["result"]["content"][0]["text"])

    print(f"  - JSON-RPC initialize: {init_resp['result']['serverInfo']['name']} v{init_resp['result']['serverInfo']['version']}")
    print(f"  - JSON-RPC tools/list: {len(tools)} total tools ({len(aws_tools)} AWS Free Tier MCP tools)")
    print(
        f"  - JSON-RPC tools/call (aws_run_free_tier_diagnostic_suite): "
        f"{call_payload['data']['passed_count']}/{call_payload['data']['total_services_tested']} PASSED "
        f"(Execution ID: {call_payload['provenance']['execution_id']})"
    )


if __name__ == "__main__":
    test_direct_mcp_tools()
    test_stdio_jsonrpc_mcp_server()
    print("\nALL AWS FREE TIER SERVICES & MCP TRANSPORT TESTS PASSED 100%!")
