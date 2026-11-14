"""Tracking Event Generation Module
Generates comprehensive tracking events:
- PICKUP
- DEPARTURE
- ARRIVAL
- FACILITY_PROCESSING
- CUSTOMS_CLEARED (where applicable)
- OUT_FOR_DELIVERY
- DELIVERED

Separates event_time and ingested_at with realistic ingestion delays (1-120 minutes).
Uses deterministic event sequence formatting: EVT-SHP-2026-000001-000001
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any
import numpy as np
import pandas as pd

from src.data.id_generator import format_tracking_event_id


def ts(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_tracking_events(
    shipments_df: pd.DataFrame,
    legs_df: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Generate tracking event ledger strictly linked to shipments and legs."""
    events: List[Dict[str, Any]] = []

    # Group legs by shipment_id
    grouped_legs = legs_df.groupby("shipment_id")

    sources = ["IOT_SCANNER", "EDI_CARRIER", "API_PARTNER", "MANUAL_DISPATCH"]
    source_weights = [0.60, 0.25, 0.12, 0.03]

    for ship in shipments_df.itertuples():
        ship_id = ship.shipment_id
        carrier_id = ship.carrier_id
        status = ship.current_status
        origin_fac = ship.origin_facility_id
        dest_fac = ship.destination_facility_id

        if ship_id not in grouped_legs.groups:
            continue

        ship_legs = grouped_legs.get_group(ship_id).sort_values("leg_sequence")
        evt_counter = 1

        # 1. PICKUP Event (if not cancelled)
        if status != "CANCELLED":
            pickup_dt = datetime.strptime(ship.actual_pickup_at or ship.planned_pickup_at, "%Y-%m-%dT%H:%M:%SZ")
            ingest_dt = pickup_dt + timedelta(minutes=float(rng.uniform(2, 35)))
            events.append({
                "event_id": format_tracking_event_id(ship_id, evt_counter),
                "shipment_id": ship_id,
                "leg_id": ship_legs.iloc[0]["leg_id"],
                "carrier_id": carrier_id,
                "facility_id": origin_fac,
                "event_type": "PICKUP",
                "event_time": ts(pickup_dt),
                "ingested_at": ts(ingest_dt),
                "event_location": ship.origin_city,
                "event_source": str(rng.choice(sources, p=source_weights)),
                "event_sequence_number": evt_counter,
                "description": f"Shipment picked up by carrier {carrier_id} at {origin_fac}",
            })
            evt_counter += 1

        # 2. Leg-by-leg DEPARTURE, PROCESSING, ARRIVAL
        for leg_idx, leg in enumerate(ship_legs.itertuples()):
            leg_status = leg.leg_status
            if leg_status not in ["COMPLETED", "IN_TRANSIT"]:
                continue

            # Departure event
            dep_dt_str = leg.actual_departure_at or leg.planned_departure_at
            dep_dt = datetime.strptime(dep_dt_str, "%Y-%m-%dT%H:%M:%SZ")
            dep_ingest = dep_dt + timedelta(minutes=float(rng.uniform(3, 45)))

            events.append({
                "event_id": format_tracking_event_id(ship_id, evt_counter),
                "shipment_id": ship_id,
                "leg_id": leg.leg_id,
                "carrier_id": carrier_id,
                "facility_id": leg.origin_facility_id,
                "event_type": "DEPARTURE",
                "event_time": ts(dep_dt),
                "ingested_at": ts(dep_ingest),
                "event_location": leg.origin_facility_id,
                "event_source": str(rng.choice(sources, p=source_weights)),
                "event_sequence_number": evt_counter,
                "description": f"Departed origin hub {leg.origin_facility_id} via {leg.transport_mode}",
            })
            evt_counter += 1

            # Arrival event (if completed)
            if leg_status == "COMPLETED" and leg.actual_arrival_at:
                arr_dt = datetime.strptime(leg.actual_arrival_at, "%Y-%m-%dT%H:%M:%SZ")
                arr_ingest = arr_dt + timedelta(minutes=float(rng.uniform(5, 60)))

                events.append({
                    "event_id": format_tracking_event_id(ship_id, evt_counter),
                    "shipment_id": ship_id,
                    "leg_id": leg.leg_id,
                    "carrier_id": carrier_id,
                    "facility_id": leg.destination_facility_id,
                    "event_type": "ARRIVAL",
                    "event_time": ts(arr_dt),
                    "ingested_at": ts(arr_ingest),
                    "event_location": leg.destination_facility_id,
                    "event_source": str(rng.choice(sources, p=source_weights)),
                    "event_sequence_number": evt_counter,
                    "description": f"Arrived at facility {leg.destination_facility_id}",
                })
                evt_counter += 1

                # Intermediate Facility Processing
                if leg_idx < len(ship_legs) - 1:
                    proc_dt = arr_dt + timedelta(minutes=float(rng.uniform(30, 90)))
                    events.append({
                        "event_id": format_tracking_event_id(ship_id, evt_counter),
                        "shipment_id": ship_id,
                        "leg_id": leg.leg_id,
                        "carrier_id": carrier_id,
                        "facility_id": leg.destination_facility_id,
                        "event_type": "FACILITY_PROCESSING",
                        "event_time": ts(proc_dt),
                        "ingested_at": ts(proc_dt + timedelta(minutes=float(rng.uniform(2, 20)))),
                        "event_location": leg.destination_facility_id,
                        "event_source": "IOT_SCANNER",
                        "event_sequence_number": evt_counter,
                        "description": f"Automated sorting completed at {leg.destination_facility_id}",
                    })
                    evt_counter += 1

        # 3. Delivery Confirmation
        if status == "DELIVERED" and ship.actual_delivery_at:
            del_dt = datetime.strptime(ship.actual_delivery_at, "%Y-%m-%dT%H:%M:%SZ")
            
            # Out for delivery scan 1-3 hours prior
            ofd_dt = del_dt - timedelta(hours=float(rng.uniform(1.0, 3.0)))
            events.append({
                "event_id": format_tracking_event_id(ship_id, evt_counter),
                "shipment_id": ship_id,
                "leg_id": ship_legs.iloc[-1]["leg_id"],
                "carrier_id": carrier_id,
                "facility_id": dest_fac,
                "event_type": "OUT_FOR_DELIVERY",
                "event_time": ts(ofd_dt),
                "ingested_at": ts(ofd_dt + timedelta(minutes=float(rng.uniform(5, 30)))),
                "event_location": ship.destination_city,
                "event_source": "EDI_CARRIER",
                "event_sequence_number": evt_counter,
                "description": f"Out for delivery in {ship.destination_city}",
            })
            evt_counter += 1

            # Confirmed Delivered scan
            events.append({
                "event_id": format_tracking_event_id(ship_id, evt_counter),
                "shipment_id": ship_id,
                "leg_id": ship_legs.iloc[-1]["leg_id"],
                "carrier_id": carrier_id,
                "facility_id": dest_fac,
                "event_type": "DELIVERED",
                "event_time": ts(del_dt),
                "ingested_at": ts(del_dt + timedelta(minutes=float(rng.uniform(5, 25)))),
                "event_location": ship.destination_city,
                "event_source": "MANUAL_DISPATCH",
                "event_sequence_number": evt_counter,
                "description": "Delivery confirmed; consignee signature on file",
            })
            evt_counter += 1

    return pd.DataFrame(events)

