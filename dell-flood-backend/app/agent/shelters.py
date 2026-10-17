"""Shelter candidates for the incident cycle. Never invents a shelter.

Sources, in order: relief camps listed in official reports (latest fresh web-intel
run), then the operator shelter registry in flood_database.db, then nothing.
Web-listed camps have no coordinates and unconfirmed availability, so routing and
capacity allocation only ever use registry rows.
"""
from __future__ import annotations

import math
import re
import sqlite3
from typing import Any, Dict, List, Optional

from app.agent import web_evidence

# Same relative path endpoints.DB_PATH uses; opened read-only.
REGISTRY_DB_PATH = "flood_database.db"
REGISTRY_RADIUS_KM = 50.0
WEB_CAMPS = "web_relief_camps"
REGISTRY = "registry_shelters"
NO_VERIFIED = "no_verified_shelters"
_CAPACITY_NOTE = re.compile(r"^capacity as reported: (\d+)$")
_OCCUPANCY_NOTE = re.compile(r"^occupancy as reported: (\d+)$")


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def _note_int(notes: List[str], pattern: re.Pattern) -> Optional[int]:
    for note in notes:
        m = pattern.match(note)
        if m:
            return int(m.group(1))
    return None


def relief_camps(run) -> List[Dict[str, Any]]:
    camps = []
    for e in run.evidence if run else []:
        if e.category.value != "relief_camp" or e.validation_status.value == "rejected":
            continue
        camps.append({
            "name": e.claim.removeprefix("Relief camp listed: "),
            "lat": None,
            "lon": None,
            "elevation_m": None,
            "capacity": _note_int(e.notes, _CAPACITY_NOTE),
            "occupancy": _note_int(e.notes, _OCCUPANCY_NOTE),
            "district": e.district,
            "geocode_confidence": "none: the report names the place only; not geocoded",
            "availability": "unconfirmed: listed in an official report, not a guarantee of space",
            "source": WEB_CAMPS,
            "source_name": e.source_name,
            "source_url": e.source_url,
            "report_date": e.published_at.isoformat() if e.published_at else None,
            "retrieved_at": e.retrieved_at.isoformat(),
            "validation_status": e.validation_status.value,
            "web_intel_run_id": run.run_id,
            "mock": e.mock,
        })
    return camps


def registry_shelters(lat: float, lon: float) -> List[Dict[str, Any]]:
    try:
        conn = sqlite3.connect(f"file:{REGISTRY_DB_PATH}?mode=ro", uri=True)
        try:
            rows = conn.execute("SELECT name, latitude, longitude, capacity, slots_available FROM shelters").fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return []
    out = []
    for name, s_lat, s_lon, status_colour, slots in rows:
        if s_lat is None or s_lon is None:
            continue
        distance = _km(lat, lon, float(s_lat), float(s_lon))
        if distance <= REGISTRY_RADIUS_KM:
            free = max(0, int(slots or 0))
            # The registry's capacity column is a colour status, so total capacity is unknown.
            out.append({
                "name": name, "lat": float(s_lat), "lon": float(s_lon), "elevation_m": None,
                "capacity": None, "slots_available": free, "status_colour": status_colour,
                "distance_km": round(distance, 2), "source": REGISTRY,
                "provenance": "operator shelter registry (flood_database.db shelters table)",
            })
    return sorted(out, key=lambda s: s["distance_km"])


def find_safe_shelters(location: str, lat: float, lon: float) -> Dict[str, Any]:
    notes: List[str] = []
    try:
        camps = relief_camps(web_evidence.latest_run(location, lat, lon))
    except Exception as exc:
        camps = []
        notes.append(f"web evidence unavailable ({type(exc).__name__}: {exc})"[:300])
    if camps:
        return {"status": WEB_CAMPS, "shelters": camps, "notes": notes + [
            "Relief camps from the latest official report retrieved via TinyFish; not geocoded, availability unconfirmed."]}
    registry = registry_shelters(lat, lon)
    if registry:
        return {"status": REGISTRY, "shelters": registry, "notes": notes}
    return {"status": NO_VERIFIED, "shelters": [], "notes": notes + [
        f"No relief camp in recent official evidence and no registry shelter within {REGISTRY_RADIUS_KM:.0f} km."]}


def allocate(population: int, location: str, lat: float, lon: float) -> Dict[str, Any]:
    """Greedy nearest-first allocation over registry shelters' free slots. Web-listed camps are never allocated."""
    listing = find_safe_shelters(location, lat, lon)
    registry = registry_shelters(lat, lon)
    remaining = int(population)
    allocations = []
    for shelter in registry:
        take = min(remaining, shelter["slots_available"])
        allocations.append({"name": shelter["name"], "allocated": take, "slots_available": shelter["slots_available"]})
        remaining -= take
    allocated = int(population) - remaining
    if not registry:
        status = NO_VERIFIED
    else:
        status = "CAPACITY_BALANCED" if remaining == 0 else "CAPACITY_SHORTFALL"
    return {
        "allocated_population": allocated,
        "primary_shelter_allocated": allocations[0]["allocated"] if allocations else 0,
        "secondary_shelter_allocated": sum(a["allocated"] for a in allocations[1:]),
        "unallocated": remaining,
        "status": status,
        "allocations": allocations,
        "shelter_listing": listing,
    }


def nearest_registry_shelter(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    registry = registry_shelters(lat, lon)
    return registry[0] if registry else None
