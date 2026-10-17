"""Read-only bridge from stored web-intel runs to the incident cycle.

Every value returned here is context for a human reviewer. Callers must not let it
change escalation, severity, routing, or dispatch. Nothing here starts a TinyFish run.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterator, List, Optional, Tuple

from app.intel.routes import evidence_for_hitl, latest_evidence_for
from app.intel.sources import STATE_CODES

ATTACHED = "ATTACHED"
STALE = "STALE"
NONE_AVAILABLE = "NONE_AVAILABLE"
FAILED = "FAILED"

MAX_ITEMS = 100
_DISTRICT_SUFFIX = re.compile(r"\s+(district|dist\.?)$", re.IGNORECASE)
_PLACE = re.compile(r"^[\w ,.'()\-]+$")
MOBILITY_CATEGORIES = ("rail_disruption", "road_closure")


def place_from_location(location: str) -> Tuple[Optional[str], Optional[str]]:
    """'Patna, Bihar' -> ('Patna', 'Bihar'); 'Patna District' -> ('Patna', None); 'Bihar' -> (None, 'Bihar')."""
    text = " ".join(str(location or "").split())
    if not text or not _PLACE.match(text):
        return None, None
    parts = [p.strip() for p in text.split(",") if p.strip()]
    state = next((p for p in parts[1:] if p.lower() in STATE_CODES), None)
    head = _DISTRICT_SUFFIX.sub("", parts[0]) if parts else ""
    if head.lower() in STATE_CODES:
        return None, state or head
    return (head[:80] or None), state


def _queries(location: str, lat: float, lon: float) -> Iterator[Dict[str, Any]]:
    district, state = place_from_location(location)
    if district or state:
        yield {"district": district, "state": state}
    yield {"lat": float(lat), "lon": float(lon)}


def _failed(reason: str) -> Dict[str, Any]:
    return {"status": FAILED, "error": reason[:300], "run_id": None, "evidence": [], "conflicts": [],
            "failed_sources": [], "data_quality": []}


def lookup(location: str, lat: float, lon: float) -> Dict[str, Any]:
    """Compact evidence for the place: by district/state when the name gives one, else within 0.5 deg of lat/lon."""
    web: Dict[str, Any] = {}
    try:
        for query in _queries(location, lat, lon):
            web = {**evidence_for_hitl(max_items=MAX_ITEMS, **query), "matched_by": query}
            if web["status"] != NONE_AVAILABLE:
                break
    except Exception as exc:
        return _failed(f"web evidence lookup failed: {type(exc).__name__}: {exc}")
    web["active_official_alerts"] = active_official_alerts(web)
    web["verified_helplines"] = verified_helplines(web)
    web["affects_escalation"] = False
    return web


def latest_run(location: str, lat: float, lon: float):
    """Full WebIntelRun (with notes) for the place if one is fresh, else None. Raises on store errors."""
    for query in _queries(location, lat, lon):
        run = latest_evidence_for(**query)
        if run is not None:
            return run
    return None


def _usable(web: Dict[str, Any]) -> List[Dict[str, Any]]:
    if web.get("status") != ATTACHED:
        return []
    return [e for e in web.get("evidence", []) if e.get("validation_status") != "rejected"]


def cite(e: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "claim": e.get("claim"),
        "category": e.get("category"),
        "source_name": e.get("source_name"),
        "source_type": e.get("source_type"),
        "source_url": e.get("source_url"),
        "published_at": e.get("published_at"),
        "observed_at": e.get("observed_at"),
        "retrieved_at": e.get("retrieved_at"),
        "grade": e.get("grade"),
        "validation_status": e.get("validation_status"),
        "mock": bool(e.get("mock")),
    }


def reported_disruptions(web: Dict[str, Any]) -> List[Dict[str, Any]]:
    """F3: rail/road disruptions reported by sources. Advisory only; the route is not changed by them."""
    return [
        {**cite(e), "advisory": "reported disruption for human review; the computed route does not avoid it automatically"}
        for e in _usable(web) if e.get("category") in MOBILITY_CATEGORIES
    ]


def independent_reports(web: Dict[str, Any]) -> Dict[str, Any]:
    """F6: news corroboration as its own signal, graded credible_secondary at best. Never escalates."""
    items = [e for e in _usable(web) if e.get("category") == "news_report"]
    return {
        "signal": "independent_news_reports",
        "grade": "credible_secondary",
        "count": len(items),
        "links": [cite(e) for e in items],
        "affects_escalation": False,
        "note": "News reports found by district name. They may raise human attention, never escalation.",
    }


def verified_helplines(web: Dict[str, Any]) -> List[Dict[str, Any]]:
    """F7: helpline numbers that two official sources agree on (validation_status verified), one per number."""
    out: Dict[str, Dict[str, Any]] = {}
    for e in _usable(web):
        if e.get("category") != "helpline" or e.get("validation_status") != "verified":
            continue
        label, _, number = str(e.get("claim") or "").partition(":")
        number = number.strip()
        key = re.sub(r"\D", "", number)
        if not key:
            continue
        entry = out.setdefault(key, {**cite(e), "label": label.strip(), "number": number, "source_urls": []})
        if e.get("source_url") and e["source_url"] not in entry["source_urls"]:
            entry["source_urls"].append(e["source_url"])
    return list(out.values())


def active_official_alerts(web: Dict[str, Any]) -> List[Dict[str, Any]]:
    """F2: alerts already issued by official systems for the area, shown so a reviewer can spot duplicates."""
    return [cite(e) for e in _usable(web) if e.get("category") == "official_alert"]


def report_sources(web: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Non-rejected evidence for the SITREP section, fresh or stale (the section prints the status)."""
    if web.get("status") not in (ATTACHED, STALE):
        return []
    return [cite(e) for e in web.get("evidence", []) if e.get("validation_status") != "rejected"]
