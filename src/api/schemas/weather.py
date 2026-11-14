"""Weather API Schemas"""
from typing import Optional, List
from pydantic import BaseModel


class WeatherEventItem(BaseModel):
    weather_id: str
    facility_id: Optional[str] = None
    route_id: Optional[str] = None
    weather_type: str
    severity: str
    started_at: str
    ended_at: str
    impact_delay_hours: float
    visibility_km: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    precipitation_mm: Optional[float] = None


class WeatherListResponse(BaseModel):
    total: int
    weather_events: List[WeatherEventItem]

