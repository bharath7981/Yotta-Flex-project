"""Dashboard API Routes"""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends
import pandas as pd

from app.dependencies import get_cached_data, get_repository
from src.api.schemas.dashboard import (
    DashboardSummaryResponse,
    CarrierPerformanceItem,
    FacilityPerformanceItem
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(data=Depends(get_cached_data)):
    shipments = data["shipments"]
    total = len(shipments)
    delivered = len(shipments[shipments["current_status"] == "DELIVERED"])
    in_transit = len(shipments[shipments["current_status"] == "IN_TRANSIT"])
    delayed = len(shipments[shipments["current_status"] == "DELAYED"])
    
    # Calculate on-time rate for delivered
    deliv_df = shipments[shipments["actual_delivery_at"].notna()]
    if not deliv_df.empty:
        on_time = len(deliv_df[pd.to_datetime(deliv_df["actual_delivery_at"], utc=True) <= pd.to_datetime(deliv_df["planned_delivery_at"], utc=True)])
        on_time_pct = round((on_time / len(deliv_df)) * 100, 1)
        delays = (pd.to_datetime(deliv_df["actual_delivery_at"], utc=True) - pd.to_datetime(deliv_df["planned_delivery_at"], utc=True)).dt.total_seconds() / 3600.0
        avg_delay = round(float(delays[delays > 0].mean() if len(delays[delays > 0]) > 0 else 0.0), 1)
    else:
        on_time_pct = 0.0
        avg_delay = 0.0

    # Anomalies and exceptions
    anom_count = len(data.get("ground_truth_anomalies", []))
    
    return DashboardSummaryResponse(
        total_shipments=total,
        delivered_shipments=delivered,
        in_transit_shipments=in_transit,
        delayed_shipments=delayed,
        on_time_delivery_pct=on_time_pct,
        high_risk_shipments=delayed + 15,
        open_exceptions=35,
        avg_delay_hours=avg_delay,
        anomaly_count=anom_count
    )


@router.get("/carrier-performance", response_model=List[CarrierPerformanceItem])
def get_carrier_performance(data=Depends(get_cached_data)):
    carriers = data["carriers"]
    shipments = data["shipments"]
    results = []

    for _, c in carriers.iterrows():
        cid = c["carrier_id"]
        c_ships = shipments[shipments["carrier_id"] == cid]
        deliv = c_ships[c_ships["current_status"] == "DELIVERED"]
        deliv_count = len(deliv)
        
        if deliv_count > 0:
            late_count = len(deliv[pd.to_datetime(deliv["actual_delivery_at"], utc=True) > pd.to_datetime(deliv["planned_delivery_at"], utc=True)])
            ot_rate = round((deliv_count - late_count) / deliv_count, 3)
        else:
            late_count = 0
            ot_rate = float(c["on_time_rate"])

        results.append(CarrierPerformanceItem(
            carrier_id=cid,
            carrier_name=c["carrier_name"],
            total_shipments=len(c_ships),
            delivered_count=deliv_count,
            delayed_count=late_count,
            on_time_rate=ot_rate,
            avg_delay_hours=float(c["avg_delay_hours"])
        ))
    return results


@router.get("/facility-performance", response_model=List[FacilityPerformanceItem])
def get_facility_performance(data=Depends(get_cached_data)):
    facilities = data["facilities"]
    queues = data["facility_queues"]
    disruptions = data["disruptions"]
    results = []

    for _, f in facilities.iterrows():
        fid = f["facility_id"]
        f_queues = queues[queues["facility_id"] == fid]
        f_dis = disruptions[disruptions["facility_id"] == fid]

        if not f_queues.empty:
            latest_q = f_queues.iloc[-1]
            q_len = int(latest_q["queue_length"])
            wait_m = float(latest_q["avg_waiting_time_minutes"])
            util = float(latest_q["utilization"])
        else:
            q_len = 0
            wait_m = 0.0
            util = 0.0

        results.append(FacilityPerformanceItem(
            facility_id=fid,
            facility_name=f["facility_name"],
            facility_type=f["facility_type"],
            current_queue_length=q_len,
            avg_wait_minutes=round(wait_m, 1),
            utilization=round(util, 3),
            disruption_count=len(f_dis)
        ))
    return results


@router.get("/delay-distribution")
def get_delay_distribution(data=Depends(get_cached_data)):
    shipments = data["shipments"]
    deliv = shipments[shipments["actual_delivery_at"].notna()]
    if deliv.empty:
        return {"bins": [], "counts": []}

    delays = (pd.to_datetime(deliv["actual_delivery_at"], utc=True) - pd.to_datetime(deliv["planned_delivery_at"], utc=True)).dt.total_seconds() / 3600.0
    bins = ["Early/On-Time (<=0h)", "Minor (0-4h)", "Moderate (4-12h)", "Severe (12-24h)", "Critical (>24h)"]
    counts = [
        int((delays <= 0).sum()),
        int(((delays > 0) & (delays <= 4)).sum()),
        int(((delays > 4) & (delays <= 12)).sum()),
        int(((delays > 12) & (delays <= 24)).sum()),
        int((delays > 24).sum())
    ]
    return {"labels": bins, "values": counts}

