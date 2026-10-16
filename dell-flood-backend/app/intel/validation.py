"""Pure validation, grading and conflict logic for web evidence.

Nothing here performs I/O. Strings that came from web pages are treated as data:
they are cleaned, escaped and length-bounded, and never fed back into goals.
"""
from __future__ import annotations

import hashlib
import html
import math
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from app.intel.evidence import (
    Conflict,
    Evidence,
    EvidenceCategory,
    FailureReason,
    Freshness,
    Grade,
    LocationMatch,
    LocationQuery,
    Measurement,
    Signal,
    SourceType,
    ValidationStatus,
)

IST = timezone(timedelta(hours=5, minutes=30))
FUTURE_SKEW = timedelta(minutes=10)
MAX_ABOVE_HFL_M = 2.0
MAX_ABOVE_DANGER_WITHOUT_HFL_M = 8.0
MAX_BELOW_DANGER_M = 40.0
MAX_DAILY_RAIN_MM = 1500.0
LEVEL_DISAGREEMENT_M = 0.10

_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f​-‏ -‮⁦-⁩]")
_SPACE = re.compile(r"\s+")


def clean_text(value: Any, max_len: int) -> str | None:
    """Turn untrusted page text into a bounded, escaped, single-line string."""
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", str(value))
    text = _CONTROL.sub(" ", text)
    text = _SPACE.sub(" ", text).strip()
    if not text:
        return None
    if len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "…"
    escaped = html.escape(text, quote=True)
    while len(escaped) > max_len:
        text = text[: len(text) - (len(escaped) - max_len) - 1].rstrip() + "…"
        escaped = html.escape(text, quote=True)
    return escaped


def normalize_key(text: str | None) -> str:
    text = html.unescape(text or "").lower()
    text = re.sub(r"[^\w\s.]", " ", text)
    return _SPACE.sub(" ", text).strip()


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("", (parts.hostname or "").lower(), path, parts.query, ""))


def evidence_id(url: str, claim: str) -> str:
    digest = hashlib.sha256(f"{canonical_url(url)}|{normalize_key(claim)}".encode("utf-8"))
    return digest.hexdigest()[:16]


_TS_FORMATS = (
    "%d-%m-%Y %H:%M", "%d/%m/%Y %H:%M", "%d.%m.%Y %H:%M", "%Y-%m-%d %H:%M",
    "%d-%m-%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S",
    "%d %b %Y %H:%M", "%d %B %Y %H:%M", "%d-%b-%Y %H:%M",
    "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%d-%b-%Y",
)


def parse_timestamp(raw: Any) -> datetime | None:
    """Parse a displayed timestamp. Naive values are taken as IST. Unparseable -> None."""
    if raw is None:
        return None
    text = _SPACE.sub(" ", str(raw)).strip()
    text = re.sub(r"\s*(hrs?|IST)\.?$", "", text, flags=re.IGNORECASE).strip()
    if not text:
        return None
    parsed: datetime | None = None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    if parsed is None:
        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError, IndexError):
            parsed = None
    if parsed is None:
        for fmt in _TS_FORMATS:
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=IST)
    return parsed.astimezone(timezone.utc)


# --- output_schema subset validator (type, properties, required, items, enum) ---

_JSON_TYPES = {
    "object": dict, "array": list, "string": str, "boolean": bool, "null": type(None),
}


def schema_errors(value: Any, schema: dict, path: str = "$") -> list[str]:
    errors: list[str] = []
    expected = schema.get("type")
    if expected == "number":
        ok = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    elif expected == "integer":
        ok = isinstance(value, int) and not isinstance(value, bool)
    elif expected in _JSON_TYPES:
        ok = isinstance(value, _JSON_TYPES[expected]) and not (expected != "boolean" and isinstance(value, bool))
    else:
        ok = True
    if not ok:
        return [f"{path}: expected {expected}"]
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: not in enum")
    if isinstance(value, dict):
        for name in schema.get("required", []):
            if value.get(name) is None:
                errors.append(f"{path}.{name}: required")
        for name, sub in schema.get("properties", {}).items():
            if value.get(name) is not None:
                errors.extend(schema_errors(value[name], sub, f"{path}.{name}"))
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            errors.extend(schema_errors(item, schema["items"], f"{path}[{i}]"))
    return errors


def envelope(schema: dict | None) -> dict | None:
    """The run-level part of a schema: per-item rules are checked per item by the parser."""
    if not schema:
        return schema
    out = {k: v for k, v in schema.items() if k != "items"}
    if "properties" in schema:
        out["properties"] = {name: envelope(sub) for name, sub in schema["properties"].items()}
    return out


# --- two-layer run validation ---

@dataclass(frozen=True)
class RunVerdict:
    ok: bool
    result: dict | None = None
    reason: FailureReason | None = None
    detail: str | None = None
    retry_after_s: float | None = None
    retryable: bool = False


_RESULT_REASONS = {
    "login_wall": FailureReason.login_wall,
    "anti_bot": FailureReason.anti_bot,
    "captcha": FailureReason.anti_bot,
    "out_of_season": FailureReason.out_of_season,
    "season_closed": FailureReason.out_of_season,
}
_PROFILE_HINTS = {"auth_wall": FailureReason.login_wall, "bot_challenge": FailureReason.anti_bot}
UNKNOWN_RETRY_DEFAULT_S = 5.0


def judge_run(
    status: str,
    result: Any,
    error: dict | None,
    output_schema: dict | None,
    profile_hint_reason: str | None = None,
) -> RunVerdict:
    """Layer 1: run status. Layer 2: result.status, then the output schema."""
    if status == "COMPLETED":
        if not isinstance(result, dict) or not result:
            return RunVerdict(False, reason=FailureReason.goal_failure, detail="empty result")
        if str(result.get("status", "")).lower() == "failure":
            raw_reason = str(result.get("reason") or result.get("error") or "")
            reason = _RESULT_REASONS.get(normalize_key(raw_reason).replace(" ", "_"), FailureReason.goal_failure)
            return RunVerdict(False, result=result, reason=reason, detail=clean_text(raw_reason, 200))
        if output_schema:
            problems = schema_errors(result, output_schema)
            if problems:
                return RunVerdict(False, result=result, reason=FailureReason.schema_invalid,
                                  detail=clean_text("; ".join(problems[:5]), 200))
        return RunVerdict(True, result=result)

    error = error or {}
    category = error.get("category")
    code = str(error.get("code") or "").upper()
    retry_after = error.get("retry_after")
    retry_after = float(retry_after) if isinstance(retry_after, (int, float)) else None
    detail = clean_text(error.get("message") or code or status, 200)

    if category == "BILLING_FAILURE":
        return RunVerdict(False, reason=FailureReason.billing, detail=detail)
    if status == "CANCELLED":
        return RunVerdict(False, reason=FailureReason.interrupted, detail=detail or "cancelled")
    if profile_hint_reason in _PROFILE_HINTS:
        return RunVerdict(False, reason=_PROFILE_HINTS[profile_hint_reason], detail=detail)
    if code == "SITE_BLOCKED":
        return RunVerdict(False, reason=FailureReason.anti_bot, detail=detail)
    reason = FailureReason.timeout if code == "TIMEOUT" else (
        FailureReason.goal_failure if category == "AGENT_FAILURE" else FailureReason.http_error
    )
    if category == "SYSTEM_FAILURE":
        return RunVerdict(False, reason=reason, detail=detail, retry_after_s=retry_after,
                          retryable=retry_after is not None)
    if category == "UNKNOWN" or category is None:
        return RunVerdict(False, reason=reason, detail=detail,
                          retry_after_s=retry_after if retry_after is not None else UNKNOWN_RETRY_DEFAULT_S,
                          retryable=True)
    return RunVerdict(False, reason=reason, detail=detail)


# --- per-item checks ---

def assess_freshness(
    published_at: datetime | None, observed_at: datetime | None, retrieved_at: datetime, max_age: timedelta
) -> tuple[Freshness, bool]:
    """Return (freshness, is_future). Null timestamps stay unknown, never 'fresh'."""
    reference = observed_at or published_at
    if reference is None:
        return Freshness.unknown, False
    if reference > retrieved_at + FUTURE_SKEW:
        return Freshness.unknown, True
    return (Freshness.stale if retrieved_at - reference > max_age else Freshness.fresh), False


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def assess_location(
    location: LocationQuery,
    item_district: str | None,
    item_text: str | None,
    coords: tuple[float, float] | None = None,
) -> LocationMatch:
    district = normalize_key(location.district)
    state = normalize_key(location.state)
    found_district = normalize_key(item_district)
    text = normalize_key(item_text)
    if district and found_district and found_district == district:
        return LocationMatch.verified
    if coords is not None:
        distance = haversine_km(location.latitude, location.longitude, coords[0], coords[1])
        if distance <= 30:
            return LocationMatch.verified
        if distance <= 100:
            return LocationMatch.approximate
    if district and (district in found_district or re.search(rf"\b{re.escape(district)}\b", text)):
        return LocationMatch.approximate
    if state and (state in found_district or re.search(rf"\b{re.escape(state)}\b", text)):
        return LocationMatch.approximate
    return LocationMatch.uncertain


def measurement_problem(m: Measurement) -> str | None:
    if m.unit == "mm":
        return None if 0 <= m.value <= MAX_DAILY_RAIN_MM else "rainfall outside 0-1500 mm"
    if m.unit != "m":
        return None if m.value >= 0 else "negative discharge"
    if m.value <= 0:
        return "non-positive water level"
    if m.hfl is not None and m.value > m.hfl + MAX_ABOVE_HFL_M:
        return f"level {m.value} m exceeds HFL {m.hfl} m by more than {MAX_ABOVE_HFL_M} m"
    if m.danger_level is not None:
        if m.hfl is None and m.value > m.danger_level + MAX_ABOVE_DANGER_WITHOUT_HFL_M:
            return f"level {m.value} m implausibly above danger level {m.danger_level} m"
        if m.value < m.danger_level - MAX_BELOW_DANGER_M:
            return f"level {m.value} m implausibly below danger level {m.danger_level} m"
    if m.warning_level is not None and m.danger_level is not None and m.warning_level > m.danger_level:
        return "warning level above danger level"
    return None


def river_signal(m: Measurement) -> Signal:
    if m.unit != "m":
        return Signal.unknown
    threshold = m.warning_level if m.warning_level is not None else m.danger_level
    if threshold is None:
        return Signal.unknown
    return Signal.elevated if m.value >= threshold else Signal.normal


def grade(e: Evidence) -> Grade:
    if e.validation_status is ValidationStatus.rejected or e.freshness is Freshness.stale:
        return Grade.insufficient
    if e.source_type is SourceType.official:
        if e.validation_status is ValidationStatus.verified and e.location_match is not LocationMatch.uncertain:
            return Grade.verified_official
        return Grade.unverified
    if e.source_type is SourceType.secondary and e.location_match is not LocationMatch.uncertain:
        return Grade.credible_secondary
    return Grade.unverified


_AUTHORITY = {SourceType.official: 1.0, SourceType.secondary: 0.5, SourceType.unknown: 0.0}
_RECENCY = {Freshness.fresh: 1.0, Freshness.unknown: 0.4, Freshness.stale: 0.0}
_LOCATION = {LocationMatch.verified: 1.0, LocationMatch.approximate: 0.6, LocationMatch.uncertain: 0.2}
_VALIDATION = {ValidationStatus.verified: 1.0, ValidationStatus.partial: 0.5, ValidationStatus.rejected: 0.0}


def quality_score(e: Evidence) -> float:
    """See evidence.QUALITY_SCORE_NOTE. Not a flood probability."""
    score = (
        0.40 * _AUTHORITY[e.source_type] + 0.25 * _RECENCY[e.freshness]
        + 0.20 * _LOCATION[e.location_match] + 0.15 * _VALIDATION[e.validation_status]
    )
    return round(score, 3)


def assess(
    e: Evidence,
    *,
    location: LocationQuery,
    max_age: timedelta,
    coords: tuple[float, float] | None = None,
    location_floor: LocationMatch | None = None,
) -> Evidence:
    """Apply freshness, location, range checks, then grade and score one item.

    `location_floor` lifts an `uncertain` match when the source itself is scoped to
    the requested state, or the item applies everywhere (a national helpline).
    """
    notes = list(e.notes)
    status = e.validation_status
    freshness, future = assess_freshness(e.published_at, e.observed_at, e.retrieved_at, max_age)
    if future:
        status = ValidationStatus.rejected
        notes.append("rejected: timestamp is in the future")
    elif freshness is Freshness.stale:
        notes.append("stale: older than the source freshness window")
    elif freshness is Freshness.unknown:
        notes.append("no timestamp shown on source")
    signal = e.signal
    if e.measurement is not None:
        problem = measurement_problem(e.measurement)
        if problem:
            status = ValidationStatus.rejected
            notes.append(f"rejected: {problem}")
        elif e.category is EvidenceCategory.river_level:
            signal = river_signal(e.measurement)
    match = assess_location(location, e.district, f"{html.unescape(e.claim)} {html.unescape(e.excerpt or '')}", coords)
    if match is LocationMatch.uncertain and location_floor is not None:
        match = location_floor
    updated = e.model_copy(update={
        "freshness": freshness, "validation_status": status, "location_match": match,
        "signal": signal, "notes": notes[-12:],
    })
    updated = updated.model_copy(update={"grade": grade(updated)})
    return updated.model_copy(update={"quality_score": quality_score(updated)})


def _richness(e: Evidence) -> tuple:
    return (e.quality_score, e.signal is not Signal.unknown, e.excerpt is not None, len(e.notes), e.retrieved_at)


def dedupe(items: list[Evidence]) -> list[Evidence]:
    """One item per (canonical url, normalised claim); the most informative copy wins."""
    seen: dict[str, Evidence] = {}
    for item in items:
        current = seen.get(item.evidence_id)
        if current is None or _richness(item) > _richness(current):
            seen[item.evidence_id] = item
    return list(seen.values())


_FLOOD_CATEGORIES = frozenset({
    EvidenceCategory.official_warning, EvidenceCategory.river_level, EvidenceCategory.official_alert,
    EvidenceCategory.bulletin, EvidenceCategory.news_report, EvidenceCategory.situation_brief,
})


def detect_conflicts(items: list[Evidence]) -> list[Conflict]:
    usable = [e for e in items if e.validation_status is not ValidationStatus.rejected]
    conflicts: list[Conflict] = []

    by_station: dict[str, list[Evidence]] = defaultdict(list)
    for e in usable:
        if e.measurement is not None and e.measurement.unit == "m" and e.measurement.station:
            by_station[normalize_key(e.measurement.station)].append(e)
    for station, group in sorted(by_station.items()):
        values = [e.measurement.value for e in group]
        if max(values) - min(values) <= LEVEL_DISAGREEMENT_M:
            continue
        kinds = {e.source_type for e in group}
        kind = "official_vs_secondary" if {SourceType.official, SourceType.secondary} <= kinds else "value_disagreement"
        detail = "; ".join(
            f"{e.source_name}: {e.measurement.value} m" + (f" at {e.observed_at.isoformat()}" if e.observed_at else "")
            for e in group
        )
        conflicts.append(Conflict(kind=kind, key=f"river_level:{station}"[:200],
                                  evidence_ids=[e.evidence_id for e in group][:20], detail=detail[:400]))

    flood = [e for e in usable if e.category in _FLOOD_CATEGORIES and e.signal is not Signal.unknown
             and e.location_match is not LocationMatch.uncertain]
    official = [e for e in flood if e.source_type is SourceType.official]
    secondary = [e for e in flood if e.source_type is SourceType.secondary]
    official_signals = {e.signal for e in official}
    for e in secondary:
        if official_signals and e.signal not in official_signals:
            opposing = [o for o in official if o.signal is not e.signal]
            conflicts.append(Conflict(
                kind="official_vs_secondary",
                key=f"signal:{e.category}:{e.evidence_id}",
                evidence_ids=[e.evidence_id] + [o.evidence_id for o in opposing][:19],
                detail=(f"{e.source_name} indicates {e.signal}; official sources indicate "
                        f"{'/'.join(sorted(s.value for s in official_signals))}")[:400],
            ))
    return conflicts
