"""MCP read-tier tools over app/intel. Each returns (data, provenance extras) for the MCP ledger."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Callable, Dict, Optional, Tuple

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.intel.evidence import ProductId, WebIntelRun
from app.intel.routes import PLACE_PATTERN, RunBody, _location, _products, evidence_for_hitl, get_service
from app.intel.runner import RunRequest

ToolResult = Tuple[Dict[str, Any], Optional[Dict[str, Any]]]


class MCPToolInputError(ValueError):
    """Arguments failed validation; the HTTP layer answers 422."""


class _GetRunArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str = Field(min_length=1, max_length=64)


class _LatestArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    district: Optional[str] = Field(default=None, max_length=80, pattern=PLACE_PATTERN)
    state: Optional[str] = Field(default=None, max_length=60, pattern=PLACE_PATTERN)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lon: Optional[float] = Field(default=None, ge=-180, le=180)
    max_age_s: int = Field(default=6 * 3600, ge=60, le=7 * 86400)


def _parse(model, arguments: Dict[str, Any]):
    try:
        return model.model_validate(arguments)
    except ValidationError as exc:
        details = "; ".join(f"{'.'.join(map(str, e['loc'])) or 'arguments'}: {e['msg']}" for e in exc.errors())
        raise MCPToolInputError(details) from None


def _run_meta(run: WebIntelRun) -> Dict[str, Any]:
    meta = run.agent_metadata
    return {
        "run_id": run.run_id,
        "state": run.state.value,
        "tinyfish_run_ids": list(meta.tinyfish_run_ids),
        "num_of_steps": meta.num_of_steps,
        "estimated_cost_usd": meta.estimated_cost_usd,
    }


def start_run(arguments: Dict[str, Any]) -> ToolResult:
    body = _parse(RunBody, arguments)
    try:
        location = _location(body.location, body.lat, body.lon, body.state, body.district)
    except HTTPException as exc:
        raise MCPToolInputError(str(exc.detail)) from None
    # MCP output never carries the live view, so a streamed run would only cost more.
    run = get_service().runner.start(RunRequest(location=location, products=_products(body.products), stream=False))
    return {"run_id": run.run_id, "state": run.state.value, "mode": run.mode}, _run_meta(run)


def get_run(arguments: Dict[str, Any]) -> ToolResult:
    args = _parse(_GetRunArgs, arguments)
    run = get_service().runner.get(args.run_id)
    if run is None:
        raise MCPToolInputError(f"web-intel run {args.run_id} not found")
    return run.model_dump(mode="json", exclude={"live_view"}), _run_meta(run)


def latest_evidence(arguments: Dict[str, Any]) -> ToolResult:
    args = _parse(_LatestArgs, arguments)
    if not args.district and not args.state and (args.lat is None or args.lon is None):
        raise MCPToolInputError("give district, state, or lat and lon")
    data = evidence_for_hitl(district=args.district, state=args.state, lat=args.lat, lon=args.lon,
                             max_age=timedelta(seconds=args.max_age_s))
    if data["run_id"] is None:
        return data, None
    ids = sorted({e["tinyfish_run_id"] for e in data["evidence"] if e.get("tinyfish_run_id")})
    return data, {"run_id": data["run_id"], "state": data.get("run_state"), "tinyfish_run_ids": ids}


WEB_INTEL_TOOLS: Dict[str, Callable[[Dict[str, Any]], ToolResult]] = {
    "web_intel_start_run": start_run,
    "web_intel_get_run": get_run,
    "web_intel_latest_evidence": latest_evidence,
}

_PLACE = {"type": "string", "maxLength": 120, "pattern": PLACE_PATTERN}

WEB_INTEL_REGISTRY = [
    {
        "name": "web_intel_start_run",
        "description": "Starts a background TinyFish web-intelligence run that collects official flood evidence "
                       "(CWC, IMD, SACHET, state bulletins) for a place. Evidence is for human review only; it cannot "
                       "trigger alerts. Cost-bearing in live mode. Poll with web_intel_get_run.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "location": _PLACE,
                "lat": {"type": "number", "minimum": -90, "maximum": 90},
                "lon": {"type": "number", "minimum": -180, "maximum": 180},
                "state": {**_PLACE, "maxLength": 60},
                "district": {**_PLACE, "maxLength": 80},
                "products": {"type": "array", "items": {"type": "string", "enum": [p.value for p in ProductId]}},
            },
            "required": ["location", "lat", "lon"],
            "additionalProperties": False,
        },
        "requires_official_approval": False,
    },
    {
        "name": "web_intel_get_run",
        "description": "Returns the state and evidence of a web-intelligence run (no live-view URL).",
        "inputSchema": {
            "type": "object",
            "properties": {"run_id": {"type": "string", "maxLength": 64}},
            "required": ["run_id"],
            "additionalProperties": False,
        },
        "requires_official_approval": False,
    },
    {
        "name": "web_intel_latest_evidence",
        "description": "Returns stored official-source evidence for a district, state, or lat/lon (latest run). "
                       "Never starts a run.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "district": {**_PLACE, "maxLength": 80},
                "state": {**_PLACE, "maxLength": 60},
                "lat": {"type": "number", "minimum": -90, "maximum": 90},
                "lon": {"type": "number", "minimum": -180, "maximum": 180},
                "max_age_s": {"type": "integer", "minimum": 60, "maximum": 604800},
            },
            "additionalProperties": False,
        },
        "requires_official_approval": False,
    },
]
