"""Master Synthetic Data Generator Pipeline
Orchestrates dependency-ordered data generation for all 16 relational entities:
1. Carriers
2. Facilities
3. Routes
4. ServiceLevels
5. DelayReasons
6. CarrierCalendars
7. FacilityCalendars
8. Shipments
9. ShipmentLegs
10. ShipmentStatusHistory
11. RouteChangeHistory
12. ShipmentDelayReasons
13. TrackingEvents
14. WeatherEvents (and weather_forecasts)
15. FacilityQueues
16. ETAEstimates (and eta_snapshots)
Plus GroundTruth (CSV and JSON).

Modes:
- starter: 500 shipments, 15 facilities, ~3,000 events, 45 disruptions
- full: 50,000 shipments, 300,000 events, 100 facilities, 1,000 disruptions
Default seed: 20261022
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd

from src.data_generation.master_data import (
    generate_service_levels,
    generate_delay_reasons,
    generate_carriers,
    generate_facilities,
    generate_routes,
    generate_carrier_calendars,
    generate_facility_calendars,
)
from src.data_generation.shipment_generator import generate_shipments_and_legs
from src.data_generation.tracking_generator import generate_tracking_events
from src.data_generation.disruption_generator import generate_weather_events, generate_facility_queues, generate_disruptions
from src.data_generation.eta_generator import generate_eta_estimates
from src.data_generation.anomaly_injector import inject_anomalies_and_generate_ground_truth

DEFAULT_SEED = 20261022


def run_generation_pipeline(
    mode: str = "starter",
    seed: int = DEFAULT_SEED,
    shipment_override: int | None = None,
    network: str = "us",
    output_dir: str | Path | None = None,
) -> Dict[str, pd.DataFrame]:
    """Execute complete dependency-ordered synthetic dataset generation."""
    rng = np.random.default_rng(seed)

    # Determine scale
    if shipment_override is not None:
        n_shipments = shipment_override
        n_facilities = max(15, min(100, int(n_shipments / 100)))
        n_disruptions = max(40, int(n_shipments / 50))
        n_carriers = 8 if n_shipments <= 5000 else 12
    elif mode == "full":
        n_shipments = 50000
        n_facilities = 100
        n_disruptions = 1000
        n_carriers = 12
    else:  # starter
        n_shipments = 500
        n_facilities = 15
        n_disruptions = 45
        n_carriers = 8

    print(f"\n=======================================================")
    print(f"Logistics Synthetic Data Pipeline")
    print(f"Mode: {mode.upper()} | Seed: {seed} | Shipments: {n_shipments:,} | Facilities: {n_facilities}")
    print(f"=======================================================")

    # 1. Master Data
    print("  [1/7] Generating ServiceLevels & DelayReasons master tables...")
    service_levels_df = generate_service_levels()
    delay_reasons_df = generate_delay_reasons()

    print(f"  [2/7] Generating {n_carriers} Carriers and {n_facilities} Facilities ({network.upper()} network)...")
    carriers_df = generate_carriers(rng, n_carriers=n_carriers)
    facilities_df = generate_facilities(rng, n_facilities=n_facilities, network=network)

    print("  [3/7] Generating Routes network & Operational Calendars...")
    routes_df = generate_routes(facilities_df, rng)
    carrier_cals_df = generate_carrier_calendars(carriers_df)
    facility_cals_df = generate_facility_calendars(facilities_df)

    # 2. Transactions: Shipments, Legs, Status History, Route Changes
    print(f"  [4/7] Generating {n_shipments:,} Shipments and Legs...")
    shipments_df, legs_df, status_hist_df, route_hist_df, ship_delays_df, routes_df = generate_shipments_and_legs(
        carriers_df=carriers_df,
        facilities_df=facilities_df,
        routes_df=routes_df,
        service_levels_df=service_levels_df,
        delay_reasons_df=delay_reasons_df,
        rng=rng,
        n_shipments=n_shipments,
    )

    # 3. Tracking Events
    print(f"  [5/7] Generating Tracking Event Ledgers...")
    tracking_events_df = generate_tracking_events(shipments_df, legs_df, rng)

    # 4. Disruptions & Queues
    print(f"  [6/7] Generating {n_disruptions} Weather Windows & Facility Queues & Disruptions...")
    weather_df = generate_weather_events(facilities_df, routes_df, rng, n_windows=n_disruptions)
    queues_df = generate_facility_queues(facilities_df, rng, sample_interval_days=4 if mode == "starter" else 8)
    disruptions_df = generate_disruptions(facilities_df, rng, n_disruptions=n_disruptions)

    # 5. ETA Estimates
    print("  [7/7] Generating Point-in-Time ETA Estimates & Injecting Anomalies...")
    # For large datasets (full mode), sample ETA snapshots per shipment to maintain targeted scale
    snaps_per_ship = 4 if mode == "starter" else 2
    eta_df = generate_eta_estimates(shipments_df, tracking_events_df, weather_df, queues_df, rng, snapshots_per_shipment=snaps_per_ship)

    # Inject Controlled Anomalies
    scale_factor = n_shipments / 500.0
    shipments_df, legs_df, tracking_events_df, eta_df, ground_truth_df = inject_anomalies_and_generate_ground_truth(
        shipments_df, legs_df, tracking_events_df, eta_df, facilities_df, rng, scale_factor=min(scale_factor, 1.0)
    )

    # Prepare backward-compatibility DataFrames
    weather_forecasts_df = weather_df.copy()
    weather_forecasts_df["forecast_id"] = weather_forecasts_df["weather_id"]
    weather_forecasts_df["valid_from"] = weather_forecasts_df["started_at"]
    weather_forecasts_df["valid_to"] = weather_forecasts_df["ended_at"]
    weather_forecasts_df["issued_at"] = weather_forecasts_df["forecast_issued_at"]

    route_changes_df = route_hist_df.copy()
    route_changes_df["change_id"] = route_changes_df["history_id"]

    all_tables = {
        "carriers": carriers_df,
        "facilities": facilities_df,
        "routes": routes_df,
        "service_levels": service_levels_df,
        "delay_reasons": delay_reasons_df,
        "carrier_calendars": carrier_cals_df,
        "facility_calendars": facility_cals_df,
        "shipments": shipments_df,
        "shipment_legs": legs_df,
        "shipment_status_history": status_hist_df,
        "route_change_history": route_hist_df,
        "shipment_delay_reasons": ship_delays_df,
        "tracking_events": tracking_events_df,
        "weather_events": weather_df,
        "weather_forecasts": weather_forecasts_df,
        "facility_queues": queues_df,
        "disruptions": disruptions_df,
        "eta_estimates": eta_df,
        "eta_snapshots": eta_df,
        "route_changes": route_changes_df,
        "ground_truth_anomalies": ground_truth_df,
        "ground_truth": ground_truth_df,
    }

    # Save outputs if output_dir specified
    if output_dir:
        out_p = Path(output_dir)
        out_p.mkdir(parents=True, exist_ok=True)
        print(f"\nPersisting generated tables to {out_p}...")
        for name, df in all_tables.items():
            if name in ["ground_truth"]:
                continue
            df.to_csv(out_p / f"{name}.csv", index=False)

        # Ground truth CSV and JSON
        ground_truth_df.to_csv(out_p / "ground_truth.csv", index=False)
        with open(out_p / "ground_truth.json", "w") as f:
            json.dump(ground_truth_df.to_dict(orient="records"), f, indent=2)

    print("\nDataset generation completed successfully.")
    print("Summary of Generated Entities:")
    for k in ["shipments", "shipment_legs", "tracking_events", "facilities", "weather_events", "eta_estimates", "ground_truth"]:
        if k in all_tables:
            print(f"  - {k}: {len(all_tables[k]):,} rows")

    return all_tables
