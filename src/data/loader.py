"""Data loader module for the Logistics ETA Platform.

Loads CSV datasets, parses timestamps to UTC datetime objects,
and handles null values appropriately. Provides a single entry point `load_all_data()`
that returns a dictionary of pandas DataFrames keyed by table name.
"""

import os
from pathlib import Path
from typing import Dict, Optional
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "existing"

# Comprehensive schema definitions for all 16 core & supporting tables
_SCHEMAS: Dict[str, dict] = {
    "carriers": {
        "file": "carriers.csv",
        "ts_cols": [],
        "nullable_ts_cols": [],
    },
    "facilities": {
        "file": "facilities.csv",
        "ts_cols": [],
        "nullable_ts_cols": [],
    },
    "routes": {
        "file": "routes.csv",
        "ts_cols": [],
        "nullable_ts_cols": [],
    },
    "service_levels": {
        "file": "service_levels.csv",
        "ts_cols": [],
        "nullable_ts_cols": [],
    },
    "delay_reasons": {
        "file": "delay_reasons.csv",
        "ts_cols": [],
        "nullable_ts_cols": [],
    },
    "carrier_calendars": {
        "file": "carrier_calendars.csv",
        "ts_cols": ["effective_start_date", "effective_end_date"],
        "nullable_ts_cols": [],
    },
    "facility_calendars": {
        "file": "facility_calendars.csv",
        "ts_cols": ["effective_start_date", "effective_end_date"],
        "nullable_ts_cols": [],
    },
    "shipments": {
        "file": "shipments.csv",
        "ts_cols": ["created_at", "planned_delivery_at"],
        "nullable_ts_cols": ["actual_delivery_at", "actual_pickup_at", "promised_delivery_at", "planned_pickup_at"],
    },
    "shipment_legs": {
        "file": "shipment_legs.csv",
        "ts_cols": ["planned_departure_at", "planned_arrival_at"],
        "nullable_ts_cols": ["actual_departure_at", "actual_arrival_at"],
    },
    "shipment_status_history": {
        "file": "shipment_status_history.csv",
        "ts_cols": ["changed_at", "recorded_at"],
        "nullable_ts_cols": [],
    },
    "route_change_history": {
        "file": "route_change_history.csv",
        "ts_cols": ["changed_at", "recorded_at"],
        "nullable_ts_cols": [],
    },
    "shipment_delay_reasons": {
        "file": "shipment_delay_reasons.csv",
        "ts_cols": [],
        "nullable_ts_cols": [],
    },
    "tracking_events": {
        "file": "tracking_events.csv",
        "ts_cols": ["event_time", "ingested_at"],
        "nullable_ts_cols": [],
    },
    "eta_snapshots": {
        "file": "eta_snapshots.csv",
        "ts_cols": ["snapshot_time", "planned_delivery_at", "predicted_delivery_at",
                     "data_cutoff_at", "max_ingested_at_used"],
        "nullable_ts_cols": [],
    },
    "eta_estimates": {
        "file": "eta_estimates.csv",
        "ts_cols": ["prediction_timestamp", "predicted_arrival_timestamp", "p50_eta", "p90_eta",
                     "feature_cutoff_timestamp", "snapshot_time", "planned_delivery_at", "predicted_delivery_at"],
        "nullable_ts_cols": [],
    },
    "facility_queues": {
        "file": "facility_queues.csv",
        "ts_cols": ["observed_at", "ingested_at"],
        "nullable_ts_cols": [],
    },
    "weather_events": {
        "file": "weather_events.csv",
        "ts_cols": ["started_at", "ended_at", "forecast_issued_at", "observed_at"],
        "nullable_ts_cols": [],
    },
    "weather_forecasts": {
        "file": "weather_forecasts.csv",
        "ts_cols": ["valid_from", "valid_to", "issued_at"],
        "nullable_ts_cols": [],
    },
    "weather_observations": {
        "file": "weather_observations.csv",
        "ts_cols": ["observed_at", "ingested_at"],
        "nullable_ts_cols": [],
    },
    "route_changes": {
        "file": "route_changes.csv",
        "ts_cols": ["changed_at", "recorded_at"],
        "nullable_ts_cols": [],
    },
    "disruptions": {
        "file": "disruptions.csv",
        "ts_cols": ["started_at", "reported_at"],
        "nullable_ts_cols": ["ended_at"],
    },
    "ground_truth_anomalies": {
        "file": "ground_truth_anomalies.csv",
        "ts_cols": [],
        "nullable_ts_cols": [],
    },
    "ground_truth": {
        "file": "ground_truth.csv",
        "ts_cols": [],
        "nullable_ts_cols": [],
    },
}


def _load_table(table_name: str, schema: dict, data_dir: Path) -> Optional[pd.DataFrame]:
    """Load a single CSV table with proper type parsing. Returns None if file does not exist."""
    filepath = data_dir / schema["file"]
    if not filepath.exists():
        return None

    df = pd.read_csv(filepath)

    # Parse non-nullable timestamp columns
    for col in schema["ts_cols"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")

    # Parse nullable timestamp columns
    for col in schema["nullable_ts_cols"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")

    # Convert boolean-like string columns
    for col in df.columns:
        if df[col].dtype == object:
            unique_vals = set(df[col].dropna().unique())
            if unique_vals <= {"True", "False", "true", "false"}:
                df[col] = df[col].map(
                    {"True": True, "False": False, "true": True, "false": False}
                )

    return df


def load_all_data(data_dir: Path | None = None) -> Dict[str, pd.DataFrame]:
    """Load all available CSV datasets from the data directory.
    
    If data/generated exists and has files, defaults to data/generated if data/existing lacks new entities.
    """
    if data_dir is None:
        generated_dir = PROJECT_ROOT / "data" / "generated"
        if generated_dir.exists() and (generated_dir / "routes.csv").exists():
            data_dir = generated_dir
        else:
            data_dir = DATA_DIR

    data = {}
    for table_name, schema in _SCHEMAS.items():
        loaded = _load_table(table_name, schema, data_dir)
        if loaded is not None:
            data[table_name] = loaded

    # Maintain aliases if either modern or legacy table is loaded
    if "eta_estimates" in data and "eta_snapshots" not in data:
        data["eta_snapshots"] = data["eta_estimates"]
    elif "eta_snapshots" in data and "eta_estimates" not in data:
        data["eta_estimates"] = data["eta_snapshots"]

    if "weather_events" in data and "weather_forecasts" not in data:
        wf = data["weather_events"].copy()
        wf["forecast_id"] = wf["weather_id"]
        wf["valid_from"] = wf["started_at"]
        wf["valid_to"] = wf["ended_at"]
        wf["issued_at"] = wf["forecast_issued_at"]
        data["weather_forecasts"] = wf

    if "route_change_history" in data and "route_changes" not in data:
        rc = data["route_change_history"].copy()
        rc["change_id"] = rc["history_id"]
        data["route_changes"] = rc

    if "ground_truth" in data and "ground_truth_anomalies" not in data:
        data["ground_truth_anomalies"] = data["ground_truth"]

    return data


if __name__ == "__main__":
    print("Loading all datasets...")
    datasets = load_all_data()
    for name, df in datasets.items():
        print(f"  {name}: {len(df)} rows, {len(df.columns)} columns")
    print("All datasets loaded successfully.")
