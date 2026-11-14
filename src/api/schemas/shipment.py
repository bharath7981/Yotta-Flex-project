"""Shipment Pydantic Schemas"""
from typing import Optional, List, Any
from pydantic import BaseModel


class ShipmentSummary(BaseModel):
    shipment_id: str
    created_at: str
    service_level: str
    carrier_id: str
    origin_city: str
    destination_city: str
    distance_km: float
    planned_delivery_at: str
    actual_delivery_at: Optional[str] = None
    current_status: str
    is_delayed: Optional[bool] = None
    delay_hours: Optional[float] = None


class ShipmentLegItem(BaseModel):
    leg_id: str
    leg_sequence: int
    origin_facility_id: str
    destination_facility_id: str
    transport_mode: str
    planned_departure_at: str
    planned_arrival_at: str
    actual_departure_at: Optional[str] = None
    actual_arrival_at: Optional[str] = None
    leg_status: str
    distance_km: float


class TrackingEventItem(BaseModel):
    event_id: str
    event_type: str
    event_time: str
    ingested_at: str
    facility_id: str
    description: str
    carrier_id: str


class ShipmentTimelineResponse(BaseModel):
    shipment_id: str
    created_at: str
    planned_delivery_at: str
    actual_delivery_at: Optional[str] = None
    current_status: str
    legs: List[ShipmentLegItem]
    events: List[TrackingEventItem]


class ShipmentListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    shipments: List[ShipmentSummary]

