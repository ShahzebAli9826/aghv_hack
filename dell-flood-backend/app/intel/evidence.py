"""Public contract for Aegis web intelligence (schema_version 1.1).

These models are what the API returns and what the store persists. Everything
here is data; nothing in this module talks to the network.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.1"
QUALITY_SCORE_NOTE = (
    "Evidence quality score = 0.40*authority + 0.25*recency + 0.20*location_match "
    "+ 0.15*validation, each in [0,1]. It rates how trustworthy a source item is. "
    "It is not a flood probability."
)
DISCLAIMER = (
    "Official-source evidence informs a human decision. It is not a sensor "
    "measurement and cannot trigger alerts."
)


class ProductId(StrEnum):
    river_levels = "river_levels"
    imd_warnings = "imd_warnings"
    official_alerts = "official_alerts"
    state_bulletin = "state_bulletin"
    mobility = "mobility"
    relief_camps = "relief_camps"
    district_brief = "district_brief"
    news_corroboration = "news_corroboration"
    helplines = "helplines"
    health_power = "health_power"


class EvidenceCategory(StrEnum):
    official_warning = "official_warning"
    river_level = "river_level"
    rainfall = "rainfall"
    official_alert = "official_alert"
    bulletin = "bulletin"
    barrage_gate = "barrage_gate"
    embankment = "embankment"
    rail_disruption = "rail_disruption"
    road_closure = "road_closure"
    relief_camp = "relief_camp"
    news_report = "news_report"
    helpline = "helpline"
    hospital_capacity = "hospital_capacity"
    power_outage = "power_outage"
    situation_brief = "situation_brief"
    other = "other"


class RunState(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    partial = "partial"
    failed = "failed"
    disabled = "disabled"
    cancelled = "cancelled"


TERMINAL_STATES = frozenset(
    {RunState.succeeded, RunState.partial, RunState.failed, RunState.disabled, RunState.cancelled}
)


class AccessMethod(StrEnum):
    api = "api"
    rss = "rss"
    fetch = "fetch"
    agent = "agent"
    search = "search"
    research = "research"


class SourceType(StrEnum):
    official = "official"
    secondary = "secondary"
    unknown = "unknown"


class LocationMatch(StrEnum):
    verified = "verified"
    approximate = "approximate"
    uncertain = "uncertain"


class Freshness(StrEnum):
    fresh = "fresh"
    stale = "stale"
    unknown = "unknown"


class ValidationStatus(StrEnum):
    verified = "verified"
    partial = "partial"
    rejected = "rejected"


class Grade(StrEnum):
    verified_official = "verified_official"
    credible_secondary = "credible_secondary"
    unverified = "unverified"
    insufficient = "insufficient"


class Signal(StrEnum):
    """Direction an item points in, used only to surface disagreements to a human."""

    elevated = "elevated"
    normal = "normal"
    unknown = "unknown"


class FailureReason(StrEnum):
    login_wall = "login_wall"
    anti_bot = "anti_bot"
    timeout = "timeout"
    goal_failure = "goal_failure"
    schema_invalid = "schema_invalid"
    stale = "stale"
    out_of_season = "out_of_season"
    http_error = "http_error"
    billing = "billing"
    disabled = "disabled"
    budget_exceeded = "budget_exceeded"
    unverified_source = "unverified_source"
    interrupted = "interrupted"


class TaskState(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    skipped = "skipped"
    cancelled = "cancelled"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class Measurement(_Model):
    station: str | None = Field(default=None, max_length=120)
    river: str | None = Field(default=None, max_length=120)
    value: float
    unit: Literal["m", "mm", "m3/s"]
    danger_level: float | None = None
    warning_level: float | None = None
    hfl: float | None = None
    trend: Literal["rising", "falling", "steady"] | None = None


class Evidence(_Model):
    evidence_id: str = Field(max_length=64)
    claim: str = Field(max_length=500)
    category: EvidenceCategory
    product_id: ProductId
    source_id: str = Field(max_length=64)
    source_name: str = Field(max_length=160)
    source_type: SourceType
    source_url: str = Field(max_length=2048)
    retrieved_at: datetime
    published_at: datetime | None = None
    observed_at: datetime | None = None
    district: str | None = Field(default=None, max_length=120)
    location_match: LocationMatch = LocationMatch.uncertain
    freshness: Freshness = Freshness.unknown
    validation_status: ValidationStatus = ValidationStatus.partial
    grade: Grade = Grade.unverified
    signal: Signal = Signal.unknown
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    measurement: Measurement | None = None
    access_method: AccessMethod
    tinyfish_run_id: str | None = Field(default=None, max_length=128)
    excerpt: str | None = Field(default=None, max_length=700)
    notes: list[str] = Field(default_factory=list, max_length=12)
    mock: bool = False


class FailedSource(_Model):
    source_id: str = Field(max_length=64)
    product_id: ProductId | None = None
    reason: FailureReason
    detail: str | None = Field(default=None, max_length=300)
    retry_after_s: float | None = None
    tinyfish_run_id: str | None = Field(default=None, max_length=128)


class Conflict(_Model):
    kind: Literal["value_disagreement", "official_vs_secondary"]
    key: str = Field(max_length=200)
    evidence_ids: list[str] = Field(max_length=20)
    detail: str = Field(max_length=400)


class LiveView(_Model):
    streaming_url: str = Field(max_length=2048)
    expires_at: datetime
    tinyfish_run_id: str | None = Field(default=None, max_length=128)


class LocationQuery(_Model):
    query: str = Field(min_length=1, max_length=120)
    resolved_name: str | None = Field(default=None, max_length=160)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    jurisdiction: str | None = Field(default=None, max_length=8)
    state: str | None = Field(default=None, max_length=60)
    district: str | None = Field(default=None, max_length=80)


class SourceTaskStatus(_Model):
    source_id: str = Field(max_length=64)
    product_id: ProductId
    access_method: AccessMethod
    state: TaskState
    evidence_count: int = 0
    tinyfish_run_id: str | None = Field(default=None, max_length=128)


class AgentMetadata(_Model):
    provider: Literal["TinyFish"] = "TinyFish"
    tinyfish_run_ids: list[str] = Field(default_factory=list, max_length=100)
    run_statuses: dict[str, str] = Field(default_factory=dict)
    result_statuses: dict[str, str] = Field(default_factory=dict)
    num_of_steps: int | None = None
    estimated_cost_usd: float | None = None
    budget_usd: float | None = None


class WebIntelRun(_Model):
    schema_version: Literal["1.1"] = SCHEMA_VERSION
    run_id: str = Field(max_length=64)
    state: RunState
    mode: Literal["live", "replay", "disabled"]
    products: list[ProductId] = Field(max_length=len(ProductId))
    location: LocationQuery
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    summary: str | None = Field(default=None, max_length=1200)
    evidence: list[Evidence] = Field(default_factory=list, max_length=500)
    source_tasks: list[SourceTaskStatus] = Field(default_factory=list, max_length=100)
    sources_checked: int = 0
    sources_succeeded: int = 0
    sources_failed: int = 0
    failed_sources: list[FailedSource] = Field(default_factory=list, max_length=100)
    conflicts: list[Conflict] = Field(default_factory=list, max_length=100)
    data_quality: list[str] = Field(default_factory=list, max_length=30)
    human_review_required: Literal[True] = True
    quality_score_note: str = QUALITY_SCORE_NOTE
    disclaimer: str = DISCLAIMER
    agent_metadata: AgentMetadata = Field(default_factory=AgentMetadata)
    live_view: LiveView | None = None
    error: str | None = Field(default=None, max_length=300)
