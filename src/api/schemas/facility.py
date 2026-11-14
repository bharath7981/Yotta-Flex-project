"""Facility and Queue API Schemas"""
from typing import Optional, List
from pydantic import BaseModel


class FacilityItem(BaseModel):
    facility_id: str
    facility_name: str
    facility_type: str
    city: str
    country: str
    latitude: float
    longitude: float
    processing_capacity_per_hour: Optional[int] = None
    avg_processing_time_hours: Optional[float] = None


class FacilityListResponse(BaseModel):
    total: int
    facilities: List[FacilityItem]


class FacilityQueueItem(BaseModel):
    queue_id: str
    facility_id: str
    observed_at: str
    ingested_at: Optional[str] = None
    queue_length: int
    wait_time_hours: float
    congestion_level: str


class FacilityQueueResponse(BaseModel):
    facility_id: str
    total_records: int
    queues: List[FacilityQueueItem]

