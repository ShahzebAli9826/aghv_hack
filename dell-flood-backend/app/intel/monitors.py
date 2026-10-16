"""F2: TinyFish Page/Topic monitors and the webhook that turns a real change into a web-intel run.

A webhook body is only a hint: TinyFish documents no signature. We check our shared
token, dedupe, confirm the monitor with the API key, and re-read the page or query
ourselves before deciding anything changed. The only action a change can cause is
a new evidence run for a human to review; nothing here dispatches alerts.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import re
from datetime import datetime, timezone
from enum import StrEnum

from app.intel.config import Settings
from app.intel.evidence import LocationQuery, ProductId
from app.intel.products import DEFAULT_PRODUCTS
from app.intel.runner import IntelRunner, RunRequest
from app.intel.sources import SOURCES, url_rejection
from app.intel.store import IntelStore
from app.intel.tinyfish_client import TinyFishClient, TinyFishError

log = logging.getLogger("aegis.intel.monitors")

_CRON = re.compile(r"^(\S+\s+){4}\S+$")
_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_INVALID_ID = {"status": "ignored", "reason": "invalid id"}
MAX_MONITORS = 50


class MonitorKind(StrEnum):
    page = "page"
    topic = "topic"


_TINYFISH_TYPE = {MonitorKind.page: "fetch", MonitorKind.topic: "search"}


class MonitorUnavailable(Exception):
    pass


class MonitorRequestError(ValueError):
    pass


class WebhookUnauthorized(Exception):
    pass


def topic_cron_ok(cron: str) -> bool:
    """Topic monitors must run at least 30 minutes apart (TinyFish rule)."""
    minute = cron.split()[0]
    step = re.fullmatch(r"\*/(\d+)", minute)
    if step:
        return int(step.group(1)) >= 30
    parts = minute.split(",")
    if not all(p.isdigit() for p in parts):
        return False
    values = sorted(int(p) for p in parts)
    gaps = [b - a for a, b in zip(values, values[1:])] + ([60 - values[-1] + values[0]] if len(values) > 1 else [])
    return all(g >= 30 for g in gaps)


def content_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()


class MonitorService:
    def __init__(self, settings: Settings, store: IntelStore, client: TinyFishClient | None, runner: IntelRunner):
        self._settings = settings
        self._store = store
        self._client = client
        self._runner = runner

    def _require_client(self) -> TinyFishClient:
        if self._client is None:
            raise MonitorUnavailable("monitors need TINYFISH_MODE=live with an API key")
        return self._client

    def _webhook_url(self) -> str | None:
        if self._settings.public_base_url and self._settings.webhook_token:
            return f"{self._settings.public_base_url}/api/agent/web-intelligence/webhook?token={self._settings.webhook_token}"
        return None

    def _observe(self, record: dict) -> str | None:
        """Authoritative re-read with our own key: page text hash, or the set of result URLs."""
        client = self._require_client()
        try:
            if record["kind"] == MonitorKind.page:
                result = client.fetch([record["target"]])
                return content_hash(result.pages[0].text) if result.pages else None
            hits = client.search(record["target"], domain_type="news")
            return content_hash("\n".join(sorted(h.url for h in hits)))
        except TinyFishError:
            return None

    def create(self, kind: MonitorKind, *, location: LocationQuery, source_id: str | None,
               products: tuple[ProductId, ...], schedule_cron: str) -> dict:
        client = self._require_client()
        if not _CRON.match(schedule_cron.strip()):
            raise MonitorRequestError("schedule_cron must be a five-field cron expression")
        if len(self._store.list_monitors()) >= MAX_MONITORS:
            raise MonitorRequestError(f"TinyFish allows at most {MAX_MONITORS} monitors per account")
        if kind is MonitorKind.page:
            source = SOURCES.get(source_id or "")
            if source is None or not source.start_url:
                raise MonitorRequestError("page monitors need a registry source_id with a start_url")
            if url_rejection(source.start_url, source.domains) is not None:
                raise MonitorRequestError("source start_url is not allowlisted")
            if not source.verified and not self._settings.allow_unverified_sources:
                raise MonitorRequestError("source is not verified")
            target = source.start_url
            config = {"url": target, "format": "markdown"}
        else:
            place = location.district or location.state
            if not place:
                raise MonitorRequestError("topic monitors need a district or state")
            if not topic_cron_ok(schedule_cron):
                raise MonitorRequestError("topic monitors must run at least 30 minutes apart")
            target = f"{place} flood"
            config = {"query": target, "result_limit": 10, "recency_minutes": 1440}
        monitor = client.create_monitor(
            type_=_TINYFISH_TYPE[kind], config=config, schedule_cron=schedule_cron.strip(),
            name=f"Aegis {kind.value}: {location.district or location.state or source_id}"[:100],
            purpose="Detect new official flood bulletins, warnings or reports for this area.",
            webhook_url=self._webhook_url(),
        )
        record = {
            "monitor_id": monitor.id, "kind": kind.value, "target": target, "source_id": source_id,
            "district": location.district, "state": location.state, "jurisdiction": location.jurisdiction,
            "query": location.query, "latitude": location.latitude, "longitude": location.longitude,
            "products": [p.value for p in products], "schedule_cron": schedule_cron.strip(),
            "created_at": datetime.now(timezone.utc).isoformat(), "webhook_configured": self._webhook_url() is not None,
        }
        try:
            record["baseline_hash"] = self._observe(record)
            self._store.save_monitor(record)
        except BaseException:
            self._delete_remote_quietly(client, monitor.id)
            raise
        return _public(record)

    def _delete_remote_quietly(self, client: TinyFishClient, monitor_id: str) -> None:
        """A remote monitor with no local record would keep running and calling the webhook unseen."""
        try:
            client.delete_monitor(monitor_id)
        except TinyFishError as exc:
            log.warning("could not delete orphaned TinyFish monitor: %s", type(exc).__name__)

    def list(self) -> list[dict]:
        return [_public(r) for r in self._store.list_monitors()]

    def delete(self, monitor_id: str) -> bool:
        if self._store.get_monitor(monitor_id) is None:
            return False
        client = self._require_client()
        try:
            client.delete_monitor(monitor_id)
        except TinyFishError as exc:
            if exc.status_code != 404:
                raise
        return self._store.delete_monitor(monitor_id)

    def authorize_webhook(self, token: str | None) -> None:
        expected = self._settings.webhook_token
        if not expected or not token or not hmac.compare_digest(token.encode("utf-8"), expected.encode("utf-8")):
            raise WebhookUnauthorized("bad webhook token")

    def handle_webhook(self, payload: object) -> dict:
        """Act on a webhook body. The caller must have passed authorize_webhook first."""
        if not isinstance(payload, dict):
            return {"status": "ignored", "reason": "unrecognised payload"}
        monitor_id = payload.get("fetch_monitor_id") or payload.get("search_monitor_id")
        if monitor_id:
            event_id = payload.get("id") or ""
            if not _plain_id(monitor_id) or (event_id and not _plain_id(event_id)):
                return _INVALID_ID
            return self._monitor_event(monitor_id, event_id)
        if payload.get("run_id") and payload.get("event"):
            return self._run_event(payload["run_id"]) if _plain_id(payload["run_id"]) else _INVALID_ID
        return {"status": "ignored", "reason": "unrecognised payload"}

    def _once(self, key: str, process) -> dict | None:
        """Run `process` only for the first delivery of `key`; a failed attempt can be redelivered."""
        if not self._store.record_webhook_event(key):
            return None
        try:
            return process()
        except Exception:
            self._store.forget_webhook_event(key)
            raise

    def _run_event(self, run_id: str) -> dict:
        def process() -> dict:
            run = self._require_client().get_run(run_id)
            return {"status": "acknowledged", "run_id": run_id, "verified_status": run.status}

        return self._once(f"run:{run_id}", process) or {"status": "duplicate", "run_id": run_id}

    def _monitor_event(self, monitor_id: str, event_id: str) -> dict:
        record = self._store.get_monitor(monitor_id)
        if record is None:
            return {"status": "ignored", "reason": "unknown monitor"}
        if not event_id:
            return {"status": "ignored", "reason": "missing monitor run id"}
        return self._once(f"monitor_run:{monitor_id}:{event_id}", lambda: self._verify_change(monitor_id, record)) \
            or {"status": "duplicate", "monitor_id": monitor_id}

    def _verify_change(self, monitor_id: str, record: dict) -> dict:
        self._require_client().get_monitor(monitor_id)
        current = self._observe(record)
        if current is None:
            return {"status": "unverified", "monitor_id": monitor_id, "reason": "could not re-read the target"}
        if current == record.get("baseline_hash"):
            return {"status": "no_change", "monitor_id": monitor_id}
        self._store.set_monitor_baseline(monitor_id, current)
        location = LocationQuery(
            query=record.get("query") or record.get("district") or record.get("state") or "monitor",
            latitude=record["latitude"], longitude=record["longitude"], jurisdiction=record.get("jurisdiction"),
            state=record.get("state"), district=record.get("district"),
        )
        products = tuple(ProductId(p) for p in record.get("products") or []) or DEFAULT_PRODUCTS
        run = self._runner.start(RunRequest(location=location, products=products))
        return {"status": "change_detected", "monitor_id": monitor_id, "run_id": run.run_id}


def _plain_id(value: object) -> bool:
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _public(record: dict) -> dict:
    keys = ("monitor_id", "kind", "target", "source_id", "district", "state", "products", "schedule_cron",
            "created_at", "webhook_configured")
    return {k: record.get(k) for k in keys}
