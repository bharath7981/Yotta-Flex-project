"""Disruption Generation Module
Generates:
1. WeatherEvent (40-50 windows for starter, 1,000 windows for full)
2. FacilityQueue (periodic queue observations and congestion spikes)
"""

from datetime import datetime, timedelta
from typing import Tuple, List, Dict, Any
import numpy as np
import pandas as pd

from src.data.id_generator import format_weather_id, format_queue_id

BASE_DATE = datetime(2026, 6, 1, 0, 0, 0)
END_DATE = datetime(2026, 10, 31, 23, 59, 59)


def ts(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_weather_events(
    facilities_df: pd.DataFrame,
    routes_df: pd.DataFrame,
    rng: np.random.Generator,
    n_windows: int = 45,
) -> pd.DataFrame:
    """Generate discrete WeatherEvents overlapping network hubs."""
    events: List[Dict[str, Any]] = []
    facility_ids = facilities_df["facility_id"].tolist()
    routes_list = routes_df["route_id"].tolist()
    total_window_seconds = int((END_DATE - BASE_DATE).total_seconds())

    w_types = ["RAIN", "STORM", "SNOW", "FOG", "HIGH_WIND", "BLIZZARD"]
    w_probs = [0.35, 0.25, 0.15, 0.12, 0.08, 0.05]
    severities = ["LOW", "MODERATE", "SEVERE", "EXTREME"]
    sev_probs = [0.40, 0.35, 0.20, 0.05]

    for i in range(1, n_windows + 1):
        fac_id = str(rng.choice(facility_ids))
        route_id = str(rng.choice(routes_list)) if rng.random() < 0.4 else None
        w_type = str(rng.choice(w_types, p=w_probs))
        severity = str(rng.choice(severities, p=sev_probs))

        # Random start within window
        start_sec = int(rng.integers(0, total_window_seconds - 86400))
        started_at = BASE_DATE + timedelta(seconds=start_sec)
        duration_h = float(rng.uniform(3.0, 36.0)) if severity in ["SEVERE", "EXTREME"] else float(rng.uniform(1.0, 12.0))
        ended_at = started_at + timedelta(hours=duration_h)

        # Forecast issued 6 to 48 hours prior
        forecast_issued_at = started_at - timedelta(hours=float(rng.uniform(6.0, 48.0)))
        observed_at = started_at + timedelta(minutes=float(rng.uniform(5, 30)))

        is_disruptive = 1 if severity in ["SEVERE", "EXTREME"] or w_type in ["BLIZZARD", "STORM"] else 0
        precip = round(float(rng.uniform(15.0, 95.0)) if is_disruptive else float(rng.uniform(0.0, 10.0)), 1)
        wind = round(float(rng.uniform(45.0, 110.0)) if is_disruptive else float(rng.uniform(10.0, 35.0)), 1)

        events.append({
            "weather_id": format_weather_id(i),
            "facility_id": fac_id,
            "route_id": route_id,
            "weather_type": w_type,
            "severity": severity,
            "started_at": ts(started_at),
            "ended_at": ts(ended_at),
            "forecast_issued_at": ts(forecast_issued_at),
            "observed_at": ts(observed_at),
            "precipitation_mm": precip,
            "wind_speed_kmh": wind,
            "is_disruptive": is_disruptive,
            "source": "NATIONAL_WEATHER_SERVICE",
        })

    return pd.DataFrame(events)


def generate_facility_queues(
    facilities_df: pd.DataFrame,
    rng: np.random.Generator,
    sample_interval_days: int = 5,
) -> pd.DataFrame:
    """Generate FacilityQueue observations across time."""
    records: List[Dict[str, Any]] = []
    total_days = int((END_DATE - BASE_DATE).days)
    q_seq = 1

    for fac in facilities_df.itertuples():
        fac_id = fac.facility_id
        capacity = int(fac.processing_capacity_per_hour)

        # Generate observations every sample_interval_days across simulation
        for day in range(0, total_days, max(1, sample_interval_days)):
            for hour in [8, 14, 20]:
                obs_dt = BASE_DATE + timedelta(days=day, hours=hour, minutes=int(rng.integers(0, 50)))
                ingest_dt = obs_dt + timedelta(minutes=float(rng.uniform(2, 20)))

                # Normal utilization vs spike
                is_spike = bool(rng.random() < 0.08)
                if is_spike:
                    util = round(float(rng.uniform(0.91, 1.25)), 3)
                    q_len = int(capacity * util)
                    wait_m = round(float(rng.uniform(75.0, 240.0)), 1)
                    exp_delay_h = round(wait_m / 60.0, 2)
                    is_disrupted = 1
                else:
                    util = round(float(rng.uniform(0.35, 0.85)), 3)
                    q_len = int(capacity * util)
                    wait_m = round(float(rng.uniform(10.0, 45.0)), 1)
                    exp_delay_h = round(wait_m / 60.0, 2)
                    is_disrupted = 0

                records.append({
                    "queue_id": format_queue_id(q_seq),
                    "facility_id": fac_id,
                    "observed_at": ts(obs_dt),
                    "ingested_at": ts(ingest_dt),
                    "queue_length": q_len,
                    "avg_waiting_time_minutes": wait_m,
                    "processing_capacity": capacity,
                    "utilization": util,
                    "expected_processing_delay_hours": exp_delay_h,
                    "is_disrupted": is_disrupted,
                })
                q_seq += 1

    return pd.DataFrame(records)


def generate_disruptions(
    facilities_df: pd.DataFrame,
    rng: np.random.Generator,
    n_disruptions: int = 1000,
) -> pd.DataFrame:
    """Generate operational disruptions across network facilities."""
    records: List[Dict[str, Any]] = []
    facility_ids = facilities_df["facility_id"].tolist()
    total_window_seconds = int((END_DATE - BASE_DATE).total_seconds())

    types = ["CONGESTION", "EQUIPMENT_FAILURE", "CUSTOMS_HOLD", "LABOR_ACTION", "WEATHER_SLOWDOWN", "GATE_SYSTEM_DOWN"]
    severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    sev_weights = [0.40, 0.35, 0.20, 0.05]

    for i in range(1, n_disruptions + 1):
        f_id = str(rng.choice(facility_ids))
        d_type = str(rng.choice(types))
        sev = str(rng.choice(severities, p=sev_weights))
        start_sec = int(rng.integers(0, total_window_seconds - 86400 * 2))
        start_dt = BASE_DATE + timedelta(seconds=start_sec)
        dur_h = float(rng.uniform(2.0, 36.0)) if sev in ["HIGH", "CRITICAL"] else float(rng.uniform(1.0, 12.0))
        end_dt = start_dt + timedelta(hours=dur_h)
        rep_dt = start_dt - timedelta(minutes=float(rng.uniform(10, 60)))

        d_id = f"DIS-{i:04d}"
        desc = f"{sev} {d_type} at facility {f_id}"
        impact = f"Potential delays and gate queue accumulation for shipments processing through {f_id}"

        records.append({
            "disruption_id": d_id,
            "facility_id": f_id,
            "disruption_type": d_type,
            "severity": sev,
            "started_at": ts(start_dt),
            "ended_at": ts(end_dt),
            "reported_at": ts(rep_dt),
            "description": desc,
            "impact_description": impact,
        })

    return pd.DataFrame(records)
