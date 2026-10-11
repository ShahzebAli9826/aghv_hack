import hashlib
import json
from typing import Any, List, Tuple

_MEMORY_CACHE = {}

def get(key: str):
    return _MEMORY_CACHE.get(key)

def set(key: str, val: Any):
    if len(_MEMORY_CACHE) > 250:
        _MEMORY_CACHE.pop(next(iter(_MEMORY_CACHE)), None)
    _MEMORY_CACHE[key] = val

def polygon_hash(coordinates: List[Any]) -> str:
    serial = []
    for pt in coordinates or []:
        lat = getattr(pt, "lat", pt.get("lat", 0.0) if isinstance(pt, dict) else 0.0)
        lng = getattr(pt, "lng", pt.get("lng", 0.0) if isinstance(pt, dict) else 0.0)
        serial.append((round(float(lat), 5), round(float(lng), 5)))
    return hashlib.sha256(json.dumps(serial).encode("utf-8")).hexdigest()[:12]

def make_batch_cache_key(points: List[Tuple[float, float]], preset_or_fields: str) -> str:
    norm_pts = [(round(float(lat), 5), round(float(lng), 5)) for lat, lng in points]
    payload = {"pts": norm_pts, "preset": preset_or_fields}
    return "batch_" + hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
