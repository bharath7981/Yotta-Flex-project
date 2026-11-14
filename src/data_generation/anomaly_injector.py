"""Anomaly Injection & Ground Truth Generation Module
Injects the 4 Mandatory Anomaly Families:
1. EVENT_INGESTION_CONFUSION (ingested_at < event_time)
2. IMPOSSIBLE_ROUTE_ORDER (leg continuity break)
3. FUTURE_DATA_LEAKAGE (max_ingested_at_used > snapshot_time)
4. DELIVERED_BUT_IN_TRANSIT (status mismatch)
Plus secondary operational anomalies (Duplicates, Delayed Ingestion).

Exports:
- data/ground_truth.csv
- data/ground_truth.json
"""

import json
from datetime import datetime, timedelta
from typing import Tuple, List, Dict, Any
import numpy as np
import pandas as pd

from src.data.id_generator import format_anomaly_id


def ts(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def inject_anomalies_and_generate_ground_truth(
    shipments_df: pd.DataFrame,
    legs_df: pd.DataFrame,
    events_df: pd.DataFrame,
    eta_df: pd.DataFrame,
    facilities_df: pd.DataFrame,
    rng: np.random.Generator,
    scale_factor: float = 1.0,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Inject controlled anomalies into operational datasets and produce isolated ground-truth files."""
    shipments = shipments_df.copy()
    legs = legs_df.copy()
    events = events_df.copy()
    etas = eta_df.copy()
    ground_truth: List[Dict[str, Any]] = []

    anom_seq = 1
    fac_ids = facilities_df["facility_id"].tolist()

    # 1. Anomaly 1: EVENT_INGESTION_CONFUSION (20 for starter, scaled for full)
    n_a1 = max(10, int(20 * scale_factor))
    eligible_events = events[events["event_type"].isin(["DEPARTURE", "ARRIVAL"])].index
    if len(eligible_events) >= n_a1:
        chosen_indices = rng.choice(eligible_events, size=n_a1, replace=False)
        for idx in chosen_indices:
            evt = events.loc[idx]
            evt_time = datetime.strptime(evt["event_time"], "%Y-%m-%dT%H:%M:%SZ")
            # Ingestion occurs BEFORE event time (clock skew / confused feed)
            confused_ingest = evt_time - timedelta(minutes=float(rng.uniform(15, 180)))
            events.loc[idx, "ingested_at"] = ts(confused_ingest)

            anom_id = format_anomaly_id(anom_seq)
            ground_truth.append({
                "anomaly_id": anom_id,
                "entity_type": "tracking_event",
                "entity_id": evt["event_id"],
                "shipment_id": evt["shipment_id"],
                "issue_type": "EVENT_INGESTION_CONFUSION",
                "ground_truth_label": "EVENT_INGESTION_CONFUSION",
                "expected_detection": "FLAG_TELEMETRY_CLOCK_SKEW",
                "expected_decision": "USE_INGESTED_FOR_AVAILABILITY_EVENT_FOR_SEQUENCE",
                "severity": "MEDIUM",
                "evidence_event_ids": evt["event_id"],
                "injection_description": f"Ingestion timestamp ({ts(confused_ingest)}) precedes physical event time ({evt['event_time']}).",
            })
            anom_seq += 1

    # 2. Anomaly 2: IMPOSSIBLE_ROUTE_ORDER (15 for starter, scaled for full)
    n_a2 = max(8, int(15 * scale_factor))
    multi_leg_ships = legs.groupby("shipment_id").filter(lambda g: len(g) >= 2)["shipment_id"].unique()
    if len(multi_leg_ships) >= n_a2:
        chosen_ships = rng.choice(multi_leg_ships, size=n_a2, replace=False)
        for s_id in chosen_ships:
            ship_legs_idx = legs[legs["shipment_id"] == s_id].sort_values("leg_sequence").index
            if len(ship_legs_idx) >= 2:
                # Corrupt intermediate destination of leg 1
                curr_fac = legs.loc[ship_legs_idx[0], "destination_facility_id"]
                other_facs = [f for f in fac_ids if f != curr_fac and f != legs.loc[ship_legs_idx[1], "origin_facility_id"]]
                if other_facs:
                    corrupted_fac = str(rng.choice(other_facs))
                    legs.loc[ship_legs_idx[0], "destination_facility_id"] = corrupted_fac

                    anom_id = format_anomaly_id(anom_seq)
                    ground_truth.append({
                        "anomaly_id": anom_id,
                        "entity_type": "shipment_leg",
                        "entity_id": legs.loc[ship_legs_idx[0], "leg_id"],
                        "shipment_id": s_id,
                        "issue_type": "IMPOSSIBLE_ROUTE_ORDER",
                        "ground_truth_label": "IMPOSSIBLE_ROUTE_ORDER",
                        "expected_detection": "FLAG_TOPOLOGICAL_DISCONTINUITY",
                        "expected_decision": "REROUTE_SHIPMENT_OR_INVESTIGATE_LEG_CHAIN",
                        "severity": "HIGH",
                        "evidence_event_ids": legs.loc[ship_legs_idx[0], "leg_id"],
                        "injection_description": f"Leg 1 dest ({corrupted_fac}) does not match Leg 2 origin ({legs.loc[ship_legs_idx[1], 'origin_facility_id']}).",
                    })
                    anom_seq += 1

    # 3. Anomaly 3: FUTURE_DATA_LEAKAGE (15 for starter, scaled for full)
    n_a3 = max(8, int(15 * scale_factor))
    if len(etas) >= n_a3:
        chosen_eta_indices = rng.choice(etas.index, size=n_a3, replace=False)
        for idx in chosen_eta_indices:
            eta_row = etas.loc[idx]
            snap_time = datetime.strptime(eta_row["snapshot_time"], "%Y-%m-%dT%H:%M:%SZ")
            # Set max_ingested_at_used and data_cutoff_at in the FUTURE of snapshot_time
            future_leak = snap_time + timedelta(hours=float(rng.uniform(6, 48)))
            etas.loc[idx, "max_ingested_at_used"] = ts(future_leak)
            if "data_cutoff_at" in etas.columns:
                etas.loc[idx, "data_cutoff_at"] = ts(future_leak)

            anom_id = format_anomaly_id(anom_seq)
            ground_truth.append({
                "anomaly_id": anom_id,
                "entity_type": "eta_snapshot",
                "entity_id": eta_row["eta_id"],
                "shipment_id": eta_row["shipment_id"],
                "issue_type": "FUTURE_DATA_LEAKAGE",
                "ground_truth_label": "FUTURE_DATA_LEAKAGE",
                "expected_detection": "FLAG_FEATURE_LEAKAGE_VIOLATION",
                "expected_decision": "EXCLUDE_FROM_TRAINING_FEATURE_STORE",
                "severity": "CRITICAL",
                "evidence_event_ids": eta_row["eta_id"],
                "injection_description": f"Snapshot uses feature cutoff ({ts(future_leak)}) after snapshot time ({eta_row['snapshot_time']}).",
            })
            anom_seq += 1

    # 4. Anomaly 4: DELIVERED_BUT_IN_TRANSIT (10 for starter, scaled for full)
    n_a4 = max(5, int(10 * scale_factor))
    delivered_ships = shipments[shipments["current_status"] == "DELIVERED"]["shipment_id"].tolist()
    if len(delivered_ships) >= n_a4:
        chosen_deliv_ships = rng.choice(delivered_ships, size=n_a4, replace=False)
        for s_id in chosen_deliv_ships:
            # Change shipment status back to IN_TRANSIT while DELIVERED tracking scan remains
            ship_idx = shipments[shipments["shipment_id"] == s_id].index[0]
            shipments.loc[ship_idx, "current_status"] = "IN_TRANSIT"

            anom_id = format_anomaly_id(anom_seq)
            ground_truth.append({
                "anomaly_id": anom_id,
                "entity_type": "shipment",
                "entity_id": s_id,
                "shipment_id": s_id,
                "issue_type": "DELIVERED_BUT_IN_TRANSIT",
                "ground_truth_label": "DELIVERED_BUT_IN_TRANSIT",
                "expected_detection": "FLAG_LIFECYCLE_STATUS_CONFLICT",
                "expected_decision": "RECONCILE_STATUS_TO_DELIVERED",
                "severity": "HIGH",
                "evidence_event_ids": s_id,
                "injection_description": "Shipment current_status is IN_TRANSIT despite confirmed delivery scan.",
            })
            anom_seq += 1

    gt_df = pd.DataFrame(ground_truth)
    return shipments, legs, events, etas, gt_df

