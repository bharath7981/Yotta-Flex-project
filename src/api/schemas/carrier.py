"""Carrier API Schemas"""
from typing import Optional, List
from pydantic import BaseModel


class CarrierItem(BaseModel):
    carrier_id: str
    carrier_name: str
    primary_mode: str
    on_time_rate: float
    avg_delay_hours: float
    reliability_score: Optional[float] = None
    transit_variability_hours: Optional[float] = None
    is_active: bool = True


class CarrierListResponse(BaseModel):
    total: int
    carriers: List[CarrierItem]

