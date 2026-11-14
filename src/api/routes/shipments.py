"""Shipments API Routes"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
import pandas as pd

from app.dependencies import get_cached_data, get_repository
from src.api.schemas.shipment import (
    ShipmentSummary,
    ShipmentListResponse,
    ShipmentTimelineResponse,
    ShipmentLegItem,
    TrackingEventItem
)

router = APIRouter(prefix="/shipments", tags=["Shipments"])


@router.get("", response_model=ShipmentListResponse)
def list_shipments(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    status: Optional[str] = None,
    carrier_id: Optional[str] = None,
    service_level: Optional[str] = None,
    data=Depends(get_cached_data)
):
    df = data["shipments"].copy()

    if status:
        df = df[df["current_status"] == status.upper()]
    if carrier_id:
        df = df[df["carrier_id"] == carrier_id]
    if service_level:
        df = df[df["service_level"] == service_level.upper()]

    total = len(df)
    subset = df.iloc[skip:skip + limit]

    items = []
    for _, row in subset.iterrows():
        is_deliv = pd.notna(row["actual_delivery_at"])
        delay_h = None
        is_del = None
        if is_deliv:
            plan = pd.to_datetime(row["planned_delivery_at"], utc=True)
            act = pd.to_datetime(row["actual_delivery_at"], utc=True)
            delay_h = round((act - plan).total_seconds() / 3600.0, 1)
            is_del = delay_h > 0

        items.append(ShipmentSummary(
            shipment_id=row["shipment_id"],
            created_at=str(row["created_at"]),
            service_level=row["service_level"],
            carrier_id=row["carrier_id"],
            origin_city=row["origin_city"],
            destination_city=row["destination_city"],
            distance_km=float(row["distance_km"]),
            planned_delivery_at=str(row["planned_delivery_at"]),
            actual_delivery_at=str(row["actual_delivery_at"]) if is_deliv else None,
            current_status=row["current_status"],
            is_delayed=is_del,
            delay_hours=delay_h
        ))

    return ShipmentListResponse(
        total=total,
        skip=skip,
        limit=limit,
        shipments=items
    )


@router.get("/{shipment_id}", response_model=ShipmentSummary)
def get_shipment_detail(shipment_id: str, data=Depends(get_cached_data)):
    df = data["shipments"]
    match = df[df["shipment_id"] == shipment_id]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Shipment {shipment_id} not found")

    row = match.iloc[0]
    is_deliv = pd.notna(row["actual_delivery_at"])
    delay_h = None
    is_del = None
    if is_deliv:
        plan = pd.to_datetime(row["planned_delivery_at"], utc=True)
        act = pd.to_datetime(row["actual_delivery_at"], utc=True)
        delay_h = round((act - plan).total_seconds() / 3600.0, 1)
        is_del = delay_h > 0

    return ShipmentSummary(
        shipment_id=row["shipment_id"],
        created_at=str(row["created_at"]),
        service_level=row["service_level"],
        carrier_id=row["carrier_id"],
        origin_city=row["origin_city"],
        destination_city=row["destination_city"],
        distance_km=float(row["distance_km"]),
        planned_delivery_at=str(row["planned_delivery_at"]),
        actual_delivery_at=str(row["actual_delivery_at"]) if is_deliv else None,
        current_status=row["current_status"],
        is_delayed=is_del,
        delay_hours=delay_h
    )


@router.get("/{shipment_id}/timeline", response_model=ShipmentTimelineResponse)
def get_shipment_timeline(shipment_id: str, data=Depends(get_cached_data)):
    shipments = data["shipments"]
    match = shipments[shipments["shipment_id"] == shipment_id]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Shipment {shipment_id} not found")

    ship = match.iloc[0]
    legs = data["shipment_legs"][data["shipment_legs"]["shipment_id"] == shipment_id].sort_values("leg_sequence")
    events = data["tracking_events"][data["tracking_events"]["shipment_id"] == shipment_id].sort_values("event_time")

    leg_items = []
    for _, l in legs.iterrows():
        leg_items.append(ShipmentLegItem(
            leg_id=l["leg_id"],
            leg_sequence=int(l["leg_sequence"]),
            origin_facility_id=l["origin_facility_id"],
            destination_facility_id=l["destination_facility_id"],
            transport_mode=l["transport_mode"],
            planned_departure_at=str(l["planned_departure_at"]),
            planned_arrival_at=str(l["planned_arrival_at"]),
            actual_departure_at=str(l["actual_departure_at"]) if pd.notna(l.get("actual_departure_at")) else None,
            actual_arrival_at=str(l["actual_arrival_at"]) if pd.notna(l.get("actual_arrival_at")) else None,
            leg_status=l["leg_status"],
            distance_km=float(l["distance_km"])
        ))

    event_items = []
    for _, e in events.iterrows():
        event_items.append(TrackingEventItem(
            event_id=e["event_id"],
            event_type=e["event_type"],
            event_time=str(e["event_time"]),
            ingested_at=str(e["ingested_at"]),
            facility_id=str(e.get("facility_id", "")),
            description=str(e.get("description", "")),
            carrier_id=str(e.get("carrier_id", ""))
        ))

    return ShipmentTimelineResponse(
        shipment_id=shipment_id,
        created_at=str(ship["created_at"]),
        planned_delivery_at=str(ship["planned_delivery_at"]),
        actual_delivery_at=str(ship["actual_delivery_at"]) if pd.notna(ship["actual_delivery_at"]) else None,
        current_status=ship["current_status"],
        legs=leg_items,
        events=event_items
    )


@router.get("/{shipment_id}/legs", response_model=List[ShipmentLegItem])
def get_shipment_legs(shipment_id: str, data=Depends(get_cached_data)):
    legs = data.get("shipment_legs")
    if legs is None or legs.empty:
        raise HTTPException(status_code=404, detail="Shipment legs not found")
    match = legs[legs["shipment_id"] == shipment_id].sort_values("leg_sequence")
    if match.empty:
        # Check if shipment exists
        ships = data.get("shipments")
        if ships is not None and not ships[ships["shipment_id"] == shipment_id].empty:
            return []
        raise HTTPException(status_code=404, detail=f"Shipment {shipment_id} not found")

    items = []
    for _, l in match.iterrows():
        items.append(ShipmentLegItem(
            leg_id=str(l["leg_id"]),
            leg_sequence=int(l["leg_sequence"]),
            origin_facility_id=str(l["origin_facility_id"]),
            destination_facility_id=str(l["destination_facility_id"]),
            transport_mode=str(l["transport_mode"]),
            planned_departure_at=str(l["planned_departure_at"]),
            planned_arrival_at=str(l["planned_arrival_at"]),
            actual_departure_at=str(l["actual_departure_at"]) if pd.notna(l.get("actual_departure_at")) else None,
            actual_arrival_at=str(l["actual_arrival_at"]) if pd.notna(l.get("actual_arrival_at")) else None,
            leg_status=str(l.get("leg_status", "PLANNED")),
            distance_km=float(l.get("distance_km", 0.0))
        ))
    return items


@router.get("/{shipment_id}/events", response_model=List[TrackingEventItem])
def get_shipment_events(shipment_id: str, data=Depends(get_cached_data)):
    events = data.get("tracking_events")
    if events is None or events.empty:
        raise HTTPException(status_code=404, detail="Tracking events not found")
    match = events[events["shipment_id"] == shipment_id].sort_values("event_time")
    if match.empty:
        ships = data.get("shipments")
        if ships is not None and not ships[ships["shipment_id"] == shipment_id].empty:
            return []
        raise HTTPException(status_code=404, detail=f"Shipment {shipment_id} not found")

    items = []
    for _, e in match.iterrows():
        items.append(TrackingEventItem(
            event_id=str(e["event_id"]),
            event_type=str(e["event_type"]),
            event_time=str(e["event_time"]),
            ingested_at=str(e["ingested_at"]),
            facility_id=str(e.get("facility_id", "") or ""),
            description=str(e.get("description", "") or ""),
            carrier_id=str(e.get("carrier_id", "") or "")
        ))
    return items


@router.get("/{shipment_id}/delay-reasons")
def get_shipment_delay_reasons(shipment_id: str, data=Depends(get_cached_data)):
    sdr = data.get("shipment_delay_reasons")
    dr = data.get("delay_reasons")
    if sdr is None or sdr.empty:
        return []
    match = sdr[sdr["shipment_id"] == shipment_id]
    if match.empty:
        return []
    
    if dr is not None and not dr.empty:
        r_col = "reason_id" if "reason_id" in dr.columns else "delay_reason_id"
        merged = match.merge(dr, left_on="reason_id", right_on=r_col, how="left")
        return merged.to_dict(orient="records")
    return match.to_dict(orient="records")


@router.get("/{shipment_id}/eta-history")
def get_shipment_eta_history(shipment_id: str, data=Depends(get_cached_data)):
    etas = data.get("eta_estimates") if "eta_estimates" in data else data.get("eta_snapshots")
    if etas is None or etas.empty:
        return []
    time_col = "prediction_timestamp" if "prediction_timestamp" in etas.columns else "snapshot_time"
    match = etas[etas["shipment_id"] == shipment_id].sort_values(time_col)
    if match.empty:
        return []
    return match.to_dict(orient="records")


@router.get("/{shipment_id}/exceptions")
def get_shipment_exceptions(shipment_id: str, repo=Depends(get_repository)):
    try:
        df = repo.query_df("SELECT * FROM exceptions WHERE shipment_id = ?", [shipment_id])
        return df.to_dict(orient="records")
    except Exception:
        return []

