"""
pipeline/cluster.py
Step 3: Compute building clusters (the "from" points)
Using DBSCAN clustering on building coordinates or a regular grid-cell fallback.
"""
from __future__ import annotations
import math
try:
    from sklearn.cluster import DBSCAN
    HAS_SKLEARN = True
except Exception:
    HAS_SKLEARN = False
    DBSCAN = None

try:
    from app.aegis.api.models import FloodPolygon
except ImportError:
    from api.models import FloodPolygon

AVG_HOUSEHOLD_SIZE = 2.6  # Standard emergency planning average


def cluster_buildings(
    buildings: list[dict[str, float]],
    eps_deg: float = 0.004,
    min_samples: int = 2,
) -> dict[int, list[dict[str, float]]]:
    """
    Cluster building points using DBSCAN or grid-cell fallback.
    buildings: list of dicts with 'lat' and 'lng' (or 'lon') keys.
    eps_deg: ~0.004 degrees is ~400m-450m.
    Returns dict mapping cluster_id -> list of buildings in that cluster.
    """
    if not buildings:
        return {}

    coords = np.array([[b.get("lat", 0.0), b.get("lng", b.get("lon", 0.0))] for b in buildings])

    if len(coords) < min_samples:
        return {0: buildings}

    labels = []
    if HAS_SKLEARN and DBSCAN is not None:
        try:
            clustering = DBSCAN(eps=eps_deg, min_samples=min_samples).fit(coords)
            labels = clustering.labels_
        except Exception:
            labels = []

    if len(labels) == 0:
        cell_to_id = {}
        for pt in coords:
            cell = (round(float(pt[0]) / eps_deg), round(float(pt[1]) / eps_deg))
            if cell not in cell_to_id:
                cell_to_id[cell] = len(cell_to_id)
            labels.append(cell_to_id[cell])

    clusters: dict[int, list[dict[str, float]]] = {}
    for label, b in zip(labels, buildings):
        clusters.setdefault(int(label), []).append(b)

    return clusters


def cluster_centroid(cluster_buildings: list[dict[str, float]]) -> tuple[float, float]:
    """Calculate the geometric centroid (lat, lng) of a building cluster."""
    lats = [b.get("lat", 0.0) for b in cluster_buildings]
    lngs = [b.get("lng", b.get("lon", 0.0)) for b in cluster_buildings]
    if not lats:
        return 0.0, 0.0
    return float(sum(lats) / len(lats)), float(sum(lngs) / len(lngs))


def generate_polygon_building_clusters(
    polygon: FloodPolygon,
    num_grid_cells: int = 4,
) -> list[dict]:
    """
    Extract or generate building clusters inside the flood polygon.
    Uses a local Generator (no global np.random.seed(42) mutation) and supports both .name and .place.
    """
    lats = [pt.lat for pt in polygon.coordinates]
    lngs = [pt.lng for pt in polygon.coordinates]
    min_lat, max_lat = min(lats), max(lats)
    min_lng, max_lng = min(lngs), max(lngs)

    seed_val = abs(int((min_lat * 10000 + min_lng * 10000))) % (2**31 - 1)
    rng = np.random.default_rng(seed_val)
    sample_buildings = []

    centers = [
        (min_lat + 0.25 * (max_lat - min_lat), min_lng + 0.3 * (max_lng - min_lng)),
        (min_lat + 0.7 * (max_lat - min_lat), min_lng + 0.4 * (max_lng - min_lng)),
        (min_lat + 0.5 * (max_lat - min_lat), min_lng + 0.75 * (max_lng - min_lng)),
    ]

    for c_lat, c_lng in centers:
        count = int(rng.integers(15, 35))
        for _ in range(count):
            b_lat = float(c_lat + rng.normal(0, 0.0015))
            b_lng = float(c_lng + rng.normal(0, 0.0015))
            sample_buildings.append({"lat": b_lat, "lng": b_lng})

    raw_clusters = cluster_buildings(sample_buildings, eps_deg=0.0035, min_samples=3)
    poly_label = getattr(polygon, "name", "") or getattr(polygon, "place", "") or "zone"

    formatted_clusters = []
    for cid, b_list in raw_clusters.items():
        if cid == -1:
            continue
        c_lat, c_lng = cluster_centroid(b_list)
        pop_est = int(round(len(b_list) * AVG_HOUSEHOLD_SIZE * 4.5))
        formatted_clusters.append({
            "cluster_id": f"{poly_label}_cluster_{cid + 1}",
            "centroid": (c_lat, c_lng),
            "building_count": len(b_list),
            "population_estimate": pop_est,
            "buildings": b_list,
        })

    return formatted_clusters
