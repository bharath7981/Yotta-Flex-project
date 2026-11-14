"""Shipment & Legs Generation Module
Generates:
1. Shipment
2. ShipmentLeg
3. ShipmentStatusHistory
4. RouteChangeHistory
5. ShipmentDelayReason (Bridge table)
"""

from datetime import datetime, timedelta
from typing import Tuple, Dict, List, Any
import numpy as np
import pandas as pd

from src.data.id_generator import (
    format_shipment_id,
    format_leg_id,
    format_route_id,
    format_status_history_id,
    format_route_change_id,
    format_shipment_delay_reason_id,
)

BASE_DATE = datetime(2026, 6, 1, 0, 0, 0)
END_DATE = datetime(2026, 10, 31, 23, 59, 59)


def ts(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_shipments_and_legs(
    carriers_df: pd.DataFrame,
    facilities_df: pd.DataFrame,
    routes_df: pd.DataFrame,
    service_levels_df: pd.DataFrame,
    delay_reasons_df: pd.DataFrame,
    rng: np.random.Generator,
    n_shipments: int = 500,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generate Shipments, Legs, Status History, Route Changes, Delay Reason associations, and complete Routes."""
    shipments: List[Dict[str, Any]] = []
    legs: List[Dict[str, Any]] = []
    status_histories: List[Dict[str, Any]] = []
    route_changes: List[Dict[str, Any]] = []
    shipment_delay_reasons: List[Dict[str, Any]] = []

    carrier_ids = carriers_df["carrier_id"].tolist()
    carrier_lookup = carriers_df.set_index("carrier_id")
    facility_ids = facilities_df["facility_id"].tolist()
    facility_lookup = facilities_df.set_index("facility_id")
    sl_lookup = service_levels_df.set_index("service_level_id")
    sla_hours_map = dict(zip(service_levels_df["service_level_id"], service_levels_df["promised_transit_hours"]))
    grace_hours_map = dict(zip(service_levels_df["service_level_id"], service_levels_df["grace_period_hours"]))
    delay_reason_ids = delay_reasons_df["reason_id"].tolist()

    # Pre-index routes by (origin, destination) for fast lookup and register any new pairs
    routes_records = routes_df.to_dict(orient="records")
    route_map = {}
    for r in routes_records:
        route_map[(r["origin_facility_id"], r["destination_facility_id"])] = r["route_id"]

    next_route_seq = len(routes_records) + 1

    def get_or_create_route(orig_id: str, dest_id: str) -> str:
        nonlocal next_route_seq
        if (orig_id, dest_id) in route_map:
            return route_map[(orig_id, dest_id)]
        r_id = format_route_id(next_route_seq)
        next_route_seq += 1
        orig = facility_lookup.loc[orig_id]
        dest = facility_lookup.loc[dest_id]
        d_km = round(float(np.sqrt((orig["latitude"] - dest["latitude"])**2 + (orig["longitude"] - dest["longitude"])**2) * 111.0), 1)
        d_km = max(50.0, d_km)
        mode = "AIR" if d_km > 1800 else ("RAIL" if d_km > 800 and rng.random() > 0.5 else "TRUCK")
        speed = 700.0 if mode == "AIR" else (55.0 if mode == "RAIL" else 65.0)
        transit_h = round(d_km / speed, 1)
        new_route = {
            "route_id": r_id,
            "origin_facility_id": orig_id,
            "destination_facility_id": dest_id,
            "standard_transit_hours": transit_h,
            "distance_km": d_km,
            "primary_transport_mode": mode,
            "is_congested": bool(rng.random() < 0.12),
        }
        routes_records.append(new_route)
        route_map[(orig_id, dest_id)] = r_id
        return r_id

    service_levels = ["STANDARD", "EXPRESS", "PRIORITY", "ECONOMY"]
    service_probs = [0.45, 0.30, 0.15, 0.10]
    statuses = ["DELIVERED", "IN_TRANSIT", "DELAYED", "AT_FACILITY", "CANCELLED"]
    status_probs = [0.55, 0.20, 0.12, 0.08, 0.05]

    total_window_seconds = int((END_DATE - BASE_DATE).total_seconds())

    ssh_seq = 1
    rch_seq = 1
    sdr_seq = 1

    for i in range(1, n_shipments + 1):
        shipment_id = format_shipment_id(i)
        
        # Pick random creation time within simulation window
        offset_sec = int(rng.integers(0, total_window_seconds))
        created_at = BASE_DATE + timedelta(seconds=offset_sec)
        
        service = str(rng.choice(service_levels, p=service_probs))
        carrier_id = str(rng.choice(carrier_ids))
        carrier = carrier_lookup.loc[carrier_id]

        # Select distinct origin and destination
        fac_pair = rng.choice(facility_ids, size=2, replace=False)
        origin_id = fac_pair[0]
        dest_id = fac_pair[1]
        origin_fac = facility_lookup.loc[origin_id]
        dest_fac = facility_lookup.loc[dest_id]

        # Calculate distance
        dist_km = round(float(np.sqrt((origin_fac["latitude"] - dest_fac["latitude"])**2 + (origin_fac["longitude"] - dest_fac["longitude"])**2) * 111.0), 1)
        dist_km = max(80.0, dist_km)

        # Planned transit hours derived from SLA window (50% to 85% of SLA)
        sla_promised = sla_hours_map[service]
        grace_h = grace_hours_map[service]
        planned_transit_hours = round(float(sla_promised * rng.uniform(0.50, 0.85)), 1)
        planned_pickup_at = created_at + timedelta(hours=float(rng.uniform(0.5, 3.0)))
        planned_delivery_at = planned_pickup_at + timedelta(hours=planned_transit_hours)
        promised_delivery_at = created_at + timedelta(hours=sla_promised)

        status = str(rng.choice(statuses, p=status_probs))
        priority = "CRITICAL" if service == "PRIORITY" else ("URGENT" if service == "EXPRESS" else "STANDARD")
        weight_kg = round(float(rng.uniform(0.5, 500.0)), 1)

        # Number of legs: mostly 1 to 4 legs
        num_legs = int(rng.choice([1, 2, 3, 4], p=[0.20, 0.45, 0.25, 0.10]))

        # Build intermediate route facilities
        chain = [origin_id]
        if num_legs > 1:
            intermediates = [f for f in facility_ids if f not in [origin_id, dest_id]]
            n_inter = min(num_legs - 1, len(intermediates))
            chosen_inter = rng.choice(intermediates, size=n_inter, replace=False)
            chain.extend(chosen_inter)
        chain.append(dest_id)
        num_legs = len(chain) - 1

        actual_pickup_at = None
        actual_delivery_at = None
        delay_hours = 0.0
        is_delayed = False
        is_sla_breached = None

        if status in ["DELIVERED", "DELAYED"]:
            actual_pickup_at = planned_pickup_at + timedelta(hours=float(rng.uniform(-0.5, 2.0)))
            
            if status == "DELIVERED":
                # Carrier on-time probability determines whether actual misses plan
                is_delay_event = bool(rng.random() > float(carrier["on_time_rate"]))
                if is_delay_event:
                    actual_del_offset = float(rng.uniform(1.0, float(carrier["avg_delay_hours"]) * 1.5))
                    actual_delivery_at = planned_delivery_at + timedelta(hours=actual_del_offset)
                else:
                    actual_delivery_at = planned_delivery_at - timedelta(hours=float(rng.uniform(0.5, 4.0)))

                # Calculate authoritative SLA breach
                sla_deadline = promised_delivery_at + timedelta(hours=grace_h)
                is_sla_breached = int(actual_delivery_at > sla_deadline)
                raw_delay = (actual_delivery_at - planned_delivery_at).total_seconds() / 3600.0
                delay_hours = max(0.0, raw_delay)
                is_delayed = raw_delay > 0.0
            else: # DELAYED
                raw_delay = float(rng.uniform(6.0, 36.0))
                delay_hours = raw_delay
                is_delayed = True
                is_sla_breached = 1

        elif status == "IN_TRANSIT":
            actual_pickup_at = planned_pickup_at + timedelta(hours=float(rng.uniform(-0.5, 2.0)))
            is_delayed = bool(rng.random() < 0.20)
            delay_hours = float(rng.uniform(1.0, 10.0)) if is_delayed else 0.0

        # Primary route reference
        primary_route_id = get_or_create_route(origin_id, dest_id)

        shipments.append({
            "shipment_id": shipment_id,
            "created_at": ts(created_at),
            "carrier_id": carrier_id,
            "service_level": service,
            "origin_facility_id": origin_id,
            "destination_facility_id": dest_id,
            "origin_city": origin_fac["city"],
            "destination_city": dest_fac["city"],
            "weight_kg": weight_kg,
            "distance_km": dist_km,
            "num_legs": num_legs,
            "planned_transit_hours": planned_transit_hours,
            "planned_pickup_at": ts(planned_pickup_at),
            "planned_delivery_at": ts(planned_delivery_at),
            "promised_delivery_at": ts(promised_delivery_at),
            "actual_pickup_at": ts(actual_pickup_at),
            "actual_delivery_at": ts(actual_delivery_at),
            "current_status": status,
            "priority": priority,
            "route_id": primary_route_id,
            "sla_hours": sla_promised,
            "delay_hours": round(delay_hours, 2),
            "is_delayed": is_delayed,
            "is_sla_breached": is_sla_breached,
            "grace_hours": grace_h,
        })

        # Generate shipment legs
        transit_per_leg = planned_transit_hours / num_legs
        current_dep = planned_pickup_at

        for j in range(num_legs):
            leg_seq = j + 1
            leg_id = format_leg_id(shipment_id, leg_seq)
            leg_orig = chain[j]
            leg_dest = chain[j + 1]
            leg_route_id = get_or_create_route(leg_orig, leg_dest)

            leg_arr = current_dep + timedelta(hours=transit_per_leg)
            leg_dist = round(dist_km / num_legs, 1)
            leg_mode = str(carrier["primary_mode"])

            actual_dep = None
            actual_arr = None
            leg_status = "PLANNED"

            if status == "DELIVERED":
                actual_dep = current_dep + timedelta(hours=float(rng.uniform(-0.3, 1.0)))
                actual_arr = leg_arr + timedelta(hours=float(rng.uniform(-0.5, 2.0)))
                leg_status = "COMPLETED"
            elif status in ["IN_TRANSIT", "DELAYED"]:
                if j == 0 or (j < num_legs - 1 and rng.random() > 0.4):
                    actual_dep = current_dep + timedelta(hours=float(rng.uniform(-0.3, 1.0)))
                    actual_arr = leg_arr + timedelta(hours=float(rng.uniform(-0.5, 2.0)))
                    leg_status = "COMPLETED"
                elif j == 1:
                    actual_dep = current_dep + timedelta(hours=float(rng.uniform(-0.3, 1.0)))
                    leg_status = "IN_TRANSIT"

            legs.append({
                "leg_id": leg_id,
                "shipment_id": shipment_id,
                "leg_sequence": leg_seq,
                "route_id": leg_route_id,
                "origin_facility_id": leg_orig,
                "destination_facility_id": leg_dest,
                "transport_mode": leg_mode,
                "planned_departure_at": ts(current_dep),
                "planned_arrival_at": ts(leg_arr),
                "actual_departure_at": ts(actual_dep),
                "actual_arrival_at": ts(actual_arr),
                "leg_status": leg_status,
                "distance_km": leg_dist,
            })
            current_dep = leg_arr + timedelta(hours=float(rng.uniform(0.5, 2.0)))

        # Generate status history (append-only lifecycle)
        status_histories.append({
            "history_id": format_status_history_id(ssh_seq),
            "shipment_id": shipment_id,
            "status": "CREATED",
            "changed_at": ts(created_at),
            "recorded_at": ts(created_at + timedelta(minutes=2)),
            "reason": "Order booked and created in system",
            "updated_by": "SYSTEM",
        })
        ssh_seq += 1

        if status != "CANCELLED":
            status_histories.append({
                "history_id": format_status_history_id(ssh_seq),
                "shipment_id": shipment_id,
                "status": "IN_TRANSIT",
                "changed_at": ts(actual_pickup_at or planned_pickup_at),
                "recorded_at": ts((actual_pickup_at or planned_pickup_at) + timedelta(minutes=15)),
                "reason": "Picked up from origin facility",
                "updated_by": f"CARRIER-{carrier_id}",
            })
            ssh_seq += 1

        if status == "DELIVERED":
            status_histories.append({
                "history_id": format_status_history_id(ssh_seq),
                "shipment_id": shipment_id,
                "status": "DELIVERED",
                "changed_at": ts(actual_delivery_at),
                "recorded_at": ts(actual_delivery_at + timedelta(minutes=10)),
                "reason": "Customer signature obtained; delivery completed",
                "updated_by": "DRIVER_APP",
            })
            ssh_seq += 1

        # Route change history (approximately 8% of shipments undergo route modification)
        if rng.random() < 0.08 and num_legs > 1:
            change_time = created_at + timedelta(hours=planned_transit_hours * 0.4)
            route_changes.append({
                "history_id": format_route_change_id(rch_seq),
                "shipment_id": shipment_id,
                "change_type": "DETOUR_CONGESTION",
                "old_route_id": primary_route_id,
                "new_route_id": f"{primary_route_id}-ALT",
                "changed_at": ts(change_time),
                "recorded_at": ts(change_time + timedelta(minutes=5)),
                "impact_hours": round(float(rng.uniform(1.5, 6.0)), 1),
                "reason": "Congestion avoidance re-routing around interstate blockage",
            })
            rch_seq += 1

        # Delay reason associations (for delayed shipments)
        if is_delayed:
            n_reasons = int(rng.choice([1, 2], p=[0.75, 0.25]))
            chosen_reasons = rng.choice(delay_reason_ids, size=min(n_reasons, len(delay_reason_ids)), replace=False)
            split_delay = delay_hours / len(chosen_reasons)
            for r_id in chosen_reasons:
                shipment_delay_reasons.append({
                    "association_id": format_shipment_delay_reason_id(sdr_seq),
                    "shipment_id": shipment_id,
                    "reason_id": r_id,
                    "attributed_delay_hours": round(split_delay, 2),
                    "confidence_score": round(float(rng.uniform(0.75, 0.98)), 2),
                    "evidence_references": f"LOG-EVD-{shipment_id}-{r_id}",
                })
                sdr_seq += 1

    return (
        pd.DataFrame(shipments),
        pd.DataFrame(legs),
        pd.DataFrame(status_histories),
        pd.DataFrame(route_changes),
        pd.DataFrame(shipment_delay_reasons),
        pd.DataFrame(routes_records),
    )
