"""Routes Master API Routes"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
import pandas as pd
from app.dependencies import get_cached_data
from src.api.schemas.route import RouteItem, RouteListResponse

router = APIRouter(prefix="/routes", tags=["Routes"])


@router.get("", response_model=RouteListResponse)
def list_routes(
    origin_facility_id: Optional[str] = None,
    destination_facility_id: Optional[str] = None,
    mode: Optional[str] = None,
    limit: int = 250,
    data=Depends(get_cached_data)
):
    n_limit = limit if isinstance(limit, int) else 250
    df = data.get("routes")
    if df is None or df.empty:
        return RouteListResponse(total=0, routes=[])

    subset = df.copy()
    if origin_facility_id:
        subset = subset[subset["origin_facility_id"] == origin_facility_id]
    if destination_facility_id:
        subset = subset[subset["destination_facility_id"] == destination_facility_id]
    if mode:
        subset = subset[subset["primary_transport_mode"].astype(str).str.upper() == mode.upper()]

    subset = subset.head(n_limit)
    items = []
    for _, row in subset.iterrows():
        items.append(RouteItem(
            route_id=str(row["route_id"]),
            origin_facility_id=str(row["origin_facility_id"]),
            destination_facility_id=str(row["destination_facility_id"]),
            standard_transit_hours=float(row.get("standard_transit_hours", 0.0)),
            distance_km=float(row.get("distance_km", 0.0)),
            primary_transport_mode=str(row.get("primary_transport_mode", "TRUCK")),
            is_congested=bool(row.get("is_congested", False)),
        ))

    return RouteListResponse(
        total=len(items),
        routes=items
    )


@router.get("/{route_id}", response_model=RouteItem)
def get_route(route_id: str, data=Depends(get_cached_data)):
    df = data.get("routes")
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"Route {route_id} not found")

    match = df[df["route_id"] == route_id]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Route {route_id} not found")

    row = match.iloc[0]
    return RouteItem(
        route_id=str(row["route_id"]),
        origin_facility_id=str(row["origin_facility_id"]),
        destination_facility_id=str(row["destination_facility_id"]),
        standard_transit_hours=float(row.get("standard_transit_hours", 0.0)),
        distance_km=float(row.get("distance_km", 0.0)),
        primary_transport_mode=str(row.get("primary_transport_mode", "TRUCK")),
        is_congested=bool(row.get("is_congested", False)),
    )
