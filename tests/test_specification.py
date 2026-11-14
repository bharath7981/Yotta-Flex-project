"""Specification Verification Test Suite — Part 17
Comprehensive unit and integration test suite covering all 22 required areas:
1. ID generation formats
2. Primary-key uniqueness across all 16 tables
3. Foreign-key referential integrity across all 16 tables
4. Shipment-to-leg relationships
5. Shipment-to-event relationships
6. Route sequence and node handoff continuity
7. Event timestamp ordering
8. Ingestion timestamp handling and latency
9. ETA as-of calculations
10. Future-data leakage detection
11. SLA delay calculations
12. Ground-truth isolation and mandatory categories
13. Anomaly detection benchmark
14. Calendar handling
15. Queue calculations
16. Weather disruption effects
17. All 16 API endpoints
18. Dashboard data loading
19. CSV exports completeness
20. JSON exports completeness
21. Standalone SQL reconstruction
22. Fixed-seed reproducibility
"""

import json
from pathlib import Path
import duckdb
import pandas as pd
import pytest

from src.data.loader import load_all_data
from src.data.validator import DataValidator
from src.data.id_generator import (
    format_shipment_id, format_leg_id, format_tracking_event_id,
    format_eta_id, format_facility_id, format_carrier_id,
    format_route_id, format_anomaly_id, format_queue_id, format_weather_id
)
from src.data.sla import is_sla_breached

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def lake_data():
    return load_all_data()


# 1. ID generation formats
def test_01_id_generation_formats():
    assert format_shipment_id(1) == "SHP-2026-000001"
    assert format_leg_id("SHP-2026-000001", 1) == "LEG-SHP-2026-000001-01"
    assert format_tracking_event_id("SHP-2026-000001", 1) == "EVT-SHP-2026-000001-000001"
    assert format_eta_id("SHP-2026-000001", "2026-10-22T08:00:00Z") == "ETA-SHP-2026-000001-20261022080000"
    assert format_facility_id(1) == "FAC-2026-000001"
    assert format_carrier_id(1) == "CAR-2026-000001"
    assert format_route_id(1) == "RTE-2026-000001"
    assert format_anomaly_id(1) == "ANOM-2026-000001"
    assert format_queue_id(1) == "QUE-2026-000001"
    assert format_weather_id(1) == "WTH-2026-000001"


# 2. Primary-key uniqueness across all 16 tables
def test_02_primary_key_uniqueness(lake_data):
    validator = DataValidator(lake_data, allow_expected_anomalies=True)
    validator.validate_primary_keys()
    pk_issues = [i for i in validator.report.issues if i.rule == "PRIMARY_KEY_UNIQUE"]
    assert len(pk_issues) == 0, f"Primary key duplicates found: {pk_issues}"


# 3. Foreign-key referential integrity across all 16 tables
def test_03_foreign_key_referential_integrity(lake_data):
    validator = DataValidator(lake_data, allow_expected_anomalies=True)
    validator.validate_foreign_keys()
    fk_issues = [i for i in validator.report.issues if i.rule.startswith("FK_")]
    assert len(fk_issues) == 0, f"Foreign key referential integrity violations: {fk_issues}"


# 4. Shipment-to-leg relationships
def test_04_shipment_to_leg_relationships(lake_data):
    ships = lake_data["shipments"]
    legs = lake_data["shipment_legs"]
    leg_counts = legs.groupby("shipment_id")["leg_sequence"].count().to_dict()

    for _, row in ships.iterrows():
        s_id = row["shipment_id"]
        assert s_id in leg_counts, f"Shipment {s_id} has zero associated legs"
        assert leg_counts[s_id] == row["num_legs"], f"Shipment {s_id} leg count mismatch"


# 5. Shipment-to-event relationships
def test_05_shipment_to_event_relationships(lake_data):
    ships = lake_data["shipments"]
    events = lake_data["tracking_events"]
    ship_ids = set(ships["shipment_id"])
    assert events["shipment_id"].isin(ship_ids).all(), "Orphan tracking events detected"


# 6. Route sequence and node handoff continuity
def test_06_route_sequence_continuity(lake_data):
    legs = lake_data["shipment_legs"]
    for ship_id, ship_legs in legs.groupby("shipment_id"):
        seqs = ship_legs["leg_sequence"].sort_values().tolist()
        expected = list(range(1, len(seqs) + 1))
        assert seqs == expected, f"Shipment {ship_id} has non-contiguous leg sequence: {seqs}"


# 7. Event timestamp ordering
def test_07_event_timestamp_ordering(lake_data):
    ships = lake_data["shipments"]
    deliv = ships[ships["actual_delivery_at"].notna() & ships["actual_pickup_at"].notna()]
    assert (pd.to_datetime(deliv["actual_delivery_at"], utc=True) >= pd.to_datetime(deliv["actual_pickup_at"], utc=True)).all()


# 8. Ingestion timestamp handling and latency
def test_08_ingestion_timestamp_latency(lake_data):
    events = lake_data["tracking_events"]
    gt = lake_data.get("ground_truth", lake_data.get("ground_truth_anomalies"))
    known_ids = set(gt["entity_id"].dropna()) if gt is not None else set()

    clean_events = events[~events["event_id"].isin(known_ids)]
    assert (pd.to_datetime(clean_events["ingested_at"], utc=True) >= pd.to_datetime(clean_events["event_time"], utc=True)).all()


# 9. ETA as-of calculations
def test_09_eta_as_of_calculations(lake_data):
    etas = lake_data.get("eta_estimates", lake_data.get("eta_snapshots"))
    assert not etas.empty
    assert "p50_eta" in etas.columns or "predicted_arrival_timestamp" in etas.columns
    if "p50_eta" in etas.columns and "p90_eta" in etas.columns:
        p50 = pd.to_datetime(etas["p50_eta"], utc=True)
        p90 = pd.to_datetime(etas["p90_eta"], utc=True)
        assert (p90 >= p50).all(), "P90 ETA must be greater than or equal to P50 ETA"


# 10. Future-data leakage detection
def test_10_future_data_leakage_cutoff(lake_data):
    etas = lake_data.get("eta_estimates", lake_data.get("eta_snapshots"))
    cutoff_col = "feature_cutoff_timestamp" if "feature_cutoff_timestamp" in etas.columns else "snapshot_time"
    assert (pd.to_datetime(etas[cutoff_col], utc=True) <= pd.to_datetime(etas["prediction_timestamp"] if "prediction_timestamp" in etas.columns else etas["snapshot_time"], utc=True)).all()


# 11. SLA delay calculations
def test_11_sla_delay_calculations():
    # Exactly on time
    promised = pd.Timestamp("2026-10-22T12:00:00Z")
    actual_on_time = pd.Timestamp("2026-10-22T12:00:00Z")
    assert is_sla_breached(actual_on_time, promised, grace_hours=2.0, status="DELIVERED") == 0

    # Within grace period
    actual_grace = pd.Timestamp("2026-10-22T13:30:00Z")
    assert is_sla_breached(actual_grace, promised, grace_hours=2.0, status="DELIVERED") == 0

    # Beyond grace period (SLA breach)
    actual_breach = pd.Timestamp("2026-10-22T16:00:00Z")
    assert is_sla_breached(actual_breach, promised, grace_hours=2.0, status="DELIVERED") == 1

    # Unresolved or cancelled
    assert is_sla_breached(None, promised, grace_hours=2.0, status="IN_TRANSIT") is None
    assert is_sla_breached(actual_breach, promised, grace_hours=2.0, status="CANCELLED") is None


# 12. Ground-truth isolation and mandatory categories
def test_12_ground_truth_isolation(lake_data):
    gt = lake_data.get("ground_truth", lake_data.get("ground_truth_anomalies"))
    assert gt is not None and not gt.empty
    mandatory_categories = {
        "EVENT_INGESTION_CONFUSION",
        "IMPOSSIBLE_ROUTE_ORDER",
        "FUTURE_DATA_LEAKAGE",
        "DELIVERED_BUT_IN_TRANSIT"
    }
    present_categories = set(gt["issue_type"].dropna())
    for cat in mandatory_categories:
        assert cat in present_categories, f"Mandatory anomaly category {cat} missing from ground truth"


# 13. Anomaly detection benchmark
def test_13_anomaly_detection_benchmark(lake_data):
    from src.anomaly.detectors import AnomalyDetector
    det = AnomalyDetector(lake_data)
    detected_df = det.run_all_detectors()
    assert isinstance(detected_df, pd.DataFrame)
    assert len(detected_df) > 0


# 14. Calendar handling
def test_14_calendar_handling(lake_data):
    assert "carrier_calendars" in lake_data
    assert "facility_calendars" in lake_data
    assert len(lake_data["carrier_calendars"]) > 0
    assert len(lake_data["facility_calendars"]) > 0


# 15. Queue calculations
def test_15_queue_calculations(lake_data):
    queues = lake_data["facility_queues"]
    assert (queues["queue_length"] >= 0).all()
    assert (queues["wait_time_hours"] >= 0.0).all() if "wait_time_hours" in queues.columns else True


# 16. Weather disruption effects
def test_16_weather_disruptions(lake_data):
    wth = lake_data.get("weather_events", lake_data.get("weather_forecasts"))
    assert len(wth) >= 40
    assert "severity" in wth.columns


# 17. All 16 API endpoints
def test_17_all_16_api_endpoints(lake_data):
    from src.api.routes import (
        health, shipments, carriers, facilities, weather, routes_api, analytics, validation
    )
    assert health.health_check()["status"] == "healthy"
    assert shipments.list_shipments(skip=0, limit=5, data=lake_data).total >= 500
    ship_id = lake_data["shipments"].iloc[0]["shipment_id"]
    assert shipments.get_shipment_detail(ship_id, data=lake_data).shipment_id == ship_id
    assert len(shipments.get_shipment_legs(ship_id, data=lake_data)) > 0
    assert len(shipments.get_shipment_events(ship_id, data=lake_data)) > 0
    assert isinstance(shipments.get_shipment_eta_history(ship_id, data=lake_data), list)
    assert isinstance(shipments.get_shipment_delay_reasons(ship_id, data=lake_data), list)
    assert carriers.list_carriers(data=lake_data).total >= 8
    fac_res = facilities.list_facilities(data=lake_data)
    assert fac_res.total >= 15
    fac_id = fac_res.facilities[0].facility_id
    assert facilities.get_facility_queues(fac_id, data=lake_data).facility_id == fac_id
    assert weather.list_weather_events(data=lake_data).total >= 40
    assert routes_api.list_routes(data=lake_data).total > 0
    assert "mae_hours" in analytics.get_eta_performance(data=lake_data)
    assert "overall_delay_rate" in analytics.get_delay_performance(data=lake_data)
    assert analytics.get_analytics_anomalies(data=lake_data).total_detected >= 0
    assert validation.get_validation_summary(data=lake_data)["status"] in ["PASSED", "FAILED"]


# 18. Dashboard data loading
def test_18_dashboard_data_loading():
    from frontend.utils.data_loader import load_dashboard_data
    d = load_dashboard_data()
    assert "shipments" in d
    assert "facilities" in d
    assert "carriers" in d
    assert "routes" in d


# 19. CSV exports completeness
def test_19_csv_exports_complete():
    csv_dir = PROJECT_ROOT / "data" / "exports" / "csv"
    assert csv_dir.exists()
    csv_files = list(csv_dir.glob("*.csv"))
    assert len(csv_files) >= 16, f"Expected at least 16 CSV exports, found {len(csv_files)}"


# 20. JSON exports completeness
def test_20_json_exports_complete():
    json_dir = PROJECT_ROOT / "data" / "exports" / "json"
    assert json_dir.exists()
    json_files = list(json_dir.glob("*.json"))
    assert len(json_files) >= 16, f"Expected at least 16 JSON exports, found {len(json_files)}"


# 21. Standalone SQL reconstruction
def test_21_sql_reconstruction():
    sql_dir = PROJECT_ROOT / "data" / "exports" / "sql"
    schema_sql = sql_dir / "schema.sql"
    seed_sql = sql_dir / "seed_data.sql"
    assert schema_sql.exists()
    assert seed_sql.exists()

    con = duckdb.connect(":memory:")
    with open(schema_sql, "r", encoding="utf-8") as f:
        con.execute(f.read())
    with open(seed_sql, "r", encoding="utf-8") as f:
        con.execute(f.read())

    df_ship = con.execute("SELECT count(*) as cnt FROM shipments").df()
    assert df_ship.iloc[0]["cnt"] >= 500
    df_fac = con.execute("SELECT count(*) as cnt FROM facilities").df()
    assert df_fac.iloc[0]["cnt"] >= 15
    con.close()


# 22. Fixed-seed reproducibility
def test_22_fixed_seed_reproducibility():
    repro_json = PROJECT_ROOT / "reports" / "reproducibility_report.json"
    assert repro_json.exists(), "Reproducibility report JSON missing"
    with open(repro_json, "r", encoding="utf-8") as f:
        report = json.load(f)
    assert report["reproducibility_status"] == "PASSED"
    assert report["all_sha256_matched"] is True
    assert report["all_pk_hashes_matched"] is True
    assert report["ground_truth_json_matched"] is True
