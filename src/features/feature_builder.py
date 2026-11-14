"""Point-in-Time Feature Engineering Pipeline
Constructs feature records strictly respecting information available at each ETA snapshot.
Does not introduce future target leakage into feature sets.

Changes from v1.0 (Phase 2-4 upgrade):
  - Carrier features now computed from COMPLETED past shipments (temporal, Bayesian-smoothed)
    rather than pulled from static carriers.csv random constants.
  - Missing facility queue / weather data represented as NaN (not hardcoded defaults).
  - SLA target (`is_sla_breached`) added alongside legacy `is_delayed_target`.
  - `max_source_ingested_at` field added for leakage auditing.
  - `evidence_event_ids` field added (comma-separated event IDs used for progress features).
  - Events sorted by ingested_at (not event_time) to prevent anomaly-A ordering issues.
"""

import os
from datetime import timedelta
from typing import Dict, List, Any
import numpy as np
import pandas as pd
from src.data.loader import load_all_data
from src.data.sla import get_sla_rule, get_promised_delivery
from src.features.asof import AsOfView


def build_features_for_snapshots(data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Extract features for every ETA snapshot using point-in-time rules."""
    asof = AsOfView(data)
    snapshots = data["eta_snapshots"].copy()
    shipments = data["shipments"].copy()

    # Pre-parse timestamps on shipments
    shipments["_created_dt"] = pd.to_datetime(shipments["created_at"], utc=True)
    shipments["_planned_del_dt"] = pd.to_datetime(shipments["planned_delivery_at"], utc=True)
    shipments["_actual_del_dt"] = pd.to_datetime(shipments["actual_delivery_at"], utc=True, errors="coerce")
    ship_dict = shipments.set_index("shipment_id").to_dict(orient="index")

    # Pre-parse timestamps on snapshots
    snapshots["snap_dt"] = pd.to_datetime(snapshots["snapshot_time"], utc=True)

    feature_rows: List[Dict[str, Any]] = []

    for snap in snapshots.itertuples():
        ship_id = snap.shipment_id
        ship = ship_dict.get(ship_id)
        if ship is None:
            continue

        snap_time = snap.snap_dt
        created_at = ship["_created_dt"]
        planned_delivery_at = ship["_planned_del_dt"]
        service_level = str(ship["service_level"])
        carrier_id = str(ship["carrier_id"])

        # ── 1. Shipment Attributes ───────────────────────────────────────
        shipment_age_hours = max(0.0, (snap_time - created_at).total_seconds() / 3600.0)
        planned_transit_hours = float(ship["planned_transit_hours"])
        planned_remaining_hours = max(0.0, (planned_delivery_at - snap_time).total_seconds() / 3600.0)
        distance_km = float(ship["distance_km"])
        weight_kg = float(ship["weight_kg"])
        num_legs = int(ship["num_legs"])

        # ── 2. Progress Features (ingested_at-ordered events) ────────────
        events = asof.get_tracking_events(ship_id, snap_time)  # sorted by ingested_at
        num_events = len(events)
        evidence_event_ids = []
        ingested_ats = []

        if num_events > 0:
            last_event = events.iloc[-1]
            last_event_time = pd.to_datetime(last_event["event_time"], utc=True)
            hours_since_last_event = max(0.0, (snap_time - last_event_time).total_seconds() / 3600.0)
            current_facility_id = last_event["facility_id"]
            evidence_event_ids = events["event_id"].tolist()
            if "_ingested_dt" in events.columns:
                ingested_ats.append(events["_ingested_dt"].max())
            else:
                ingested_ats.append(pd.to_datetime(events["ingested_at"].max(), utc=True))
        else:
            hours_since_last_event = shipment_age_hours
            current_facility_id = ship["origin_facility_id"]

        # Count arrival events (progress proxy)
        arrival_events = events[events["event_type"] == "ARRIVAL"] if num_events > 0 else pd.DataFrame()
        completed_legs = min(len(arrival_events), num_legs)
        remaining_legs = max(0, num_legs - completed_legs)
        progress_pct = round(completed_legs / max(num_legs, 1), 3)

        # Expected scans based on age vs transit time
        expected_scans = int((shipment_age_hours / max(planned_transit_hours, 1.0)) * (num_legs * 2))
        missing_expected_scans = max(0, expected_scans - num_events)

        # ── 3. Carrier Attributes (Temporal — from past completed shipments) ─
        carrier_perf = asof.get_carrier_performance(carrier_id, snap_time, exclude_shipment_id=ship_id)
        carrier_on_time_rate = carrier_perf["carrier_on_time_rate"]
        carrier_avg_delay = carrier_perf["carrier_avg_delay_hours"]
        carrier_reliability = carrier_perf["carrier_reliability"]
        carrier_sample_size = carrier_perf["carrier_sample_size"]

        # ── 4. Facility Attributes (NaN if not available) ────────────────
        q = asof.get_facility_queue(current_facility_id, snap_time)
        if q is not None:
            current_queue_length = float(q["queue_length"])
            avg_wait_minutes = float(q["avg_waiting_time_minutes"])
            facility_utilization = float(q["utilization"])
            facility_disrupted = int(q["is_disrupted"])
            ingested_ats.append(q["_ingested_dt"] if "_ingested_dt" in q else pd.to_datetime(q["ingested_at"], utc=True))
        else:
            current_queue_length = np.nan
            avg_wait_minutes = np.nan
            facility_utilization = np.nan
            facility_disrupted = 0

        # ── 5. Weather Attributes (NaN if not available) ─────────────────
        wf = asof.get_weather_forecast(current_facility_id, snap_time)
        if wf is not None:
            weather_severity = str(wf["severity"])
            precipitation_mm = float(wf["precipitation_mm"])
            wind_speed_kmh = float(wf["wind_speed_kmh"])
            weather_disruptive = int(wf["is_disruptive"])
            ingested_ats.append(wf["_issued_dt"] if "_issued_dt" in wf else pd.to_datetime(wf["issued_at"], utc=True))
        else:
            weather_severity = "NONE"
            precipitation_mm = np.nan
            wind_speed_kmh = np.nan
            weather_disruptive = 0

        # ── 6. Route Features ────────────────────────────────────────────
        rc = asof.get_route_changes(ship_id, snap_time)
        route_changes_count = len(rc)
        if len(rc) > 0 and "_recorded_dt" in rc.columns:
            ingested_ats.append(rc["_recorded_dt"].max())

        # ── 7. Max ingestion timestamp (leakage audit field) ─────────────
        max_source_ingested_at = (
            max(ingested_ats).isoformat() if ingested_ats else None
        )

        # ── 8. Ground-truth targets ──────────────────────────────────────
        actual_remaining_hours = None
        is_delayed_target = None
        is_sla_breached_target = None

        actual_del = ship["_actual_del_dt"]
        if pd.notna(actual_del):
            diff_hours = (actual_del - snap_time).total_seconds() / 3600.0
            if diff_hours >= 0.0:
                actual_remaining_hours = diff_hours
                # Legacy: vs planned_delivery_at (no grace)
                is_delayed_target = int(actual_del > planned_delivery_at)
                # Authoritative: vs promised_delivery_at + grace
                promised_delivery = get_promised_delivery(created_at, service_level)
                rule = get_sla_rule(service_level)
                deadline = promised_delivery + timedelta(hours=rule["grace_hours"])
                is_sla_breached_target = int(actual_del > deadline)

        row = {
            "eta_id": getattr(snap, "eta_id", f"ETA-{ship_id}"),
            "shipment_id": ship_id,
            "snapshot_time": snap_time.isoformat(),
            "feature_version": "v2.0",
            # Shipment features
            "service_level": service_level,
            "shipment_age_hours": round(shipment_age_hours, 2),
            "num_legs": num_legs,
            "weight_kg": weight_kg,
            "distance_km": distance_km,
            "planned_transit_hours": planned_transit_hours,
            "planned_remaining_hours": round(planned_remaining_hours, 2),
            # Progress features
            "completed_legs": completed_legs,
            "remaining_legs": remaining_legs,
            "progress_pct": progress_pct,
            "hours_since_last_event": round(hours_since_last_event, 2),
            "missing_expected_scans": missing_expected_scans,
            # Carrier features (temporal, Bayesian-smoothed)
            "carrier_on_time_rate": carrier_on_time_rate,
            "carrier_avg_delay": carrier_avg_delay,
            "carrier_reliability": carrier_reliability,
            "carrier_sample_size": carrier_sample_size,
            # Facility features (NaN when unavailable)
            "current_queue_length": current_queue_length,
            "avg_wait_minutes": avg_wait_minutes,
            "facility_utilization": facility_utilization,
            "facility_disrupted": facility_disrupted,
            # Weather features (NaN when unavailable)
            "weather_severity": weather_severity,
            "precipitation_mm": precipitation_mm,
            "wind_speed_kmh": wind_speed_kmh,
            "weather_disruptive": weather_disruptive,
            # Route features
            "route_changes_count": route_changes_count,
            # Leakage audit fields
            "max_source_ingested_at": max_source_ingested_at,
            "evidence_event_ids": ",".join(str(e) for e in evidence_event_ids),
            # Targets
            "actual_remaining_hours": actual_remaining_hours,
            "is_delayed_target": is_delayed_target,          # legacy (vs planned)
            "is_sla_breached_target": is_sla_breached_target, # authoritative (vs SLA+grace)
        }
        feature_rows.append(row)

    df_features = pd.DataFrame(feature_rows)
    return df_features


def build_and_save_features():
    print("Loading data...")
    data = load_all_data()

    print("Extracting point-in-time features (v2.0)...")
    df_features = build_features_for_snapshots(data)

    out_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data", "processed"
    )
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "features.csv")
    df_features.to_csv(out_path, index=False)
    print(f"Features saved successfully to {out_path} ({len(df_features)} rows)")
    return df_features


if __name__ == "__main__":
    build_and_save_features()
