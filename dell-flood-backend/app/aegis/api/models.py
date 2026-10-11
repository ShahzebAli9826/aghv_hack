from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class LatLng(BaseModel):
    lat: float
    lng: float

class FloodPolygon(BaseModel):
    place: str = ""
    name: str = ""
    severity: Optional[str] = "HIGH"
    description: Optional[str] = ""
    coordinates: List[LatLng] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        if not self.name and self.place:
            self.name = self.place
        elif not self.place and self.name:
            self.place = self.name


class FieldValue(BaseModel):
    value: Any = None
    source: str = ""
    confidence: str = ""
    description: str = ""


class PointDossier(BaseModel):
    lat: float
    lng: float
    fields: Dict[str, FieldValue] = Field(default_factory=dict)
    raw_fields: Dict[str, Any] = Field(default_factory=dict)
    cached: bool = False


class DossierSummary(BaseModel):
    total_points_sampled: int = 0
    avg_elevation_ft: Optional[float] = None
    min_elevation_ft: Optional[float] = None
    max_elevation_ft: Optional[float] = None
    flood_zone_distribution: Dict[str, int] = Field(default_factory=dict)
    avg_flood_risk_score: Optional[float] = None
    max_flood_risk_score: Optional[float] = None
    waterbody_Wait_pct: Optional[float] = None
    land_cover_distribution: Dict[str, int] = Field(default_factory=dict)
    nearest_hospitals: List[str] = Field(default_factory=list)
    nearest_fire_stations: List[str] = Field(default_factory=list)
    nearest_shelters: List[str] = Field(default_factory=list)
    avg_distance_to_hospital_m: Optional[float] = None
    avg_distance_to_road_m: Optional[float] = None
    avg_population_density: Optional[float] = None
    svi_scores: List[float] = Field(default_factory=list)
    avg_svi_score: Optional[float] = None
    soil_types: List[str] = Field(default_factory=list)


class FloodDossier(BaseModel):
    polygon_name: str
    polygon_description: Optional[str] = None
    severity: Optional[str] = "HIGH"
    centroid_lat: float
    centroid_lng: float
    extracted_at: str
    preset_used: str = "flood"
    point_dossiers: List[PointDossier] = Field(default_factory=list)
    summary: DossierSummary = Field(default_factory=DossierSummary)
    raw_polygon: List[Dict[str, float]] = Field(default_factory=list)
