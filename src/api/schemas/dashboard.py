"""Dashboard Schemas"""
from typing import Dict, List, Any, Optional
from pydantic import BaseModel


class DashboardSummaryResponse(BaseModel):
    total_shipments: int
    delivered_shipments: int
    in_transit_shipments: int
    delayed_shipments: int
    on_time_delivery_pct: float
    high_risk_shipments: int
    open_exceptions: int
    avg_delay_hours: float
    anomaly_count: int


class CarrierPerformanceItem(BaseModel):
    carrier_id: str
    carrier_name: str
    total_shipments: int
    delivered_count: int
    delayed_count: int
    on_time_rate: float
    avg_delay_hours: float


class FacilityPerformanceItem(BaseModel):
    facility_id: str
    facility_name: str
    facility_type: str
    current_queue_length: int
    avg_wait_minutes: float
    utilization: float
    disruption_count: int

