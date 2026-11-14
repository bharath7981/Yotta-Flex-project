"""Route API Schemas"""
from typing import Optional, List
from pydantic import BaseModel


class RouteItem(BaseModel):
    route_id: str
    origin_facility_id: str
    destination_facility_id: str
    standard_transit_hours: float
    distance_km: float
    primary_transport_mode: str
    is_congested: bool = False


class RouteListResponse(BaseModel):
    total: int
    routes: List[RouteItem]

