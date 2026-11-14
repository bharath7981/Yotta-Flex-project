"""Facilities and Queues API Routes"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
import pandas as pd
from app.dependencies import get_cached_data
from src.api.schemas.facility import (
    FacilityItem,
    FacilityListResponse,
    FacilityQueueItem,
    FacilityQueueResponse
)

router = APIRouter(prefix="/facilities", tags=["Facilities"])


@router.get("", response_model=FacilityListResponse)
def list_facilities(
    facility_type: Optional[str] = None,
    country: Optional[str] = None,
    data=Depends(get_cached_data)
):
    df = data.get("facilities")
    if df is None or df.empty:
        return FacilityListResponse(total=0, facilities=[])

    subset = df.copy()
    if facility_type:
        subset = subset[subset["facility_type"].astype(str).str.upper() == facility_type.upper()]
    if country:
        subset = subset[subset["country"].astype(str).str.upper() == country.upper()]

    items = []
    for _, row in subset.iterrows():
        items.append(FacilityItem(
            facility_id=str(row["facility_id"]),
            facility_name=str(row["facility_name"]),
            facility_type=str(row["facility_type"]),
            city=str(row["city"]),
            country=str(row["country"]),
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            processing_capacity_per_hour=int(row["processing_capacity_per_hour"]) if pd.notna(row.get("processing_capacity_per_hour")) else None,
            avg_processing_time_hours=float(row["avg_processing_time_hours"]) if pd.notna(row.get("avg_processing_time_hours")) else None,
        ))

    return FacilityListResponse(
        total=len(items),
        facilities=items
    )


@router.get("/{facility_id}", response_model=FacilityItem)
def get_facility(facility_id: str, data=Depends(get_cached_data)):
    df = data.get("facilities")
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"Facility {facility_id} not found")

    match = df[df["facility_id"] == facility_id]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Facility {facility_id} not found")

    row = match.iloc[0]
    return FacilityItem(
        facility_id=str(row["facility_id"]),
        facility_name=str(row["facility_name"]),
        facility_type=str(row["facility_type"]),
        city=str(row["city"]),
        country=str(row["country"]),
        latitude=float(row["latitude"]),
        longitude=float(row["longitude"]),
        processing_capacity_per_hour=int(row["processing_capacity_per_hour"]) if pd.notna(row.get("processing_capacity_per_hour")) else None,
        avg_processing_time_hours=float(row["avg_processing_time_hours"]) if pd.notna(row.get("avg_processing_time_hours")) else None,
    )


@router.get("/{facility_id}/queues", response_model=FacilityQueueResponse)
def get_facility_queues(
    facility_id: str,
    limit: int = 100,
    data=Depends(get_cached_data)
):
    n_limit = limit if isinstance(limit, int) else 100
    facs = data.get("facilities")
    if facs is not None and not facs.empty:
        if facs[facs["facility_id"] == facility_id].empty:
            raise HTTPException(status_code=404, detail=f"Facility {facility_id} not found")

    queues = data.get("facility_queues")
    if queues is None or queues.empty:
        return FacilityQueueResponse(facility_id=facility_id, total_records=0, queues=[])

    match = queues[queues["facility_id"] == facility_id].sort_values("observed_at", ascending=False).head(n_limit)
    items = []
    for _, row in match.iterrows():
        items.append(FacilityQueueItem(
            queue_id=str(row["queue_id"]),
            facility_id=str(row["facility_id"]),
            observed_at=str(row["observed_at"]),
            ingested_at=str(row["ingested_at"]) if pd.notna(row.get("ingested_at")) else None,
            queue_length=int(row.get("queue_length", 0)),
            wait_time_hours=float(row.get("wait_time_hours", 0.0)),
            congestion_level=str(row.get("congestion_level", "NORMAL")),
        ))

    return FacilityQueueResponse(
        facility_id=facility_id,
        total_records=len(items),
        queues=items
    )
