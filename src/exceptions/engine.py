"""Operational Exception Engine — Phase 9 Upgrade
Generates, stores, and updates exceptions across shipments:
1. NO_SCAN_24H
2. ETA_SLIP
3. MISSED_CONNECTION
4. SEVERE_WEATHER_ON_PATH (Context-aware: matches active/upcoming legs with time overlap)
5. QUEUE_OVERLOAD (Context-aware: matches active/upcoming facility within transit window)
6. SLA_BREACH_RISK
7. ROUTE_INCONSISTENCY
8. DELIVERED_STATE_MISMATCH

Features:
- Context-aware spatial & temporal matching for weather and queue events
- Deduplication: enforces unique (shipment_id, exception_type) active exceptions
- Real entity IDs stored in evidence_ids
- Configurable operational thresholds
- Persistent lifecycle statuses: OPEN -> ACKNOWLEDGED -> RESOLVED
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
import pandas as pd

from src.data.loader import load_all_data
from src.exceptions.recommendations import get_recommendation_for_exception

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ANALYTICS_DIR = PROJECT_ROOT / "data" / "analytics"
EXCEPTIONS_CSV = ANALYTICS_DIR / "exceptions.csv"

# Configurable Operational Thresholds
QUEUE_OVERLOAD_THRESHOLD = 0.90
ETA_SLIP_MIN_HOURS = 12.0
NO_SCAN_GAP_HOURS = 24.0
MISSED_CONNECTION_HOURS = 4.0


@dataclass
class OperationalException:
    exception_id: str
    shipment_id: str
    exception_type: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    description: str
    detected_at: str
    evidence_ids: List[str]
    recommended_action: str
    status: str = "OPEN"  # OPEN, ACKNOWLEDGED, RESOLVED

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["evidence_ids"] = ",".join(self.evidence_ids)
        return d


class ExceptionEngine:
    def __init__(self, data: Optional[Dict[str, pd.DataFrame]] = None):
        self.data = data or load_all_data()

    def generate_all_exceptions(self) -> pd.DataFrame:
        """Scan operational data across all 8 exception rules with context-awareness and deduplication."""
        exceptions: List[OperationalException] = []
        seen_keys: Set[Tuple[str, str]] = set()  # (shipment_id, exception_type)
        exc_count = 0

        shipments = self.data["shipments"]
        legs = self.data["shipment_legs"].copy()
        events = self.data["tracking_events"]
        etas = self.data["eta_snapshots"]
        queues = self.data["facility_queues"]
        weather = self.data["weather_forecasts"]
        routes = self.data["route_changes"]

        # Ensure datetime parsing for leg boundaries
        legs["planned_dep_dt"] = pd.to_datetime(legs["planned_departure_at"], utc=True)
        legs["planned_arr_dt"] = pd.to_datetime(legs["planned_arrival_at"], utc=True)
        active_legs = legs[legs["leg_status"].isin(["IN_TRANSIT", "PLANNED"])].copy()
        legs_by_dest = {k: v for k, v in active_legs.groupby("destination_facility_id")}
        legs_by_orig = {k: v for k, v in active_legs.groupby("origin_facility_id")}
        evts_by_ship = {k: v.sort_values("event_time") for k, v in events.groupby("shipment_id")}

        def add_exception(ship_id: str, exc_type: str, severity: str, desc: str, ev_ids: List[str]):
            nonlocal exc_count
            key = (ship_id, exc_type)
            if key in seen_keys:
                return  # Deduplication: only one active exception per (shipment, type)
            seen_keys.add(key)
            exc_count += 1
            rec = get_recommendation_for_exception(exc_type)
            exceptions.append(OperationalException(
                exception_id=f"EXC-{exc_count:05d}",
                shipment_id=ship_id,
                exception_type=exc_type,
                severity=severity,
                description=desc,
                detected_at=datetime.now(timezone.utc).isoformat(),
                evidence_ids=ev_ids,
                recommended_action=rec["recommended_action"]
            ))

        # 1. NO_SCAN_24H: in-transit shipments with >24h gap
        for _, ship in shipments[shipments["current_status"].isin(["IN_TRANSIT", "DELAYED"])].iterrows():
            ship_id = ship["shipment_id"]
            ship_evts = evts_by_ship.get(ship_id, pd.DataFrame())
            if ship_evts.empty:
                add_exception(
                    ship_id=ship_id,
                    exc_type="NO_SCAN_24H",
                    severity="HIGH",
                    desc="Shipment active without any tracking scans recorded since creation",
                    ev_ids=[str(ship["created_at"])]
                )
            else:
                for i in range(len(ship_evts) - 1):
                    t1 = pd.to_datetime(ship_evts.iloc[i]["event_time"], utc=True)
                    t2 = pd.to_datetime(ship_evts.iloc[i + 1]["event_time"], utc=True)
                    gap_h = (t2 - t1).total_seconds() / 3600.0
                    if gap_h > NO_SCAN_GAP_HOURS:
                        add_exception(
                            ship_id=ship_id,
                            exc_type="NO_SCAN_24H",
                            severity="MEDIUM" if gap_h <= 36 else "HIGH",
                            desc=f"Tracking black-out: {gap_h:.1f}h silence between {ship_evts.iloc[i]['event_id']} and {ship_evts.iloc[i+1]['event_id']}",
                            ev_ids=[str(ship_evts.iloc[i]["event_id"]), str(ship_evts.iloc[i + 1]["event_id"])]
                        )
                        break

        # 2. ETA_SLIP: snapshots where predicted > planned by >= ETA_SLIP_MIN_HOURS
        for _, snap in etas[etas["predicted_remaining_hours"] > 0].iterrows():
            plan_del = pd.to_datetime(snap["planned_delivery_at"], utc=True)
            pred_del = pd.to_datetime(snap["predicted_delivery_at"], utc=True)
            slip_hours = (pred_del - plan_del).total_seconds() / 3600.0
            if slip_hours >= ETA_SLIP_MIN_HOURS:
                add_exception(
                    ship_id=snap["shipment_id"],
                    exc_type="ETA_SLIP",
                    severity="HIGH" if slip_hours > 24 else "MEDIUM",
                    desc=f"Predicted ETA slipped by {slip_hours:.1f} hours beyond planned schedule at snapshot {snap['eta_id']}",
                    ev_ids=[str(snap["eta_id"])]
                )

        # 3. MISSED_CONNECTION: leg actual arrival > planned arrival by >= MISSED_CONNECTION_HOURS
        for _, leg in legs[legs["leg_status"] == "COMPLETED"].iterrows():
            if pd.notna(leg["actual_arrival_at"]) and pd.notna(leg["planned_arrival_at"]):
                arr_late = (pd.to_datetime(leg["actual_arrival_at"], utc=True) - pd.to_datetime(leg["planned_arrival_at"], utc=True)).total_seconds() / 3600.0
                if arr_late >= MISSED_CONNECTION_HOURS:
                    add_exception(
                        ship_id=leg["shipment_id"],
                        exc_type="MISSED_CONNECTION",
                        severity="CRITICAL" if arr_late > 12 else "HIGH",
                        desc=f"Leg {leg['leg_id']} arrived {arr_late:.1f} hours late, risking downstream connection",
                        ev_ids=[str(leg["leg_id"])]
                    )

        # 4. SEVERE_WEATHER_ON_PATH (Context-aware: matches active/upcoming legs with time overlap)
        severe_wf = weather[weather["severity"].isin(["SEVERE", "EXTREME"])].copy()
        if not severe_wf.empty:
            severe_wf["valid_from_dt"] = pd.to_datetime(severe_wf["valid_from"], utc=True)
            severe_wf["valid_to_dt"] = pd.to_datetime(severe_wf["valid_to"], utc=True)

            for _, wf in severe_wf.iterrows():
                fac_id = wf["facility_id"]
                dest_l = legs_by_dest.get(fac_id, pd.DataFrame())
                orig_l = legs_by_orig.get(fac_id, pd.DataFrame())
                fac_legs = pd.concat([dest_l, orig_l]).drop_duplicates(subset=["leg_id"]) if (not dest_l.empty or not orig_l.empty) else pd.DataFrame()
                if not fac_legs.empty:
                    matching = fac_legs[
                        (fac_legs["planned_dep_dt"] <= wf["valid_to_dt"]) &
                        (fac_legs["planned_arr_dt"] >= wf["valid_from_dt"])
                    ]
                    for _, l in matching.iterrows():
                        add_exception(
                            ship_id=l["shipment_id"],
                            exc_type="SEVERE_WEATHER_ON_PATH",
                            severity="HIGH",
                            desc=f"Severe weather alert ({wf['weather_type']}, wind {wf['wind_speed_kmh']} km/h) at {fac_id} during leg {l['leg_id']}",
                            ev_ids=[str(wf["forecast_id"]), str(l["leg_id"])]
                        )

        # 5. QUEUE_OVERLOAD (Context-aware: matches active/upcoming facility within leg window)
        heavy_q = queues[queues["utilization"] >= QUEUE_OVERLOAD_THRESHOLD].copy()
        if not heavy_q.empty:
            heavy_q["obs_dt"] = pd.to_datetime(heavy_q["observed_at"], utc=True)
            for _, q in heavy_q.iterrows():
                fac_id = q["facility_id"]
                q_time = q["obs_dt"]
                dest_legs = legs_by_dest.get(fac_id, pd.DataFrame())
                if not dest_legs.empty:
                    matching = dest_legs[
                        dest_legs["planned_arr_dt"].between(q_time - pd.Timedelta(hours=24), q_time + pd.Timedelta(hours=24))
                    ]
                    for _, l in matching.iterrows():
                        add_exception(
                            ship_id=l["shipment_id"],
                            exc_type="QUEUE_OVERLOAD",
                            severity="HIGH",
                            desc=f"Facility {fac_id} queue overload: utilization={q['utilization']:.1%}, wait={q['avg_waiting_time_minutes']}min near arrival of leg {l['leg_id']}",
                            ev_ids=[str(q["queue_id"]), str(l["leg_id"])]
                        )

        # 6. ROUTE_INCONSISTENCY (from route changes)
        for _, rc in routes.iterrows():
            add_exception(
                ship_id=rc["shipment_id"],
                exc_type="ROUTE_INCONSISTENCY",
                severity="MEDIUM",
                desc=f"Route modification recorded: {rc['change_type']} (impact: +{rc['impact_hours']}h)",
                ev_ids=[str(rc["change_id"])]
            )

        # 7. DELIVERED_STATE_MISMATCH (from anomaly detector)
        delivered_evts = events[events["event_type"] == "DELIVERED"]
        mismatch_ships = shipments[
            (shipments["current_status"] == "IN_TRANSIT") &
            (shipments["shipment_id"].isin(delivered_evts["shipment_id"]) | shipments["actual_delivery_at"].notna())
        ]
        for _, s in mismatch_ships.iterrows():
            add_exception(
                ship_id=s["shipment_id"],
                exc_type="DELIVERED_STATE_MISMATCH",
                severity="HIGH",
                desc=f"Shipment {s['shipment_id']} marked IN_TRANSIT despite confirmed delivery event or timestamp",
                ev_ids=[str(s["shipment_id"])]
            )

        # 8. SLA_BREACH_RISK: shipments flagged DELAYED
        for _, s in shipments[shipments["current_status"] == "DELAYED"].iterrows():
            add_exception(
                ship_id=s["shipment_id"],
                exc_type="SLA_BREACH_RISK",
                severity="CRITICAL",
                desc=f"Shipment active in DELAYED state exceeding promised transit SLA ({s['sla_hours']}h)",
                ev_ids=[str(s["shipment_id"])]
            )

        df_exc = pd.DataFrame([e.to_dict() for e in exceptions])
        ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
        df_exc.to_csv(EXCEPTIONS_CSV, index=False)
        print(f"Generated {len(df_exc)} operational exceptions saved to {EXCEPTIONS_CSV}")
        return df_exc

    def update_exception_status(self, exception_id: str, new_status: str) -> Optional[Dict[str, Any]]:
        """Update exception status (OPEN -> ACKNOWLEDGED -> RESOLVED)."""
        if not EXCEPTIONS_CSV.exists():
            self.generate_all_exceptions()

        df = pd.read_csv(EXCEPTIONS_CSV)
        idx = df[df["exception_id"] == exception_id].index
        if len(idx) == 0:
            return None

        df.loc[idx[0], "status"] = new_status
        df.to_csv(EXCEPTIONS_CSV, index=False)
        return df.loc[idx[0]].to_dict()


if __name__ == "__main__":
    engine = ExceptionEngine()
    df = engine.generate_all_exceptions()
    print("\nExceptions generated by type:")
    print(df["exception_type"].value_counts())
