"""HTTP surface for web intelligence, plus plain functions for the orchestrator and MCP."""
from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from app.api.auth_deps import require_official
from app.intel.config import Mode, Settings, load_settings
from app.intel.evidence import DISCLAIMER, QUALITY_SCORE_NOTE, SCHEMA_VERSION, LocationQuery, ProductId, WebIntelRun
from app.intel.monitors import MonitorKind, MonitorRequestError, MonitorService, MonitorUnavailable, WebhookUnauthorized
from app.intel.products import DEFAULT_PRODUCTS, PRODUCTS
from app.intel.runner import IntelRunner, LiveGateway, ReplayGateway, RunRequest
from app.intel.sources import SOURCES, Resolver, default_resolver, state_code
from app.intel.store import IntelStore
from app.intel.tinyfish_client import TinyFishClient, TinyFishError

PLACE_PATTERN = r"^[\w ,.'()\-]+$"
MAX_WEBHOOK_BYTES = 1_000_000
DEFAULT_MAX_AGE = timedelta(hours=6)


@dataclass
class IntelService:
    settings: Settings
    store: IntelStore
    runner: IntelRunner
    monitors: MonitorService
    client: TinyFishClient | None


def build_service(
    settings: Settings | None = None,
    *,
    store: IntelStore | None = None,
    tinyfish_http: httpx.Client | None = None,
    direct_http: httpx.Client | None = None,
    resolver: Resolver = default_resolver,
    sleep: Callable[[float], None] = time.sleep,
    today: Callable[[], date] | None = None,
) -> IntelService:
    settings = settings or load_settings()
    store = store or IntelStore()
    store.mark_interrupted()
    client = None
    gateway = None
    if settings.mode is Mode.live:
        client = TinyFishClient(settings, tinyfish_http, sleep=sleep)
        gateway = LiveGateway(client, settings, direct_http, resolver)
    elif settings.mode is Mode.replay:
        gateway = ReplayGateway()
    extra = {"today": today} if today else {}
    runner = IntelRunner(settings, store, gateway, sleep=sleep, **extra)
    return IntelService(settings, store, runner, MonitorService(settings, store, client, runner), client)


_service: IntelService | None = None
_service_lock = threading.Lock()


def get_service() -> IntelService:
    global _service
    with _service_lock:
        if _service is None:
            _service = build_service()
        return _service


# --- request bodies ---

class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunBody(_Body):
    location: str = Field(min_length=1, max_length=120, pattern=PLACE_PATTERN)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    state: str | None = Field(default=None, max_length=60, pattern=PLACE_PATTERN)
    district: str | None = Field(default=None, max_length=80, pattern=PLACE_PATTERN)
    products: list[ProductId] | None = Field(default=None, max_length=len(ProductId))
    stream: bool = False


class MonitorBody(_Body):
    kind: MonitorKind
    source_id: str | None = Field(default=None, max_length=64)
    location: str = Field(min_length=1, max_length=120, pattern=PLACE_PATTERN)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    state: str | None = Field(default=None, max_length=60, pattern=PLACE_PATTERN)
    district: str | None = Field(default=None, max_length=80, pattern=PLACE_PATTERN)
    products: list[ProductId] | None = Field(default=None, max_length=len(ProductId))
    schedule_cron: str = Field(default="0 */6 * * *", max_length=100)


def _location(location: str, lat: float, lon: float, state: str | None, district: str | None) -> LocationQuery:
    code = state_code(state)
    if state and code is None:
        raise HTTPException(status_code=422, detail="state must be an Indian state or union territory name")
    clean = lambda s: " ".join(s.split()) if s else None  # noqa: E731
    return LocationQuery(query=clean(location), latitude=round(lat, 4), longitude=round(lon, 4),
                         jurisdiction=code, state=clean(state), district=clean(district))


def _products(requested: list[ProductId] | None) -> tuple[ProductId, ...]:
    return tuple(dict.fromkeys(requested)) if requested else DEFAULT_PRODUCTS


def _describe_products(today: date) -> list[dict]:
    out = []
    for product in PRODUCTS.values():
        entry = product.describe()
        entry["sources"] = [
            {
                "id": s.id, "name": s.name, "authority": s.authority, "access_method": s.access.value,
                "source_type": s.source_type.value, "jurisdictions": sorted(s.jurisdictions),
                "verified": s.verified, "in_season": s.in_season(today),
                "allow_readonly_lookup": s.allow_readonly_lookup, "notes": s.notes,
            }
            for s in (SOURCES[sid] for sid in product.source_ids)
        ]
        out.append(entry)
    return out


def _freshness_status(run: WebIntelRun | None, fresh: bool) -> str:
    if run is None:
        return "NONE_AVAILABLE"
    return "ATTACHED" if fresh else "STALE"


def _lookup(service: IntelService, district: str | None, state: str | None, lat: float | None, lon: float | None,
            max_age: timedelta) -> tuple[WebIntelRun | None, bool]:
    code = state_code(state) or state
    run = service.store.latest_for(district=district, state=code, lat=lat, lon=lon, max_age=max_age)
    if run is not None:
        return run, True
    return service.store.latest_for(district=district, state=code, lat=lat, lon=lon, include_stale=True), False


# --- functions for later wiring (orchestrator WebEvidenceAgent, MCP tools) ---

def latest_evidence_for(
    *,
    district: str | None = None,
    state: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    max_age: timedelta = DEFAULT_MAX_AGE,
    service: IntelService | None = None,
) -> WebIntelRun | None:
    """Most recent succeeded/partial run for a place within max_age, or None. Never starts a run."""
    run, fresh = _lookup(service or get_service(), district, state, lat, lon, max_age)
    return run if fresh else None


def evidence_for_hitl(
    *,
    district: str | None = None,
    state: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    max_age: timedelta = DEFAULT_MAX_AGE,
    max_items: int = 25,
    service: IntelService | None = None,
) -> dict:
    """Compact, JSON-serialisable evidence for a HITL draft. Read-only; cannot change escalation."""
    run, fresh = _lookup(service or get_service(), district, state, lat, lon, max_age)
    status = _freshness_status(run, fresh)
    if run is None:
        return {"status": status, "run_id": None, "evidence": [], "conflicts": [], "failed_sources": [],
                "data_quality": [], "disclaimer": DISCLAIMER, "quality_score_note": QUALITY_SCORE_NOTE}
    keep = ("evidence_id", "claim", "category", "grade", "source_id", "source_name", "source_type", "source_url",
            "retrieved_at", "published_at", "observed_at", "freshness", "validation_status", "location_match",
            "signal", "quality_score", "measurement", "tinyfish_run_id", "mock")
    return {
        "status": status,
        "run_id": run.run_id,
        "run_state": run.state.value,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "summary": run.summary,
        "evidence": [e.model_dump(mode="json", include=set(keep)) for e in run.evidence[:max_items]],
        "conflicts": [c.model_dump(mode="json") for c in run.conflicts],
        "failed_sources": [f.model_dump(mode="json") for f in run.failed_sources],
        "data_quality": list(run.data_quality),
        "disclaimer": DISCLAIMER,
        "quality_score_note": QUALITY_SCORE_NOTE,
    }


# --- routes ---

intel_router = APIRouter(prefix="/api/agent/web-intelligence", tags=["web-intelligence"])
Official = Depends(require_official)


@intel_router.get("/config")
def get_config(_: dict = Official, service: IntelService = Depends(get_service)) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": service.runner.mode.value,
        "enabled": service.runner.mode is not Mode.disabled,
        "products": [p.describe() for p in PRODUCTS.values()],
        "default_products": [p.value for p in DEFAULT_PRODUCTS],
        "limits": service.settings.limits(),
        "monitors_available": service.client is not None,
        "disclaimer": DISCLAIMER,
    }


@intel_router.get("/products")
def get_products(_: dict = Official, service: IntelService = Depends(get_service)) -> dict:
    return {"products": _describe_products(service.runner.today())}


@intel_router.post("/run", status_code=202)
def start_run(body: RunBody, _: dict = Official, service: IntelService = Depends(get_service)) -> dict:
    location = _location(body.location, body.lat, body.lon, body.state, body.district)
    run = service.runner.start(RunRequest(location=location, products=_products(body.products), stream=body.stream))
    return {"run_id": run.run_id, "state": run.state.value}


@intel_router.get("/latest")
def get_latest(
    district: str | None = Query(default=None, max_length=80, pattern=PLACE_PATTERN),
    state: str | None = Query(default=None, max_length=60, pattern=PLACE_PATTERN),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lon: float | None = Query(default=None, ge=-180, le=180),
    max_age_s: int = Query(default=int(DEFAULT_MAX_AGE.total_seconds()), ge=60, le=7 * 86400),
    _: dict = Official,
    service: IntelService = Depends(get_service),
) -> dict:
    if not district and not state and (lat is None or lon is None):
        raise HTTPException(status_code=422, detail="give district, state, or lat and lon")
    run, fresh = _lookup(service, district, state, lat, lon, timedelta(seconds=max_age_s))
    return {"status": _freshness_status(run, fresh), "run": run.model_dump(mode="json") if run else None}


@intel_router.get("/monitors")
def list_monitors(_: dict = Official, service: IntelService = Depends(get_service)) -> dict:
    return {"monitors": service.monitors.list()}


@intel_router.post("/monitors", status_code=201)
def create_monitor(body: MonitorBody, _: dict = Official, service: IntelService = Depends(get_service)) -> dict:
    location = _location(body.location, body.lat, body.lon, body.state, body.district)
    try:
        return service.monitors.create(body.kind, location=location, source_id=body.source_id,
                                       products=_products(body.products), schedule_cron=body.schedule_cron)
    except MonitorUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except MonitorRequestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except TinyFishError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None


@intel_router.delete("/monitors/{monitor_id}")
def delete_monitor(monitor_id: str, _: dict = Official, service: IntelService = Depends(get_service)) -> dict:
    try:
        deleted = service.monitors.delete(monitor_id[:64])
    except MonitorUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except TinyFishError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    if not deleted:
        raise HTTPException(status_code=404, detail="monitor not found")
    return {"deleted": True, "monitor_id": monitor_id}


@intel_router.post("/webhook")
async def webhook(request: Request, token: str | None = Query(default=None, max_length=200),
                  service: IntelService = Depends(get_service)) -> dict:
    raw = await request.body()
    if len(raw) > MAX_WEBHOOK_BYTES:
        raise HTTPException(status_code=413, detail="payload too large")
    try:
        payload = json.loads(raw or b"null")
    except ValueError:
        payload = None
    try:
        return service.monitors.handle_webhook(payload, token)
    except WebhookUnauthorized:
        raise HTTPException(status_code=401, detail="invalid webhook token") from None
    except MonitorUnavailable as exc:
        return {"status": "ignored", "reason": str(exc)}
    except TinyFishError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None


@intel_router.get("/{run_id}")
def get_run(run_id: str, _: dict = Official, service: IntelService = Depends(get_service)) -> dict:
    run = service.runner.get(run_id[:64])
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run.model_dump(mode="json")


@intel_router.post("/{run_id}/cancel")
def cancel_run(run_id: str, _: dict = Official, service: IntelService = Depends(get_service)) -> dict:
    run = service.runner.cancel(run_id[:64])
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {"run_id": run.run_id, "state": run.state.value, "cancel_requested": True}

