"""Evidence collection module for shipment delay analysis."""
import pandas as pd
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "existing"


def _load_data() -> dict[str, pd.DataFrame]:
    """Load all required CSVs with parsed timestamps."""
    ts_cols = {
        "shipments": ["created_at", "planned_delivery_at", "actual_delivery_at"],
        "shipment_legs": [
            "planned_departure_at", "planned_arrival_at",
            "actual_departure_at", "actual_arrival_at",
        ],
        "tracking_events": ["event_time", "ingested_at"],
        "eta_snapshots": [
            "snapshot_time", "planned_delivery_at", "predicted_delivery_at",
            "data_cutoff_at", "max_ingested_at_used",
        ],
        "facility_queues": ["observed_at", "ingested_at"],
        "weather_forecasts": ["valid_from", "valid_to", "issued_at"],
        "route_changes": ["changed_at", "recorded_at"],
        "disruptions": ["started_at", "ended_at", "reported_at"],
    }
    data: dict[str, pd.DataFrame] = {}
    for name, cols in ts_cols.items():
        csv_file = DATA_DIR / f"{name}.csv"
        if not csv_file.exists():
            csv_file = DATA_DIR.parent / "generated" / f"{name}.csv"
        df = pd.read_csv(csv_file)
        for c in cols:
            if c in df.columns:
                df[c] = pd.to_datetime(df[c], utc=True, errors="coerce")
        data[name] = df
    return data


def _get_or_create_cache(data: dict[str, Any], key: str, source_key: str, group_col: str):
    cached = data.get(key)
    if cached is None:
        source_df = data.get(source_key, pd.DataFrame())
        if not source_df.empty and group_col in source_df.columns:
            cached = {k: v for k, v in source_df.groupby(group_col)}
        else:
            cached = {}
        data[key] = cached
    return cached


def collect_evidence(
    shipment_id: str,
    data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Collect all evidence records for a given shipment.

    Returns a list of dicts with keys:
        evidence_type, evidence_id, description, timestamp, severity
    """
    evidence: list[dict[str, Any]] = []

    # Pre-cache group lookups for fast retrieval across thousands of shipments
    events_by_ship = _get_or_create_cache(data, "_cache_events_by_ship", "tracking_events", "shipment_id")
    legs_by_ship = _get_or_create_cache(data, "_cache_legs_by_ship", "shipment_legs", "shipment_id")
    rc_by_ship = _get_or_create_cache(data, "_cache_rc_by_ship", "route_changes", "shipment_id")
    etas_by_ship = _get_or_create_cache(data, "_cache_etas_by_ship", "eta_snapshots", "shipment_id")
    q_by_fac = _get_or_create_cache(data, "_cache_q_by_fac", "facility_queues", "facility_id")
    wf_by_fac = _get_or_create_cache(data, "_cache_wf_by_fac", "weather_forecasts", "facility_id")
    dis_by_fac = _get_or_create_cache(data, "_cache_dis_by_fac", "disruptions", "facility_id")

    # --- tracking events ---
    ship_events = events_by_ship.get(shipment_id, pd.DataFrame())
    if not ship_events.empty:
        for ev in ship_events.itertuples():
            fac_id = getattr(ev, "facility_id", "N/A")
            desc = getattr(ev, "description", "")
            evidence.append({
                "evidence_type": "TRACKING_EVENT",
                "evidence_id": getattr(ev, "event_id", ""),
                "description": f"{getattr(ev, 'event_type', '')} at {fac_id}: {desc}",
                "timestamp": getattr(ev, "event_time", None),
                "severity": "LOW",
            })

    # --- shipment legs ---
    ship_legs = legs_by_ship.get(shipment_id, pd.DataFrame())
    facility_ids = set()
    if not ship_legs.empty:
        for leg in ship_legs.itertuples():
            facility_ids.add(getattr(leg, "origin_facility_id", None))
            facility_ids.add(getattr(leg, "destination_facility_id", None))
            status = getattr(leg, "leg_status", "")
            sev = "LOW"
            desc = (
                f"Leg {getattr(leg, 'leg_sequence', '')} ({getattr(leg, 'origin_facility_id', '')} -> "
                f"{getattr(leg, 'destination_facility_id', '')}) via {getattr(leg, 'transport_mode', '')}, status={status}"
            )
            act_arr = getattr(leg, "actual_arrival_at", None)
            pln_arr = getattr(leg, "planned_arrival_at", None)
            if pd.notna(act_arr) and pd.notna(pln_arr):
                delta_h = (pd.to_datetime(act_arr, utc=True) - pd.to_datetime(pln_arr, utc=True)).total_seconds() / 3600
                if delta_h > 2:
                    sev = "MEDIUM" if delta_h <= 12 else "HIGH"
                    desc += f" — arrived {delta_h:.1f}h {'late' if delta_h > 0 else 'early'}"
            evidence.append({
                "evidence_type": "SHIPMENT_LEG",
                "evidence_id": getattr(leg, "leg_id", ""),
                "description": desc,
                "timestamp": getattr(leg, "actual_departure_at", None) or getattr(leg, "planned_departure_at", None),
                "severity": sev,
            })

    facility_ids.discard(None)

    # --- facility queues (for facilities on route) ---
    for f_id in facility_ids:
        fac_q = q_by_fac.get(f_id)
        if fac_q is not None and not fac_q.empty:
            high_util = fac_q[fac_q["utilization"] > 0.85]
            for q in high_util.itertuples():
                util = getattr(q, "utilization", 0.0)
                is_dis = getattr(q, "is_disrupted", 0)
                dis_text = ", facility is disrupted" if is_dis else ""
                evidence.append({
                    "evidence_type": "FACILITY_QUEUE",
                    "evidence_id": getattr(q, "queue_id", ""),
                    "description": (
                        f"Facility {f_id} utilization={util:.2f}, "
                        f"queue_length={getattr(q, 'queue_length', 0)}, avg_wait={getattr(q, 'avg_waiting_time_minutes', 0.0):.0f}min{dis_text}"
                    ),
                    "timestamp": getattr(q, "observed_at", None),
                    "severity": "HIGH" if util > 0.95 else "MEDIUM",
                })

    # --- weather forecasts for route facilities ---
    for f_id in facility_ids:
        fac_w = wf_by_fac.get(f_id)
        if fac_w is not None and not fac_w.empty:
            disruptive_w = fac_w[fac_w["is_disruptive"] == True]
            for w in disruptive_w.itertuples():
                sev = getattr(w, "severity", "MEDIUM")
                w_type = getattr(w, "weather_type", getattr(w, "condition", "STORM"))
                evidence.append({
                    "evidence_type": "WEATHER_FORECAST",
                    "evidence_id": getattr(w, "forecast_id", getattr(w, "event_id", "")),
                    "description": (
                        f"Disruptive weather at {f_id}: {w_type}, "
                        f"severity={sev}, precip={getattr(w, 'precipitation_mm', 0.0)}mm, "
                        f"wind={getattr(w, 'wind_speed_kmh', 0.0)}km/h"
                    ),
                    "timestamp": getattr(w, "valid_from", None),
                    "severity": "HIGH" if sev in ("SEVERE", "EXTREME") else "MEDIUM",
                })

    # --- disruptions at route facilities ---
    for f_id in facility_ids:
        fac_dis = dis_by_fac.get(f_id)
        if fac_dis is not None and not fac_dis.empty:
            for d in fac_dis.itertuples():
                sev = getattr(d, "severity", "MEDIUM")
                evidence.append({
                    "evidence_type": "DISRUPTION",
                    "evidence_id": getattr(d, "disruption_id", ""),
                    "description": (
                        f"Disruption at {f_id}: {getattr(d, 'disruption_type', '')} "
                        f"({sev}), {getattr(d, 'description', '')}"
                    ),
                    "timestamp": getattr(d, "started_at", None),
                    "severity": sev if sev in ("HIGH", "CRITICAL") else "MEDIUM",
                })

    # --- route changes ---
    ship_rc = rc_by_ship.get(shipment_id, pd.DataFrame())
    if not ship_rc.empty:
        for r in ship_rc.itertuples():
            chg_type = getattr(r, "change_type", "REROUTE")
            reason = getattr(r, "reason", getattr(r, "description", ""))
            imp_h = getattr(r, "impact_hours", 0.0)
            evidence.append({
                "evidence_type": "ROUTE_CHANGE",
                "evidence_id": getattr(r, "change_id", getattr(r, "history_id", "")),
                "description": f"Route change ({chg_type}): {reason}, impact={imp_h}h",
                "timestamp": getattr(r, "changed_at", getattr(r, "recorded_at", None)),
                "severity": "HIGH" if imp_h > 12 else "MEDIUM",
            })

    # --- ETA snapshots showing slip ---
    ship_etas = etas_by_ship.get(shipment_id, pd.DataFrame())
    if not ship_etas.empty:
        for e in ship_etas.itertuples():
            pred_dt = getattr(e, "predicted_delivery_at", None)
            pln_dt = getattr(e, "planned_delivery_at", None)
            if pd.notna(pred_dt) and pd.notna(pln_dt):
                slip_h = (pd.to_datetime(pred_dt, utc=True) - pd.to_datetime(pln_dt, utc=True)).total_seconds() / 3600
                if slip_h > 0:
                    evidence.append({
                        "evidence_type": "ETA_SNAPSHOT",
                        "evidence_id": getattr(e, "eta_id", ""),
                        "description": (
                            f"ETA slip: predicted {slip_h:.1f}h past planned "
                            f"(method={getattr(e, 'prediction_method', '')}, confidence={getattr(e, 'confidence_score', 0.0):.2f})"
                        ),
                        "timestamp": getattr(e, "snapshot_time", None),
                        "severity": "HIGH" if slip_h > 24 else "MEDIUM" if slip_h > 6 else "LOW",
                    })

    return evidence
