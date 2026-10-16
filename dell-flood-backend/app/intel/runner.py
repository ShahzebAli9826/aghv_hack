"""Web-intelligence run orchestration.

A run moves queued -> running -> (succeeded | partial | failed | cancelled), or is
created directly in `disabled`. Source tasks run on a thread pool; each returns a
TaskOutcome, and only the run thread folds outcomes into the run and persists it,
so polling shows partial progress after every source.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Any, Protocol

import httpx

from app.intel.config import Mode, Settings
from app.intel.direct import DirectFetchError, safe_get
from app.intel.evidence import (
    AccessMethod,
    AgentMetadata,
    Conflict,
    Evidence,
    EvidenceCategory,
    FailedSource,
    FailureReason,
    Freshness,
    Grade,
    LiveView,
    LocationMatch,
    LocationQuery,
    ProductId,
    RunState,
    SourceTaskStatus,
    TaskState,
    WebIntelRun,
)
from app.intel.products import (
    DEFAULT_PRODUCTS,
    PRODUCTS,
    AgentRaw,
    ApiRaw,
    FeedRaw,
    GoalInputs,
    HitsRaw,
    PagesRaw,
    ParseCtx,
    ParseFailure,
    Product,
    Raw,
    ResearchRaw,
)
from app.intel.sources import SOURCES, Resolver, Source, default_resolver, url_rejection
from app.intel.store import IntelStore
from app.intel.tinyfish_client import (
    AgentRun,
    CostLedger,
    FetchResult,
    ResearchRun,
    SearchHit,
    TinyFishClient,
    TinyFishError,
    _normalize_fetch,
    _normalize_research,
    _normalize_run,
    _normalize_search,
)
from app.intel.validation import (
    IST,
    RunVerdict,
    assess,
    dedupe,
    detect_conflicts,
    envelope,
    grade,
    judge_run,
    quality_score,
)

log = logging.getLogger("aegis.intel.runner")

FIXTURE_DIR = Path(__file__).with_name("fixtures")
LIVE_VIEW_TTL = timedelta(hours=24)
DEFAULT_RETRY_WAIT_S = 5.0


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- requests and planning ---

@dataclass(frozen=True)
class RunRequest:
    location: LocationQuery
    products: tuple[ProductId, ...] = DEFAULT_PRODUCTS
    stream: bool = False

    @property
    def key(self) -> str:
        loc = self.location
        place = (loc.district or "").lower() or f"{loc.latitude:.1f},{loc.longitude:.1f}"
        raw = json.dumps([sorted(p.value for p in self.products), place, loc.jurisdiction or ""])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


@dataclass(frozen=True)
class SourceTask:
    product: Product
    source: Source
    stream: bool = False


def plan(
    products: tuple[ProductId, ...], location: LocationQuery, settings: Settings, today: date, stream: bool = False
) -> tuple[list[SourceTask], list[FailedSource]]:
    """Choose source tasks for the requested products. Pure."""
    tasks: list[SourceTask] = []
    skipped: list[FailedSource] = []
    stream_assigned = False
    for pid in products:
        product = PRODUCTS[pid]
        sources = [SOURCES[sid] for sid in product.source_ids if SOURCES[sid].covers(location.jurisdiction)]
        runnable: set[str] = set()
        for source in sorted(sources, key=lambda s: s.fallback_of is not None):
            if source.requires_setting and not getattr(settings, source.requires_setting):
                continue
            if source.fallback_of and source.fallback_of in runnable:
                continue
            if not source.verified and not settings.allow_unverified_sources:
                skipped.append(FailedSource(source_id=source.id, product_id=pid, reason=FailureReason.unverified_source,
                                            detail=source.notes[:300]))
                continue
            if not source.in_season(today):
                skipped.append(FailedSource(source_id=source.id, product_id=pid, reason=FailureReason.out_of_season,
                                            detail=f"{source.name} publishes only in season; today is {today.isoformat()}"))
                continue
            use_stream = stream and not stream_assigned and source.access is AccessMethod.agent
            stream_assigned = stream_assigned or use_stream
            tasks.append(SourceTask(product=product, source=source, stream=use_stream))
            runnable.add(source.id)
    return tasks, skipped


# --- gateways: live TinyFish + direct HTTP, or recorded fixtures ---

class Gateway(Protocol):
    mock: bool

    def run_agent(self, source: Source, goal: str, schema: dict | None, *, ledger: CostLedger, stream: bool,
                  on_started: Callable[[str], None], on_streaming_url: Callable[[str, str | None], None],
                  cancel_event: threading.Event, webhook_url: str | None) -> AgentRun: ...

    def fetch(self, source: Source, urls: list[str]) -> FetchResult: ...

    def search(self, source: Source, query: str, domain_type: str | None) -> list[SearchHit]: ...

    def research(self, source: Source, query: str, cancel_event: threading.Event) -> ResearchRun: ...

    def get_text(self, source: Source, url: str) -> tuple[str, str]: ...

    def api_get(self, source: Source, url: str) -> Any: ...


class LiveGateway:
    mock = False

    def __init__(self, client: TinyFishClient, settings: Settings, http: httpx.Client | None = None,
                 resolver: Resolver = default_resolver):
        self._client = client
        self._settings = settings
        self._http = http or httpx.Client(timeout=settings.http_timeout_s, follow_redirects=False,
                                          headers={"User-Agent": "Aegis-FloodIntel/1.1"})
        self._resolver = resolver

    def run_agent(self, source, goal, schema, *, ledger, stream, on_started, on_streaming_url, cancel_event,
                  webhook_url):
        return self._client.run_agent(source.start_url, goal, schema, ledger=ledger, stream=stream,
                                      on_started=on_started, on_streaming_url=on_streaming_url,
                                      cancel_event=cancel_event, webhook_url=webhook_url)

    def fetch(self, source, urls):
        return self._client.fetch(urls)

    def search(self, source, query, domain_type):
        return self._client.search(query, include_domains=source.domains, domain_type=domain_type)

    def research(self, source, query, cancel_event):
        return self._client.run_research(query, domains=source.domains, recency_minutes=72 * 60,
                                         cancel_event=cancel_event)

    def get_text(self, source, url):
        return safe_get(self._http, url, source.domains, resolver=self._resolver)

    def api_get(self, source, url):
        # unverified: IMD API auth. api_reference.html documents no header; a Bearer
        # token is assumed. Confirm when the IMD key is issued (source stays verified=False).
        _, text = safe_get(self._http, url, source.domains, resolver=self._resolver,
                           headers={"Authorization": f"Bearer {self._settings.imd_api_key}"})
        return json.loads(text)


_TS_TOKEN = re.compile(r"\{\{ts:([+-]\d+)([mhd])(?::(iso|dmy|rfc))?\}\}")
_TS_UNITS = {"m": "minutes", "h": "hours", "d": "days"}


def render_fixture_times(text: str, now: datetime) -> str:
    """Replace {{ts:-2h}} style tokens with times relative to `now`, so mock data keeps a realistic age."""

    def sub(match: re.Match) -> str:
        moment = (now + timedelta(**{_TS_UNITS[match[2]]: int(match[1])})).astimezone(IST)
        style = match[3] or "iso"
        if style == "dmy":
            return moment.strftime("%d-%m-%Y %H:%M")
        if style == "rfc":
            return format_datetime(moment.astimezone(timezone.utc), usegmt=True)
        return moment.isoformat(timespec="seconds")

    return _TS_TOKEN.sub(sub, text)


class ReplayGateway:
    """Serves recorded responses from app/intel/fixtures/<source_id>.json. Output is always marked mock."""

    mock = True

    def __init__(self, fixture_dir: Path = FIXTURE_DIR, now: Callable[[], datetime] = utcnow):
        self._dir = fixture_dir
        self._now = now

    def _fixture(self, source: Source) -> dict:
        path = self._dir / f"{source.id}.json"
        if not path.is_file():
            raise DirectFetchError(f"no replay fixture for {source.id}")
        return json.loads(render_fixture_times(path.read_text(encoding="utf-8"), self._now()))

    def run_agent(self, source, goal, schema, *, ledger, stream, on_started, on_streaming_url, cancel_event,
                  webhook_url):
        run = _normalize_run(self._fixture(source)["run"])
        on_started(run.run_id)
        return run

    def fetch(self, source, urls):
        return _normalize_fetch(self._fixture(source)["fetch"])

    def search(self, source, query, domain_type):
        return _normalize_search(self._fixture(source)["search"])

    def research(self, source, query, cancel_event):
        return _normalize_research(self._fixture(source)["research"])

    def get_text(self, source, url):
        fixture = self._fixture(source)
        if url == source.start_url:
            return url, fixture["feed"]
        if url in fixture.get("linked", {}):
            return url, fixture["linked"][url]
        raise DirectFetchError("url not in replay fixture")

    def api_get(self, source, url):
        return self._fixture(source)["payload"]


# --- task execution ---

class VerdictFailure(Exception):
    def __init__(self, verdict: RunVerdict, run_id: str | None):
        super().__init__(verdict.detail or "")
        self.verdict = verdict
        self.run_id = run_id


@dataclass
class TaskMeta:
    run_ids: list[str] = field(default_factory=list)
    run_statuses: dict[str, str] = field(default_factory=dict)
    result_statuses: dict[str, str] = field(default_factory=dict)
    steps: int = 0


@dataclass(frozen=True)
class TaskOutcome:
    index: int
    task: SourceTask
    evidence: tuple[Evidence, ...]
    failure: FailedSource | None
    meta: TaskMeta
    cancelled: bool = False


@dataclass
class ExecCtx:
    gateway: Gateway
    settings: Settings
    location: LocationQuery
    inputs: GoalInputs
    ledger: CostLedger
    cancel_event: threading.Event
    on_streaming_url: Callable[[str, str | None], None]
    sleep: Callable[[float], None]
    meta: TaskMeta
    webhook_url: str | None


def _exec_agent(task: SourceTask, ctx: ExecCtx) -> Raw:
    schema = task.product.output_schema
    goal = task.product.goal(ctx.inputs, task.source)

    def started(run_id: str) -> None:
        ctx.meta.run_ids.append(run_id)

    run = ctx.gateway.run_agent(task.source, goal, schema, ledger=ctx.ledger, stream=task.stream,
                                on_started=started, on_streaming_url=ctx.on_streaming_url,
                                cancel_event=ctx.cancel_event, webhook_url=ctx.webhook_url)
    if run.run_id and run.run_id not in ctx.meta.run_ids:
        ctx.meta.run_ids.append(run.run_id)
    ctx.meta.run_statuses[run.run_id] = run.status
    if isinstance(run.result, dict):
        ctx.meta.result_statuses[run.run_id] = str(run.result.get("status") or "n/a")
    ctx.meta.steps += run.num_of_steps or 0
    verdict = judge_run(run.status, run.result, run.error, envelope(schema), run.profile_hint_reason)
    if not verdict.ok:
        raise VerdictFailure(verdict, run.run_id)
    return AgentRaw(verdict.result)


def _exec_fetch(task: SourceTask, ctx: ExecCtx) -> Raw:
    result = ctx.gateway.fetch(task.source, [task.source.start_url])
    if not result.pages:
        detail = "; ".join(f"{err} ({status})" for _, err, status in result.errors)[:200] or "no content"
        raise DirectFetchError(f"fetch failed: {detail}")
    return PagesRaw(result.pages)


def _exec_search(task: SourceTask, ctx: ExecCtx) -> Raw:
    query = task.product.search_query(ctx.inputs)
    hits = ctx.gateway.search(task.source, query, task.product.search_domain_type)
    allowed = tuple(h for h in hits if url_rejection(h.url, task.source.domains) is None)
    if not task.product.fetch_search_hits:
        return HitsRaw(allowed)
    urls = [h.url for h in allowed[: task.product.fetch_search_hits]]
    if not urls:
        return PagesRaw(())
    return PagesRaw(ctx.gateway.fetch(task.source, urls).pages)


def _exec_research(task: SourceTask, ctx: ExecCtx) -> Raw:
    run = ctx.gateway.research(task.source, task.product.search_query(ctx.inputs), ctx.cancel_event)
    ctx.meta.run_ids.append(run.research_run_id)
    ctx.meta.run_statuses[run.research_run_id] = run.status
    return ResearchRaw(run)


def _exec_rss(task: SourceTask, ctx: ExecCtx, parse_ctx: ParseCtx) -> Raw:
    feed_url, text = ctx.gateway.get_text(task.source, task.source.start_url)
    linked: dict[str, str] = {}
    if task.product.links_to_follow:
        for link in task.product.links_to_follow(text, parse_ctx):
            try:
                linked[link] = ctx.gateway.get_text(task.source, link)[1]
            except DirectFetchError:
                continue
    return FeedRaw(feed_url, text, linked)


def _exec_api(task: SourceTask, ctx: ExecCtx) -> Raw:
    return ApiRaw(ctx.gateway.api_get(task.source, task.source.start_url))


EXECUTORS: dict[AccessMethod, Callable[..., Raw]] = {
    AccessMethod.agent: _exec_agent,
    AccessMethod.fetch: _exec_fetch,
    AccessMethod.search: _exec_search,
    AccessMethod.research: _exec_research,
    AccessMethod.api: _exec_api,
}


def _retry_wait(exc: Exception) -> float | None:
    """Seconds to wait before the single retry, or None when the failure is not retryable."""
    if isinstance(exc, VerdictFailure) and exc.verdict.retryable:
        return exc.verdict.retry_after_s
    if isinstance(exc, TinyFishError) and exc.retryable and exc.reason is not FailureReason.budget_exceeded:
        return exc.retry_after_s if exc.retry_after_s is not None else DEFAULT_RETRY_WAIT_S
    return None


def _failure(task: SourceTask, exc: Exception) -> FailedSource:
    base = {"source_id": task.source.id, "product_id": task.product.id}
    if isinstance(exc, VerdictFailure):
        v = exc.verdict
        return FailedSource(**base, reason=v.reason, detail=v.detail, retry_after_s=v.retry_after_s,
                            tinyfish_run_id=exc.run_id)
    if isinstance(exc, ParseFailure):
        return FailedSource(**base, reason=exc.reason, detail=exc.detail[:300])
    if isinstance(exc, TinyFishError):
        return FailedSource(**base, reason=exc.reason, detail=str(exc)[:300], retry_after_s=exc.retry_after_s,
                            tinyfish_run_id=exc.run_id)
    if isinstance(exc, DirectFetchError):
        return FailedSource(**base, reason=FailureReason.timeout if exc.timeout else FailureReason.http_error,
                            detail=str(exc)[:300])
    return FailedSource(**base, reason=FailureReason.http_error, detail=f"unexpected {type(exc).__name__}")


def _location_floor(source: Source, e: Evidence, location: LocationQuery) -> LocationMatch | None:
    state_scoped = location.jurisdiction is not None and location.jurisdiction in source.jurisdictions
    if state_scoped or e.category is EvidenceCategory.helpline:
        return LocationMatch.approximate
    return None


def run_task(index: int, task: SourceTask, ctx: ExecCtx, retrieved_at: Callable[[], datetime]) -> TaskOutcome:
    parse_ctx = ParseCtx(location=ctx.location, source=task.source, product_id=task.product.id,
                         retrieved_at=retrieved_at(), mock=ctx.gateway.mock)
    if ctx.cancel_event.is_set():
        return TaskOutcome(index, task, (), None, ctx.meta, cancelled=True)
    for attempt in range(2):
        try:
            if task.source.access is AccessMethod.rss:
                raw = _exec_rss(task, ctx, parse_ctx)
            else:
                raw = EXECUTORS[task.source.access](task, ctx)
            parse_ctx = ParseCtx(location=ctx.location, source=task.source, product_id=task.product.id,
                                 retrieved_at=retrieved_at(), mock=ctx.gateway.mock,
                                 tinyfish_run_id=ctx.meta.run_ids[-1] if ctx.meta.run_ids else None)
            items = [assess(e, location=ctx.location, max_age=task.source.freshness_max_age,
                            location_floor=_location_floor(task.source, e, ctx.location))
                     for e in task.product.parse(raw, parse_ctx)]
            failure = None
            if items and all(e.freshness is Freshness.stale for e in items):
                failure = FailedSource(source_id=task.source.id, product_id=task.product.id,
                                       reason=FailureReason.stale, detail="every item is older than the freshness window")
            return TaskOutcome(index, task, tuple(items), failure, ctx.meta)
        except Exception as exc:  # noqa: BLE001 - every failure becomes a FailedSource
            if ctx.cancel_event.is_set():
                return TaskOutcome(index, task, (), None, ctx.meta, cancelled=True)
            wait = _retry_wait(exc)
            if attempt == 0 and wait is not None and wait <= ctx.settings.max_retry_wait_s:
                ctx.sleep(wait)
                continue
            log.info("web-intel source %s failed: %s", task.source.id, type(exc).__name__)
            return TaskOutcome(index, task, (), _failure(task, exc), ctx.meta)
    raise AssertionError("unreachable")


# --- composing the public run from outcomes (pure) ---

_GRADE_ORDER = {Grade.verified_official: 0, Grade.credible_secondary: 1, Grade.unverified: 2, Grade.insufficient: 3}


def merge_evidence(outcomes: list[TaskOutcome]) -> tuple[list[Evidence], list[Conflict]]:
    items = [e for o in outcomes for e in o.evidence]
    for product in {o.task.product.id: o.task.product for o in outcomes}.values():
        if product.finalize is None:
            continue
        mine = [e for e in items if e.product_id is product.id]
        rest = [e for e in items if e.product_id is not product.id]
        finalized = []
        for e in product.finalize(mine):
            graded = e.model_copy(update={"grade": grade(e)})
            finalized.append(graded.model_copy(update={"quality_score": quality_score(graded)}))
        items = rest + finalized
    items = dedupe(items)
    items.sort(key=lambda e: (_GRADE_ORDER[e.grade], -e.quality_score, e.category.value))
    return items, detect_conflicts(items)


def summarize(evidence: list[Evidence], conflicts: list[Conflict], failed: list[FailedSource]) -> str:
    counts = {g: sum(1 for e in evidence if e.grade is g) for g in Grade}
    parts = [
        f"{counts[Grade.verified_official]} verified official",
        f"{counts[Grade.credible_secondary]} credible secondary",
        f"{counts[Grade.unverified]} unverified",
        f"{counts[Grade.insufficient]} insufficient",
    ]
    text = f"{len(evidence)} evidence items ({', '.join(parts)}); {len(conflicts)} conflicts; {len(failed)} sources failed."
    return text + " For human review only."


@dataclass
class _Handle:
    run: WebIntelRun
    request: RunRequest
    tasks: list[SourceTask] = field(default_factory=list)
    skipped: list[FailedSource] = field(default_factory=list)
    task_states: dict[int, TaskState] = field(default_factory=dict)
    outcomes: list[TaskOutcome] = field(default_factory=list)
    live_view: LiveView | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock)
    ledger: CostLedger | None = None
    done: threading.Event = field(default_factory=threading.Event)


def compose(handle: _Handle, *, state: RunState, mock: bool, finished_at: datetime | None = None) -> WebIntelRun:
    outcomes = sorted(handle.outcomes, key=lambda o: o.index)
    evidence, conflicts = merge_evidence(outcomes)
    failed = list(handle.skipped) + [o.failure for o in outcomes if o.failure is not None]
    statuses = []
    for i, task in enumerate(handle.tasks):
        outcome = next((o for o in outcomes if o.index == i), None)
        if outcome is None:
            task_state = handle.task_states.get(i, TaskState.queued)
        elif outcome.cancelled:
            task_state = TaskState.cancelled
        else:
            task_state = TaskState.failed if outcome.failure and not outcome.evidence else TaskState.succeeded
        run_ids = outcome.meta.run_ids if outcome else []
        statuses.append(SourceTaskStatus(
            source_id=task.source.id, product_id=task.product.id, access_method=task.source.access,
            state=task_state, evidence_count=len(outcome.evidence) if outcome else 0,
            tinyfish_run_id=run_ids[-1] if run_ids else None,
        ))
    for skip in handle.skipped:
        statuses.append(SourceTaskStatus(source_id=skip.source_id, product_id=skip.product_id,
                                         access_method=SOURCES[skip.source_id].access, state=TaskState.skipped))
    metas = [o.meta for o in outcomes]
    run_ids = [rid for m in metas for rid in m.run_ids]
    data_quality = []
    if mock:
        data_quality.append("mock_replay")
    if any(t.source.fallback_of for t in handle.tasks):
        data_quality.append("imd_fallback_fetch")
    if conflicts:
        data_quality.append("conflicts_present")
    if any(e.validation_status.value == "rejected" for e in evidence):
        data_quality.append("rejected_items_present")
    ledger = handle.ledger
    live_view = handle.live_view if state is RunState.running else None
    return handle.run.model_copy(update={
        "state": state,
        "finished_at": finished_at,
        "summary": summarize(evidence, conflicts, failed) if outcomes or failed else None,
        "evidence": evidence,
        "source_tasks": statuses,
        "sources_checked": len(handle.tasks) + len(handle.skipped),
        "sources_succeeded": sum(1 for s in statuses if s.state is TaskState.succeeded),
        "sources_failed": len(failed),
        "failed_sources": failed,
        "conflicts": conflicts,
        "data_quality": data_quality,
        "agent_metadata": AgentMetadata(
            tinyfish_run_ids=run_ids,
            run_statuses={k: v for m in metas for k, v in m.run_statuses.items()},
            result_statuses={k: v for m in metas for k, v in m.result_statuses.items()},
            num_of_steps=sum(m.steps for m in metas) if metas else None,
            estimated_cost_usd=ledger.spent_usd if ledger and not mock else (0.0 if mock else None),
            budget_usd=ledger.max_usd if ledger else None,
        ),
        "live_view": live_view,
    })


def terminal_state(handle: _Handle) -> RunState:
    if handle.cancel_event.is_set():
        return RunState.cancelled
    succeeded = sum(1 for o in handle.outcomes if not o.cancelled and (o.failure is None or o.evidence))
    failures = len(handle.skipped) + sum(1 for o in handle.outcomes if o.failure is not None)
    if succeeded == 0:
        return RunState.failed
    return RunState.partial if failures else RunState.succeeded


# --- runner ---

class IntelRunner:
    def __init__(
        self,
        settings: Settings,
        store: IntelStore,
        gateway: Gateway | None,
        *,
        today: Callable[[], date] = lambda: datetime.now(IST).date(),
        now: Callable[[], datetime] = utcnow,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.settings = settings
        self.store = store
        self.gateway = gateway
        self._today = today
        self._now = now
        self._sleep = sleep
        self._lock = threading.Lock()
        self._active: dict[str, _Handle] = {}
        self._inflight: dict[str, str] = {}
        self._run_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="intel-run")
        self._task_pool = ThreadPoolExecutor(max_workers=settings.task_workers, thread_name_prefix="intel-task")

    def today(self) -> date:
        return self._today()

    @property
    def mode(self) -> Mode:
        return self.settings.mode if self.gateway is not None or self.settings.mode is Mode.disabled else Mode.disabled

    def _webhook_url(self) -> str | None:
        if self.settings.public_base_url and self.settings.webhook_token:
            return f"{self.settings.public_base_url}/api/agent/web-intelligence/webhook?token={self.settings.webhook_token}"
        return None

    def start(self, request: RunRequest) -> WebIntelRun:
        created = self._now()
        base = WebIntelRun(run_id=f"wi_{uuid.uuid4().hex[:20]}", state=RunState.queued, mode=self.mode.value,
                           products=list(request.products), location=request.location, created_at=created)
        if self.mode is Mode.disabled:
            run = base.model_copy(update={
                "state": RunState.disabled, "finished_at": created, "data_quality": ["tinyfish_disabled"],
                "summary": "Web intelligence is disabled: set TINYFISH_API_KEY (and TINYFISH_ENABLED) to enable it.",
            })
            self.store.save_run(run)
            return run
        with self._lock:
            existing_id = self._inflight.get(request.key)
            if existing_id and existing_id in self._active:
                return self.snapshot(self._active[existing_id])
            handle = _Handle(run=base, request=request)
            self._active[base.run_id] = handle
            self._inflight[request.key] = base.run_id
        self.store.save_run(base, request.key)
        self._run_pool.submit(self._execute, handle)
        return base

    def snapshot(self, handle: _Handle) -> WebIntelRun:
        with handle.lock:
            return compose(handle, state=handle.run.state, mock=self.gateway.mock,
                           finished_at=handle.run.finished_at)

    def get(self, run_id: str) -> WebIntelRun | None:
        handle = self._active.get(run_id)
        if handle is not None:
            return self.snapshot(handle)
        return self.store.get_run(run_id)

    def cancel(self, run_id: str) -> WebIntelRun | None:
        handle = self._active.get(run_id)
        if handle is None:
            return self.store.get_run(run_id)
        handle.cancel_event.set()
        return self.snapshot(handle)

    def wait(self, run_id: str, timeout: float = 30.0) -> WebIntelRun | None:
        handle = self._active.get(run_id)
        if handle is not None:
            handle.done.wait(timeout)
        return self.get(run_id)

    def _set_live_view(self, handle: _Handle, url: str, tinyfish_run_id: str | None) -> None:
        with handle.lock:
            handle.live_view = LiveView(streaming_url=url, expires_at=self._now() + LIVE_VIEW_TTL,
                                        tinyfish_run_id=tinyfish_run_id)

    def _save(self, handle: _Handle) -> None:
        self.store.save_run(self.snapshot(handle), handle.request.key)

    def _run_one(self, handle: _Handle, index: int, task: SourceTask, ctx: ExecCtx) -> TaskOutcome:
        with handle.lock:
            handle.task_states[index] = TaskState.running
        return run_task(index, task, ctx, self._now)

    def _execute(self, handle: _Handle) -> None:
        request = handle.request
        try:
            tasks, skipped = plan(request.products, request.location, self.settings, self.today(), request.stream)
            with handle.lock:
                handle.tasks, handle.skipped = tasks, skipped
                handle.ledger = CostLedger(self.settings.max_usd_per_request, self.settings.usd_per_step)
                handle.run = handle.run.model_copy(update={"state": RunState.running, "started_at": self._now()})
            self._save(handle)
            inputs = GoalInputs.from_location(request.location, self.today())
            futures = []
            for index, task in enumerate(tasks):
                ctx = ExecCtx(
                    gateway=self.gateway, settings=self.settings, location=request.location, inputs=inputs,
                    ledger=handle.ledger, cancel_event=handle.cancel_event,
                    on_streaming_url=lambda url, rid, h=handle: self._set_live_view(h, url, rid),
                    sleep=self._sleep, meta=TaskMeta(), webhook_url=self._webhook_url(),
                )
                futures.append(self._task_pool.submit(self._run_one, handle, index, task, ctx))
            for future in as_completed(futures):
                outcome = future.result()
                with handle.lock:
                    handle.outcomes.append(outcome)
                self._save(handle)
            with handle.lock:
                handle.run = handle.run.model_copy(update={"state": terminal_state(handle), "finished_at": self._now()})
                handle.live_view = None
        except Exception as exc:  # noqa: BLE001 - a run must always reach a terminal state
            log.exception("web-intel run %s crashed", handle.run.run_id)
            handle.cancel_event.set()
            with handle.lock:
                handle.run = handle.run.model_copy(update={
                    "state": RunState.failed, "finished_at": self._now(),
                    "error": f"internal error: {type(exc).__name__}",
                })
                handle.live_view = None
        finally:
            try:
                self._save_final(handle)
            finally:
                with self._lock:
                    self._active.pop(handle.run.run_id, None)
                    if self._inflight.get(request.key) == handle.run.run_id:
                        del self._inflight[request.key]
                handle.done.set()

    def _save_final(self, handle: _Handle) -> None:
        try:
            run = self.snapshot(handle)
        except Exception:  # noqa: BLE001 - compose failed; store what is known without it
            log.exception("web-intel run %s could not be composed", handle.run.run_id)
            with handle.lock:
                handle.run = handle.run.model_copy(update={
                    "state": RunState.failed, "finished_at": handle.run.finished_at or self._now(),
                    "error": handle.run.error or "internal error: could not compose the run",
                })
                run = handle.run
        try:
            self.store.save_run(run, handle.request.key)
        except Exception:  # noqa: BLE001 - the run must still be released below
            log.exception("web-intel run %s could not be saved", run.run_id)

    def shutdown(self) -> None:
        self._run_pool.shutdown(wait=False, cancel_futures=True)
        self._task_pool.shutdown(wait=False, cancel_futures=True)

