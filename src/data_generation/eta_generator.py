"""ETA Estimates Generation Module
Generates ETAEstimate snapshots at multiple intervals throughout the shipment lifecycle.
Provides:
- ETA ID: ETA-SHP-2026-000001-YYYYMMDDHHMMSS
- Prediction timestamp, P50 ETA, P90 ETA
- Delay probability & confidence score
- Contributing weather and queue IDs
- Prediction explanation
- Full backwards compatibility with legacy eta_snapshots columns
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any
import numpy as np
import pandas as pd

from src.data.id_generator import format_eta_id


def ts(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_eta_estimates(
    shipments_df: pd.DataFrame,
    tracking_events_df: pd.DataFrame,
    weather_df: pd.DataFrame,
    queues_df: pd.DataFrame,
    rng: np.random.Generator,
    snapshots_per_shipment: int = 5,
) -> pd.DataFrame:
    """Generate chronological ETA snapshots respecting as-of knowledge at each timestamp."""
    estimates: List[Dict[str, Any]] = []

    # Pre-parse tracking events ingested_at once
    events_df = tracking_events_df.copy()
    if not events_df.empty and "ingested_at" in events_df.columns:
        events_df["_ingested_dt"] = pd.to_datetime(events_df["ingested_at"], utc=True)
        events_grouped = dict(tuple(events_df.groupby("shipment_id")))
    else:
        events_grouped = {}

    # Pre-map weather & queue IDs by facility
    weather_by_fac: Dict[str, List[str]] = {}
    if not weather_df.empty and "facility_id" in weather_df.columns:
        for fac_id, group in weather_df.groupby("facility_id"):
            weather_by_fac[fac_id] = group["weather_id"].head(1).tolist()

    queue_by_fac: Dict[str, List[str]] = {}
    if not queues_df.empty and "facility_id" in queues_df.columns:
        for fac_id, group in queues_df.groupby("facility_id"):
            queue_by_fac[fac_id] = group["queue_id"].head(1).tolist()

    for ship in shipments_df.itertuples():
        ship_id = ship.shipment_id
        status = ship.current_status
        if status == "CANCELLED":
            continue

        created_dt = datetime.strptime(ship.created_at, "%Y-%m-%dT%H:%M:%SZ")
        planned_del_dt = datetime.strptime(ship.planned_delivery_at, "%Y-%m-%dT%H:%M:%SZ")
        actual_del_dt = datetime.strptime(ship.actual_delivery_at, "%Y-%m-%dT%H:%M:%SZ") if ship.actual_delivery_at else planned_del_dt
        transit_span = (actual_del_dt - created_dt).total_seconds() / 3600.0

        if transit_span <= 0:
            transit_span = ship.planned_transit_hours

        # Generate 3 to 6 snapshot intervals throughout the lifecycle
        n_snaps = min(snapshots_per_shipment, max(2, int(transit_span // 8)))
        interval_hours = transit_span / (n_snaps + 1)

        ship_events = events_grouped.get(ship_id)

        for s_idx in range(1, n_snaps + 1):
            snap_time = created_dt + timedelta(hours=interval_hours * s_idx)
            snap_time_utc = pd.Timestamp(snap_time, tz="UTC")
            
            # Events known at this snapshot (ingested_at <= snap_time)
            if ship_events is not None and not ship_events.empty:
                known_events = ship_events[ship_events["_ingested_dt"] <= snap_time_utc]
                source_event_ids = known_events["event_id"].tail(3).tolist()
                max_ingested = str(known_events["ingested_at"].max()) if not known_events.empty else ts(snap_time)
            else:
                source_event_ids = []
                max_ingested = ts(snap_time)

            remaining_span = max(0.5, (planned_del_dt - snap_time).total_seconds() / 3600.0)
            
            # Estimate with slight jitter / noise
            if ship.is_delayed:
                jitter = float(rng.uniform(1.0, 8.0))
                predicted_rem = remaining_span + jitter
                delay_prob = round(float(rng.uniform(0.60, 0.95)), 3)
            else:
                jitter = float(rng.uniform(-2.0, 1.5))
                predicted_rem = max(0.5, remaining_span + jitter)
                delay_prob = round(float(rng.uniform(0.05, 0.35)), 3)

            pred_arr = snap_time + timedelta(hours=predicted_rem)
            p50_eta = pred_arr
            p90_eta = pred_arr + timedelta(hours=predicted_rem * 0.20)
            conf_score = round(float(rng.uniform(0.72, 0.98)), 3)

            # Sample contributing weather & queue IDs
            weather_ids = weather_by_fac.get(ship.origin_facility_id, [])
            queue_ids = queue_by_fac.get(ship.origin_facility_id, [])

            explanation = (
                f"P50 ETA of {predicted_rem:.1f}h based on {len(source_event_ids)} tracking scans, "
                f"carrier {ship.carrier_id} reliability ({conf_score:.1%}), and "
                f"{'elevated delay risk (' + str(round(delay_prob*100)) + '%)' if delay_prob > 0.5 else 'nominal routing flow'}."
            )

            eta_id = format_eta_id(ship_id, snap_time)

            estimates.append({
                # Standard Master Schema
                "eta_id": eta_id,
                "shipment_id": ship_id,
                "prediction_timestamp": ts(snap_time),
                "predicted_arrival_timestamp": ts(pred_arr),
                "p50_eta": ts(p50_eta),
                "p90_eta": ts(p90_eta),
                "estimated_remaining_duration": round(predicted_rem, 2),
                "delay_probability": delay_prob,
                "confidence_score": conf_score,
                "model_version": "v2.0-HistGBT",
                "feature_cutoff_timestamp": ts(snap_time),
                "source_event_ids": ",".join(source_event_ids),
                "contributing_weather_event_ids": ",".join(weather_ids),
                "contributing_queue_observation_ids": ",".join(queue_ids),
                "explanation": explanation,
                # Compatibility Aliases for existing pipelines & dashboard
                "snapshot_time": ts(snap_time),
                "planned_delivery_at": ts(planned_del_dt),
                "predicted_delivery_at": ts(pred_arr),
                "predicted_remaining_hours": round(predicted_rem, 2),
                "prediction_method": "ML_HistGradientBoosting",
                "data_cutoff_at": ts(snap_time),
                "max_ingested_at_used": max_ingested,
            })

    return pd.DataFrame(estimates)

