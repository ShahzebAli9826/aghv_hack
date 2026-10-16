"""Transport adapter for the TinyFish REST API (verified 2026-10-16, see TINYFISH_CONTRACT.md).

Each endpoint's response is parsed in exactly one `_normalize_*` function. The API
key is only ever placed in the `X-API-Key` request header; it is never logged,
raised, or returned.
"""
from __future__ import annotations

import json
import logging
import math
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.intel.config import Settings
from app.intel.evidence import FailureReason

log = logging.getLogger("aegis.intel.tinyfish")

TERMINAL_RUN_STATUSES = frozenset({"COMPLETED", "FAILED", "CANCELLED"})
TERMINAL_RESEARCH_STATUSES = frozenset({"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"})


# --- errors ---

class TinyFishError(Exception):
    reason: FailureReason = FailureReason.http_error

    def __init__(self, message: str, *, status_code: int | None = None, code: str | None = None,
                 retry_after_s: float | None = None, retryable: bool = False, run_id: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.retry_after_s = retry_after_s
        self.retryable = retryable
        self.run_id = run_id


class TinyFishAuthError(TinyFishError):
    pass


class TinyFishBillingError(TinyFishError):
    reason = FailureReason.billing


class TinyFishRateLimited(TinyFishError):
    pass


class TinyFishServerError(TinyFishError):
    pass


class TinyFishInputError(TinyFishError):
    pass


class TinyFishNotFound(TinyFishError):
    pass


class TinyFishTimeout(TinyFishError):
    reason = FailureReason.timeout


class TinyFishCancelled(TinyFishError):
    reason = FailureReason.interrupted


class BudgetExceeded(TinyFishError):
    reason = FailureReason.budget_exceeded


class TinyFishDisabled(TinyFishError):
    reason = FailureReason.disabled


# --- typed results ---

@dataclass(frozen=True)
class AgentRun:
    run_id: str
    status: str
    result: Any = None
    error: dict | None = None
    num_of_steps: int | None = None
    started_at: str | None = None
    finished_at: str | None = None
    streaming_url: str | None = field(default=None, repr=False)
    profile_hint_reason: str | None = None

    @property
    def terminal(self) -> bool:
        return self.status in TERMINAL_RUN_STATUSES


@dataclass(frozen=True)
class SseEvent:
    type: str
    run_id: str | None
    data: dict


@dataclass(frozen=True)
class SearchHit:
    url: str
    title: str
    snippet: str
    site_name: str
    date: str | None
    position: int


@dataclass(frozen=True)
class FetchedPage:
    url: str
    final_url: str | None
    title: str | None
    text: str
    published_date: str | None
    language: str | None


@dataclass(frozen=True)
class FetchResult:
    pages: tuple[FetchedPage, ...]
    errors: tuple[tuple[str, str, int | None], ...]


@dataclass(frozen=True)
class ResearchRun:
    research_run_id: str
    status: str
    answer: str | None
    report: str | None
    citations: tuple[str, ...]
    error: dict | None

    @property
    def terminal(self) -> bool:
        return self.status in TERMINAL_RESEARCH_STATUSES


@dataclass(frozen=True)
class Monitor:
    id: str
    type: str
    name: str | None
    status: str | None
    config: dict
    schedule_cron: str | None


# --- normalization (one per endpoint) ---

def _normalize_run(body: dict) -> AgentRun:
    """GET /v1/runs/{id}; also the `data` of a run webhook and the sync /run response."""
    error = body.get("error") if isinstance(body.get("error"), dict) else None
    hint = body.get("profile_hint") or (error or {}).get("profile_hint")
    steps = body.get("num_of_steps")
    return AgentRun(
        run_id=str(body.get("run_id") or ""),
        status=str(body.get("status") or "").upper(),
        result=body.get("result"),
        error=error,
        num_of_steps=int(steps) if isinstance(steps, (int, float)) else None,
        started_at=body.get("started_at"),
        finished_at=body.get("finished_at"),
        streaming_url=body.get("streaming_url"),
        profile_hint_reason=hint.get("reason") if isinstance(hint, dict) else None,
    )


def _normalize_sse_line_block(lines: list[str]) -> SseEvent | None:
    # unverified: SSE framing. The OpenAPI schema documents each event as a JSON
    # object with `type`; we assume standard `data: <json>` lines separated by a
    # blank line, as in the TinyFish cookbook. Check against a live run-sse stream.
    payload = "\n".join(line[5:].lstrip() for line in lines if line.startswith("data:"))
    if not payload:
        return None
    try:
        body = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(body, dict) or not body.get("type"):
        return None
    return SseEvent(type=str(body["type"]).upper(), run_id=body.get("run_id"), data=body)


def _normalize_search(body: dict) -> list[SearchHit]:
    hits = []
    for raw in body.get("results") or []:
        if not isinstance(raw, dict) or not raw.get("url"):
            continue
        hits.append(SearchHit(
            url=str(raw["url"]), title=str(raw.get("title") or ""), snippet=str(raw.get("snippet") or ""),
            site_name=str(raw.get("site_name") or ""), date=raw.get("date"), position=int(raw.get("position") or 0),
        ))
    return hits


def _normalize_fetch(body: dict) -> FetchResult:
    pages = []
    for raw in body.get("results") or []:
        if not isinstance(raw, dict) or not raw.get("url"):
            continue
        text = raw.get("text")
        if not isinstance(text, str):
            text = json.dumps(text) if text is not None else ""
        pages.append(FetchedPage(
            url=str(raw["url"]), final_url=raw.get("final_url"), title=raw.get("title"), text=text,
            published_date=raw.get("published_date"), language=raw.get("language"),
        ))
    errors = tuple(
        (str(e.get("url") or ""), str(e.get("error") or ""), e.get("status"))
        for e in body.get("errors") or [] if isinstance(e, dict)
    )
    return FetchResult(pages=tuple(pages), errors=errors)


def _normalize_research(body: dict) -> ResearchRun:
    quick = body.get("quick_result") or {}
    deep = body.get("deep_result") or {}
    citations = list(deep.get("citations") or []) + list(quick.get("citations") or [])
    unique = tuple(dict.fromkeys(str(c) for c in citations if isinstance(c, str)))
    error = body.get("error") if isinstance(body.get("error"), dict) else None
    return ResearchRun(
        research_run_id=str(body.get("research_run_id") or ""),
        status=str(body.get("status") or "").upper(),
        answer=quick.get("answer"),
        report=deep.get("result"),
        citations=unique,
        error=error,
    )


def _normalize_monitor(body: dict) -> Monitor:
    # unverified: GET /v1/monitors/{id} body is not shown in the docs; we assume it
    # is the same `monitor` object returned by create (and listed under `monitors`).
    raw = body.get("monitor") if isinstance(body.get("monitor"), dict) else body
    return Monitor(
        id=str(raw.get("id") or ""), type=str(raw.get("type") or ""), name=raw.get("name"),
        status=raw.get("status"), config=raw.get("config") or {}, schedule_cron=raw.get("schedule_cron"),
    )


# --- cost ---

class CostLedger:
    """Per-request budget. Steps are reserved before a run starts, so concurrent
    runs can never overspend; the reservation is settled with the real step count."""

    def __init__(self, max_usd: float, usd_per_step: float):
        self.max_usd = max_usd
        self.usd_per_step = usd_per_step
        self._lock = threading.Lock()
        self._spent_steps = 0
        self._reserved_steps = 0
        self._unknown_steps = False

    def reserve(self, wanted_steps: int) -> int:
        with self._lock:
            if self.usd_per_step <= 0:
                steps = wanted_steps
            else:
                committed = (self._spent_steps + self._reserved_steps) * self.usd_per_step
                steps = min(wanted_steps, math.floor((self.max_usd - committed) / self.usd_per_step + 1e-9))
            if steps < 1:
                raise BudgetExceeded(f"budget of ${self.max_usd:.2f} for this request is exhausted")
            self._reserved_steps += steps
            return steps

    def settle(self, reserved: int, actual: int | None) -> None:
        with self._lock:
            self._reserved_steps -= reserved
            if actual is None:
                self._unknown_steps = True
            self._spent_steps += reserved if actual is None else min(actual, reserved)

    @property
    def steps(self) -> int:
        return self._spent_steps

    @property
    def spent_usd(self) -> float:
        return round(self._spent_steps * self.usd_per_step, 4)


# --- client ---

class TinyFishClient:
    def __init__(
        self,
        settings: Settings,
        http: httpx.Client | None = None,
        *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        if not settings.api_key:
            raise TinyFishDisabled("TinyFish API key is not configured")
        self._settings = settings
        self._key = settings.api_key
        self._http = http or httpx.Client(timeout=settings.http_timeout_s, follow_redirects=False)
        self._sleep = sleep
        self._clock = clock
        self._agent_slots = threading.BoundedSemaphore(settings.max_concurrent_agent_runs)

    def __repr__(self) -> str:
        return f"TinyFishClient(agent_base_url={self._settings.agent_base_url!r})"

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self._key, "Accept": "application/json"}

    def _request(self, method: str, url: str, *, json_body: Any = None, params: dict | None = None) -> dict:
        log.debug("tinyfish %s %s", method, httpx.URL(url).path)
        try:
            response = self._http.request(method, url, json=json_body, params=params, headers=self._headers())
        except httpx.TimeoutException as exc:
            raise TinyFishTimeout(f"{method} {httpx.URL(url).path} timed out", retryable=True) from None
        except httpx.TransportError as exc:
            raise TinyFishServerError(f"transport error: {type(exc).__name__}", retryable=True) from None
        if response.status_code >= 400:
            raise _http_error(response)
        try:
            body = response.json()
        except ValueError:
            raise TinyFishServerError("non-JSON response", status_code=response.status_code) from None
        return body if isinstance(body, dict) else {"_list": body}

    # Agent

    def _agent_body(self, url: str, goal: str, output_schema: dict | None, webhook_url: str | None,
                    max_steps: int | None) -> dict:
        body: dict[str, Any] = {"url": url, "goal": goal}
        if output_schema:
            body["output_schema"] = output_schema
        if webhook_url:
            body["webhook_url"] = webhook_url
        if max_steps:
            body["agent_config"] = {"max_steps": max_steps}
        return body

    def start_agent_run(self, url: str, goal: str, output_schema: dict | None = None, *,
                        webhook_url: str | None = None, max_steps: int | None = None) -> str:
        body = self._request("POST", f"{self._settings.agent_base_url}/v1/automation/run-async",
                             json_body=self._agent_body(url, goal, output_schema, webhook_url, max_steps))
        error = body.get("error")
        if not body.get("run_id"):
            message = error.get("message") if isinstance(error, dict) else "run-async returned no run_id"
            raise TinyFishInputError(str(message)[:200], code=(error or {}).get("code") if isinstance(error, dict) else None)
        return str(body["run_id"])

    def get_run(self, run_id: str) -> AgentRun:
        body = self._request("GET", f"{self._settings.agent_base_url}/v1/runs/{run_id}",
                             params={"screenshots": "none", "html": "none"})
        return _normalize_run(body)

    def cancel_run(self, run_id: str) -> str:
        body = self._request("POST", f"{self._settings.agent_base_url}/v1/runs/{run_id}/cancel")
        return str(body.get("status") or "")

    def stream_agent_run(self, url: str, goal: str, output_schema: dict | None = None, *,
                         webhook_url: str | None = None, max_steps: int | None = None) -> Iterator[SseEvent]:
        endpoint = f"{self._settings.agent_base_url}/v1/automation/run-sse"
        headers = {**self._headers(), "Accept": "text/event-stream"}
        body = self._agent_body(url, goal, output_schema, webhook_url, max_steps)
        try:
            with self._http.stream("POST", endpoint, json=body, headers=headers) as response:
                if response.status_code >= 400:
                    response.read()
                    raise _http_error(response)
                block: list[str] = []
                for line in response.iter_lines():
                    if line.strip():
                        block.append(line)
                        continue
                    event = _normalize_sse_line_block(block)
                    block = []
                    if event:
                        yield event
                event = _normalize_sse_line_block(block)
                if event:
                    yield event
        except httpx.TimeoutException:
            raise TinyFishTimeout("run-sse stream timed out", retryable=True) from None
        except httpx.TransportError as exc:
            raise TinyFishServerError(f"transport error: {type(exc).__name__}", retryable=True) from None

    def run_agent(
        self,
        url: str,
        goal: str,
        output_schema: dict | None,
        *,
        ledger: CostLedger,
        stream: bool = False,
        on_streaming_url: Callable[[str, str | None], None] | None = None,
        on_started: Callable[[str], None] | None = None,
        webhook_url: str | None = None,
        cancel_event: threading.Event | None = None,
    ) -> AgentRun:
        """Run one agent task to a terminal state while holding one concurrency slot."""
        with self._agent_slots:
            if cancel_event is not None and cancel_event.is_set():
                raise TinyFishCancelled("cancelled before start")
            steps = ledger.reserve(self._settings.max_steps_per_run)
            run: AgentRun | None = None
            run_id: str | None = None
            try:
                if stream:
                    for event in self.stream_agent_run(url, goal, output_schema,
                                                       webhook_url=webhook_url, max_steps=steps):
                        if event.run_id and not run_id:
                            run_id = event.run_id
                            if on_started:
                                on_started(run_id)
                        if event.type == "STREAMING_URL" and on_streaming_url and event.data.get("streaming_url"):
                            on_streaming_url(str(event.data["streaming_url"]), run_id)
                        if event.type == "COMPLETE":
                            break
                        if cancel_event is not None and cancel_event.is_set() and run_id:
                            self.cancel_run(run_id)
                            raise TinyFishCancelled("cancelled", run_id=run_id)
                    if not run_id:
                        raise TinyFishServerError("run-sse stream ended without a run_id")
                else:
                    run_id = self.start_agent_run(url, goal, output_schema, webhook_url=webhook_url, max_steps=steps)
                    if on_started:
                        on_started(run_id)
                run = self._poll(run_id, cancel_event)
                return run
            finally:
                ledger.settle(steps, run.num_of_steps if run is not None else None)

    def _poll(self, run_id: str, cancel_event: threading.Event | None) -> AgentRun:
        deadline = self._clock() + self._settings.run_timeout_s
        while True:
            run = self.get_run(run_id)
            if run.terminal:
                return run
            if cancel_event is not None and cancel_event.is_set():
                self.cancel_run(run_id)
                raise TinyFishCancelled("cancelled", run_id=run_id)
            if self._clock() >= deadline:
                self.cancel_run(run_id)
                raise TinyFishTimeout(f"run exceeded {self._settings.run_timeout_s:.0f}s", run_id=run_id)
            self._sleep(self._settings.poll_interval_s)

    # Search / Fetch (free within rate limits)

    def search(self, query: str, *, include_domains: tuple[str, ...] = (), domain_type: str | None = None,
               recency_minutes: int | None = None) -> list[SearchHit]:
        params: dict[str, Any] = {"query": query[:2000]}
        if include_domains:
            # unverified: the OpenAPI types include_domains as a plain string; we send
            # a comma-separated list. Confirm the separator against a live call.
            params["include_domains"] = ",".join(include_domains)
        if domain_type:
            params["domain_type"] = domain_type
        if recency_minutes:
            params["recency_minutes"] = recency_minutes
        return _normalize_search(self._request("GET", f"{self._settings.search_base_url}/", params=params))

    def fetch(self, urls: list[str], *, fmt: str = "markdown", purpose: str | None = None) -> FetchResult:
        body: dict[str, Any] = {"urls": urls, "format": fmt}
        if purpose:
            body["purpose"] = purpose[:2000]
        return _normalize_fetch(self._request("POST", f"{self._settings.fetch_base_url}/", json_body=body))

    # Research (beta)

    def start_research(self, query: str, *, domains: tuple[str, ...], recency_minutes: int | None = None) -> str:
        body: dict[str, Any] = {"query": query[:2000], "domain_filter": {"mode": "include", "domains": list(domains)}}
        if recency_minutes:
            body["recency_minutes"] = recency_minutes
        reply = self._request("POST", f"{self._settings.agent_base_url}/v1/automation/run-research-async",
                              json_body=body)
        if not reply.get("research_run_id"):
            error = reply.get("error") if isinstance(reply.get("error"), dict) else {}
            raise TinyFishInputError(str(error.get("message") or "no research_run_id")[:200], code=error.get("code"))
        return str(reply["research_run_id"])

    def get_research(self, research_run_id: str) -> ResearchRun:
        return _normalize_research(
            self._request("GET", f"{self._settings.agent_base_url}/v1/research-run/{research_run_id}"))

    def run_research(self, query: str, *, domains: tuple[str, ...], recency_minutes: int | None = None,
                     cancel_event: threading.Event | None = None) -> ResearchRun:
        research_id = self.start_research(query, domains=domains, recency_minutes=recency_minutes)
        deadline = self._clock() + self._settings.run_timeout_s
        while True:
            run = self.get_research(research_id)
            if run.terminal:
                return run
            if (cancel_event is not None and cancel_event.is_set()) or self._clock() >= deadline:
                self._request("POST", f"{self._settings.agent_base_url}/v1/research-run/{research_id}/cancel")
                if cancel_event is not None and cancel_event.is_set():
                    raise TinyFishCancelled("cancelled", run_id=research_id)
                raise TinyFishTimeout("research run timed out", run_id=research_id)
            self._sleep(self._settings.poll_interval_s)

    # Monitor

    def create_monitor(self, *, type_: str, config: dict, schedule_cron: str, name: str | None = None,
                       purpose: str | None = None, webhook_url: str | None = None) -> Monitor:
        body: dict[str, Any] = {"type": type_, "config": config, "schedule_cron": schedule_cron}
        if name:
            body["name"] = name[:100]
        if purpose:
            body["purpose"] = purpose[:2000]
        if webhook_url:
            body["webhook_url"] = webhook_url
        return _normalize_monitor(self._request("POST", f"{self._settings.agent_base_url}/v1/monitors",
                                                json_body=body))

    def list_monitors(self) -> list[Monitor]:
        body = self._request("GET", f"{self._settings.agent_base_url}/v1/monitors")
        return [_normalize_monitor(m) for m in body.get("monitors") or [] if isinstance(m, dict)]

    def get_monitor(self, monitor_id: str) -> Monitor:
        return _normalize_monitor(self._request("GET", f"{self._settings.agent_base_url}/v1/monitors/{monitor_id}"))

    def delete_monitor(self, monitor_id: str) -> bool:
        body = self._request("DELETE", f"{self._settings.agent_base_url}/v1/monitors/{monitor_id}")
        return bool(body.get("deleted"))

    def trigger_monitor(self, monitor_id: str) -> dict:
        body = self._request("POST", f"{self._settings.agent_base_url}/v1/monitors/{monitor_id}/runs")
        return body.get("run") if isinstance(body.get("run"), dict) else {}


def _retry_after_header(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def _http_error(response: httpx.Response) -> TinyFishError:
    try:
        body = response.json()
    except ValueError:
        body = {}
    error = body.get("error") if isinstance(body, dict) and isinstance(body.get("error"), dict) else {}
    code = error.get("code")
    message = f"HTTP {response.status_code}" + (f" {code}" if code else "")
    status = response.status_code
    retry_after = _retry_after_header(response)
    kw = {"status_code": status, "code": code, "retry_after_s": retry_after}
    if status in (401, 403):
        return TinyFishAuthError(message, **kw)
    if status == 402:
        return TinyFishBillingError(message, **kw)
    if status == 404:
        return TinyFishNotFound(message, **kw)
    if status == 409:
        return TinyFishServerError(message, retryable=True, **kw)
    if status == 429:
        return TinyFishRateLimited(message, retryable=code != "DAILY_LIMIT_EXCEEDED", **kw)
    if status >= 500:
        return TinyFishServerError(message, retryable=True, **kw)
    return TinyFishInputError(message, **kw)
