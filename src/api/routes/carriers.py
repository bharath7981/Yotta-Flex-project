"""Carriers API Routes"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
import pandas as pd
from app.dependencies import get_cached_data
from src.api.schemas.carrier import CarrierItem, CarrierListResponse

router = APIRouter(prefix="/carriers", tags=["Carriers"])


@router.get("", response_model=CarrierListResponse)
def list_carriers(
    active_only: bool = True,
    primary_mode: Optional[str] = None,
    data=Depends(get_cached_data)
):
    df = data.get("carriers")
    if df is None or df.empty:
        return CarrierListResponse(total=0, carriers=[])

    subset = df.copy()
    if active_only and "is_active" in subset.columns:
        subset = subset[subset["is_active"] == True]
    if primary_mode:
        subset = subset[subset["primary_mode"].astype(str).str.upper() == primary_mode.upper()]

    items = []
    for _, row in subset.iterrows():
        items.append(CarrierItem(
            carrier_id=str(row["carrier_id"]),
            carrier_name=str(row["carrier_name"]),
            primary_mode=str(row["primary_mode"]),
            on_time_rate=float(row.get("on_time_rate", 0.0)),
            avg_delay_hours=float(row.get("avg_delay_hours", 0.0)),
            reliability_score=float(row.get("reliability_score", 0.0)) if pd.notna(row.get("reliability_score")) else None,
            transit_variability_hours=float(row.get("transit_variability_hours", 0.0)) if pd.notna(row.get("transit_variability_hours")) else None,
            is_active=bool(row.get("is_active", True)),
        ))

    return CarrierListResponse(
        total=len(items),
        carriers=items
    )


@router.get("/{carrier_id}", response_model=CarrierItem)
def get_carrier(carrier_id: str, data=Depends(get_cached_data)):
    df = data.get("carriers")
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"Carrier {carrier_id} not found")

    match = df[df["carrier_id"] == carrier_id]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Carrier {carrier_id} not found")

    row = match.iloc[0]
    return CarrierItem(
        carrier_id=str(row["carrier_id"]),
        carrier_name=str(row["carrier_name"]),
        primary_mode=str(row["primary_mode"]),
        on_time_rate=float(row.get("on_time_rate", 0.0)),
        avg_delay_hours=float(row.get("avg_delay_hours", 0.0)),
        reliability_score=float(row.get("reliability_score", 0.0)) if pd.notna(row.get("reliability_score")) else None,
        transit_variability_hours=float(row.get("transit_variability_hours", 0.0)) if pd.notna(row.get("transit_variability_hours")) else None,
        is_active=bool(row.get("is_active", True)),
    )

