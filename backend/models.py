"""
Gaia Shield - Data Models
Pydantic schemas shared across the API.
"""
from pydantic import BaseModel
from typing import List, Optional


class Zone(BaseModel):
    id: str
    lat: float
    lon: float
    ndvi_current: float
    ndvi_baseline: float
    ndvi_drop: float          # 0..1, how much vegetation cover dropped
    near_road: bool
    near_river: bool
    distance_to_river_km: float
    historical_incidents: int
    risk_score: float         # 0..100
    risk_band: str            # "low" | "medium" | "high" | "critical"


class Evidence(BaseModel):
    label: str
    detail: str


class Alert(BaseModel):
    id: str
    zone_id: str
    lat: float
    lon: float
    threat_type: str          # "illegal_mining" | "illegal_logging" | "poaching_risk"
    confidence: float         # 0..100
    predicted_window_days: int
    headline: str
    explanation: str
    evidence: List[Evidence]
    created_at: str
    status: str = "open"      # "open" | "acknowledged" | "resolved"


class SimulateRequest(BaseModel):
    day_offset: Optional[int] = 1


class SimulateResponse(BaseModel):
    day: int
    zones_scanned: int
    new_alerts: List[Alert]
    total_open_alerts: int
