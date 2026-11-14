"""Anomaly Detection Module
Implements robust detection rules across the four core operational anomaly categories:
1. Event Ingestion-Time Confusion (ingested_at < event_time)
2. Impossible Route Order (facility discontinuity between consecutive non-cancelled legs)
3. Future-Data Leakage in ETA Snapshots (max_ingested_at_used > snapshot_time OR data_cutoff_at > snapshot_time)
4. Delivered But In-Transit State Mismatch (shipment marked IN_TRANSIT with terminal DELIVERED event or actual_delivery_at populated)
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
import pandas as pd

from src.data.loader import load_all_data

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ANALYTICS_DIR = PROJECT_ROOT / "data" / "analytics"


class AnomalyDetector:
    def __init__(self, data: Optional[Dict[str, pd.DataFrame]] = None):
        self.data = data or load_all_data()

    def detect_ingestion_confusion(self) -> List[Dict[str, Any]]:
        """Category A: Identify tracking events where ingestion precedes actual occurrence time."""
        anomalies = []
        events = self.data["tracking_events"].copy()
        events["ingested_at_dt"] = pd.to_datetime(events["ingested_at"], utc=True)
        events["event_time_dt"] = pd.to_datetime(events["event_time"], utc=True)

        confused = events[events["ingested_at_dt"] < events["event_time_dt"]].copy()

        for _, row in confused.iterrows():
            anomalies.append({
                "anomaly_id": f"DET-A-{row['event_id']}",
                "entity_type": "tracking_event",
                "entity_id": row["event_id"],
                "shipment_id": row["shipment_id"],
                "issue_type": "EVENT_INGESTION_CONFUSION",
                "severity": "MEDIUM",
                "detection_rule": "ingested_at < event_time",
                "evidence": f"Event time={row['event_time']} but ingested_at={row['ingested_at']}",
                "detected_at": datetime.now(timezone.utc).isoformat()
            })
        return anomalies

    def detect_impossible_route(self) -> List[Dict[str, Any]]:
        """Category B: Broken facility continuity across sequential shipment legs.
        Handles edge cases: single-leg shipments (no continuity requirement),
        and excludes CANCELLED legs from chain continuity.
        """
        anomalies = []
        legs = self.data["shipment_legs"]

        for ship_id, ship_legs in legs.groupby("shipment_id"):
            # Exclude cancelled legs if column present
            active_legs = ship_legs
            if "leg_status" in ship_legs.columns:
                active_legs = ship_legs[ship_legs["leg_status"] != "CANCELLED"]

            if len(active_legs) <= 1:
                continue

            sorted_legs = active_legs.sort_values("leg_sequence").reset_index(drop=True)
            for i in range(len(sorted_legs) - 1):
                curr_dest = sorted_legs.loc[i, "destination_facility_id"]
                next_orig = sorted_legs.loc[i + 1, "origin_facility_id"]
                if curr_dest != next_orig:
                    anomalies.append({
                        "anomaly_id": f"DET-B-{sorted_legs.loc[i, 'leg_id']}",
                        "entity_type": "shipment_leg",
                        "entity_id": sorted_legs.loc[i, "leg_id"],
                        "shipment_id": ship_id,
                        "issue_type": "IMPOSSIBLE_ROUTE_ORDER",
                        "severity": "HIGH",
                        "detection_rule": "leg[i].destination_facility != leg[i+1].origin_facility",
                        "evidence": f"Leg {sorted_legs.loc[i, 'leg_sequence']} dest ({curr_dest}) != Leg {sorted_legs.loc[i+1, 'leg_sequence']} origin ({next_orig})",
                        "detected_at": datetime.now(timezone.utc).isoformat()
                    })
        return anomalies

    def detect_future_leakage(self) -> List[Dict[str, Any]]:
        """Category C: Identify ETA records whose data cutoff or ingestion exceeds snapshot time."""
        anomalies = []
        etas = self.data["eta_snapshots"].copy()
        etas["snap_dt"] = pd.to_datetime(etas["snapshot_time"], utc=True)
        etas["max_ing_dt"] = pd.to_datetime(etas["max_ingested_at_used"], utc=True)

        # Check both max_ingested_at_used and data_cutoff_at
        leak_mask = etas["max_ing_dt"] > etas["snap_dt"]
        if "data_cutoff_at" in etas.columns:
            etas["cutoff_dt"] = pd.to_datetime(etas["data_cutoff_at"], utc=True)
            leak_mask = leak_mask | (etas["cutoff_dt"] > etas["snap_dt"])

        leaks = etas[leak_mask].copy()

        for _, row in leaks.iterrows():
            anomalies.append({
                "anomaly_id": f"DET-C-{row['eta_id']}",
                "entity_type": "eta_snapshot",
                "entity_id": row["eta_id"],
                "shipment_id": row["shipment_id"],
                "issue_type": "FUTURE_DATA_LEAKAGE",
                "severity": "CRITICAL",
                "detection_rule": "max_ingested_at_used > snapshot_time OR data_cutoff_at > snapshot_time",
                "evidence": f"Snapshot={row['snapshot_time']} but max_ingested_at_used={row['max_ingested_at_used']}",
                "detected_at": datetime.now(timezone.utc).isoformat()
            })
        return anomalies

    def detect_delivered_but_intransit(self) -> List[Dict[str, Any]]:
        """Category D: Shipments marked IN_TRANSIT despite having terminal delivery scans or actual delivery timestamp."""
        anomalies = []
        shipments = self.data["shipments"]
        events = self.data["tracking_events"]

        delivered_events = events[events["event_type"] == "DELIVERED"]
        delivered_ship_ids = set(delivered_events["shipment_id"])

        # Condition 1: status is IN_TRANSIT but has confirmed DELIVERED event
        # Condition 2: status is IN_TRANSIT but actual_delivery_at is populated
        mismatches = shipments[
            (shipments["current_status"] == "IN_TRANSIT") &
            (shipments["shipment_id"].isin(delivered_ship_ids) | shipments["actual_delivery_at"].notna())
        ].copy()

        for _, row in mismatches.iterrows():
            reason = "confirmed DELIVERED event" if row["shipment_id"] in delivered_ship_ids else "actual_delivery_at populated"
            anomalies.append({
                "anomaly_id": f"DET-D-{row['shipment_id']}",
                "entity_type": "shipment",
                "entity_id": row["shipment_id"],
                "shipment_id": row["shipment_id"],
                "issue_type": "DELIVERED_BUT_IN_TRANSIT",
                "severity": "HIGH",
                "detection_rule": "status == IN_TRANSIT and (exists(event_type == DELIVERED) or actual_delivery_at != null)",
                "evidence": f"Shipment status is IN_TRANSIT but has {reason}",
                "detected_at": datetime.now(timezone.utc).isoformat()
            })
        return anomalies

    def run_all_detectors(self) -> pd.DataFrame:
        """Run all 4 anomaly detection categories and persist results."""
        all_anomalies = []
        all_anomalies.extend(self.detect_ingestion_confusion())
        all_anomalies.extend(self.detect_impossible_route())
        all_anomalies.extend(self.detect_future_leakage())
        all_anomalies.extend(self.detect_delivered_but_intransit())

        df_anom = pd.DataFrame(all_anomalies)
        ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = ANALYTICS_DIR / "detected_anomalies.csv"
        df_anom.to_csv(out_path, index=False)
        print(f"Detected {len(df_anom)} operational anomalies saved to {out_path}")
        return df_anom


if __name__ == "__main__":
    detector = AnomalyDetector()
    df = detector.run_all_detectors()
    print(df["issue_type"].value_counts())
