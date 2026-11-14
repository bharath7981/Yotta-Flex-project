"""Predictions API Routes — Phase 5 Upgrade
Removes all hardcoded feature defaults.
Builds real point-in-time features using AsOfView from actual operational data.
"""
from datetime import datetime, timezone
from typing import List
import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_cached_data, get_predictor
from src.api.schemas.prediction import (
    ETAPredictionRequest,
    ETAPredictionResponse,
    DelayRiskResponse
)
from src.features.asof import AsOfView
from src.data.sla import get_sla_rule, get_promised_delivery

router = APIRouter(prefix="/predictions", tags=["Predictions"])

# Feature columns in training order
FEATURE_COLS = [
    "shipment_age_hours",
    "num_legs",
    "weight_kg",
    "distance_km",
    "planned_transit_hours",
    "planned_remaining_hours",
    "completed_legs",
    "remaining_legs",
    "progress_pct",
    "hours_since_last_event",
    "missing_expected_scans",
    "carrier_on_time_rate",
    "carrier_avg_delay",
    "carrier_reliability",
    "current_queue_length",
    "avg_wait_minutes",
    "facility_utilization",
    "facility_disrupted",
    "precipitation_mm",
    "wind_speed_kmh",
    "weather_disruptive",
    "route_changes_count",
]


def _build_live_features(
    ship: pd.Series,
    asof: AsOfView,
    snap_time: pd.Timestamp,
    all_data: dict,
) -> tuple:
    """
    Build a feature dictionary from live operational data at snap_time.
    Returns (feature_dict, warnings_list).
    """
    warnings: List[str] = []
    ship_id = str(ship["shipment_id"])
    carrier_id = str(ship["carrier_id"])
    service_level = str(ship["service_level"])

    created_at = pd.to_datetime(ship["created_at"], utc=True)
    planned_delivery_at = pd.to_datetime(ship["planned_delivery_at"], utc=True)

    # 1. Shipment attributes
    shipment_age_hours = max(0.0, (snap_time - created_at).total_seconds() / 3600.0)
    planned_transit_hours = float(ship["planned_transit_hours"])
    planned_remaining_hours = max(0.0, (planned_delivery_at - snap_time).total_seconds() / 3600.0)
    distance_km = float(ship["distance_km"])
    weight_kg = float(ship["weight_kg"])
    num_legs = int(ship["num_legs"])

    # 2. Progress (ingested_at-ordered events)
    events = asof.get_tracking_events(ship_id, snap_time)
    num_events = len(events)

    if num_events > 0:
        last_event = events.iloc[-1]
        last_event_time = pd.to_datetime(last_event["event_time"], utc=True)
        hours_since_last_event = max(0.0, (snap_time - last_event_time).total_seconds() / 3600.0)
        current_facility_id = last_event["facility_id"]
    else:
        hours_since_last_event = shipment_age_hours
        current_facility_id = ship["origin_facility_id"]
        warnings.append("No tracking events found by snapshot_time — progress features use defaults")

    arrival_events = events[events["event_type"] == "ARRIVAL"] if num_events > 0 else pd.DataFrame()
    completed_legs = min(len(arrival_events), num_legs)
    remaining_legs = max(0, num_legs - completed_legs)
    progress_pct = round(completed_legs / max(num_legs, 1), 3)

    expected_scans = int((shipment_age_hours / max(planned_transit_hours, 1.0)) * (num_legs * 2))
    missing_expected_scans = max(0, expected_scans - num_events)

    # 3. Carrier performance (temporal)
    carrier_perf = asof.get_carrier_performance(carrier_id, snap_time, exclude_shipment_id=ship_id)
    if carrier_perf["carrier_sample_size"] < 3:
        warnings.append(
            f"Carrier {carrier_id} has only {carrier_perf['carrier_sample_size']} completed shipments "
            "before snapshot — carrier features use Bayesian prior"
        )
    carrier_on_time_rate = carrier_perf["carrier_on_time_rate"]
    carrier_avg_delay = carrier_perf["carrier_avg_delay_hours"]
    carrier_reliability = carrier_perf["carrier_reliability"]

    # 4. Facility queue (NaN if unavailable)
    q = asof.get_facility_queue(current_facility_id, snap_time)
    if q is not None:
        current_queue_length = float(q["queue_length"])
        avg_wait_minutes = float(q["avg_waiting_time_minutes"])
        facility_utilization = float(q["utilization"])
        facility_disrupted = int(q["is_disrupted"])
    else:
        current_queue_length = np.nan
        avg_wait_minutes = np.nan
        facility_utilization = np.nan
        facility_disrupted = 0
        warnings.append(f"No facility queue data for {current_facility_id} at snapshot_time")

    # 5. Weather (NaN if unavailable)
    wf = asof.get_weather_forecast(current_facility_id, snap_time)
    if wf is not None:
        precipitation_mm = float(wf["precipitation_mm"])
        wind_speed_kmh = float(wf["wind_speed_kmh"])
        weather_disruptive = int(wf["is_disruptive"])
    else:
        precipitation_mm = np.nan
        wind_speed_kmh = np.nan
        weather_disruptive = 0
        warnings.append(f"No weather forecast for {current_facility_id} at snapshot_time")

    # 6. Route changes
    rc = asof.get_route_changes(ship_id, snap_time)
    route_changes_count = len(rc)

    feature_dict = {
        "shipment_age_hours": shipment_age_hours,
        "num_legs": num_legs,
        "weight_kg": weight_kg,
        "distance_km": distance_km,
        "planned_transit_hours": planned_transit_hours,
        "planned_remaining_hours": planned_remaining_hours,
        "completed_legs": completed_legs,
        "remaining_legs": remaining_legs,
        "progress_pct": progress_pct,
        "hours_since_last_event": hours_since_last_event,
        "missing_expected_scans": missing_expected_scans,
        "carrier_on_time_rate": carrier_on_time_rate,
        "carrier_avg_delay": carrier_avg_delay,
        "carrier_reliability": carrier_reliability,
        "current_queue_length": current_queue_length,
        "avg_wait_minutes": avg_wait_minutes,
        "facility_utilization": facility_utilization,
        "facility_disrupted": facility_disrupted,
        "precipitation_mm": precipitation_mm,
        "wind_speed_kmh": wind_speed_kmh,
        "weather_disruptive": weather_disruptive,
        "route_changes_count": route_changes_count,
    }
    return feature_dict, warnings


@router.post("/eta", response_model=ETAPredictionResponse)
def predict_eta(req: ETAPredictionRequest, data=Depends(get_cached_data), predictor=Depends(get_predictor)):
    shipments = data["shipments"]
    match = shipments[shipments["shipment_id"] == req.shipment_id]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Shipment {req.shipment_id} not found")

    ship = match.iloc[0]
    snap_time_str = req.snapshot_time or datetime.now(timezone.utc).isoformat()
    snap_dt = pd.to_datetime(snap_time_str, utc=True)

    asof = AsOfView(data)
    feature_dict, warnings = _build_live_features(ship, asof, snap_dt, data)

    if req.custom_features:
        feature_dict.update(req.custom_features)

    # Build input row
    row_dict = {"eta_id": "PRED-LIVE", "shipment_id": req.shipment_id, "snapshot_time": snap_time_str}
    row_dict.update(feature_dict)

    df_in = pd.DataFrame([row_dict])
    pred_res = predictor.predict_eta(df_in).iloc[0]

    return ETAPredictionResponse(
        shipment_id=req.shipment_id,
        eta_id=str(pred_res["eta_id"]),
        snapshot_time=str(pred_res["snapshot_time"]),
        planned_delivery_at=str(ship["planned_delivery_at"]),
        predicted_delivery_at=str(pred_res["predicted_delivery_at"]),
        predicted_remaining_hours=float(pred_res["predicted_remaining_hours"]),
        prediction_method=str(pred_res["prediction_method"]),
        model_version=str(pred_res["model_version"]),
        prediction_timestamp=str(pred_res["prediction_timestamp"]),
        data_quality_warnings=warnings,
    )


@router.post("/delay-risk", response_model=DelayRiskResponse)
def predict_delay_risk(req: ETAPredictionRequest, data=Depends(get_cached_data), predictor=Depends(get_predictor)):
    shipments = data["shipments"]
    match = shipments[shipments["shipment_id"] == req.shipment_id]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Shipment {req.shipment_id} not found")

    ship = match.iloc[0]
    snap_time_str = req.snapshot_time or datetime.now(timezone.utc).isoformat()
    snap_dt = pd.to_datetime(snap_time_str, utc=True)

    asof = AsOfView(data)
    feature_dict, warnings = _build_live_features(ship, asof, snap_dt, data)

    if req.custom_features:
        feature_dict.update(req.custom_features)

    row_dict = {"shipment_id": req.shipment_id, "snapshot_time": snap_time_str}
    row_dict.update(feature_dict)

    df_in = pd.DataFrame([row_dict])
    risk_res = predictor.predict_delay_risk(df_in).iloc[0]

    return DelayRiskResponse(
        shipment_id=req.shipment_id,
        delay_probability=float(risk_res["delay_probability"]),
        delay_risk=str(risk_res["delay_risk"]),
        model_version=str(risk_res["model_version"]),
        prediction_timestamp=str(risk_res["prediction_timestamp"]),
        data_quality_warnings=warnings,
    )


@router.get("/{shipment_id}")
def get_shipment_predictions(shipment_id: str, data=Depends(get_cached_data), predictor=Depends(get_predictor)):
    eta_res = predict_eta(ETAPredictionRequest(shipment_id=shipment_id), data, predictor)
    risk_res = predict_delay_risk(ETAPredictionRequest(shipment_id=shipment_id), data, predictor)
    return {
        "shipment_id": shipment_id,
        "eta": eta_res,
        "delay_risk": risk_res
    }
