"""Unit Tests for Data Loader, Validator, and Repository"""
import pytest
from src.data.loader import load_all_data
from src.data.validator import DataValidator
from src.data.normalizer import normalize_all_data
from src.data.repository import LogisticsRepository


@pytest.fixture(scope="module")
def raw_data():
    return load_all_data()


def test_load_all_tables_present(raw_data):
    expected_tables = [
        "carriers", "facilities", "shipments", "shipment_legs",
        "tracking_events", "eta_snapshots", "facility_queues",
        "weather_forecasts", "weather_observations", "route_changes",
        "disruptions", "ground_truth_anomalies"
    ]
    for table in expected_tables:
        assert table in raw_data, f"Table {table} missing from loader"
        assert len(raw_data[table]) > 0, f"Table {table} is empty"


def test_primary_keys_unique(raw_data):
    validator = DataValidator(raw_data)
    validator.validate_primary_keys()
    pk_issues = [i for i in validator.report.issues if i.rule == "PRIMARY_KEY_UNIQUE"]
    assert len(pk_issues) == 0, f"Primary key violations found: {pk_issues}"


def test_foreign_key_referential_integrity(raw_data):
    validator = DataValidator(raw_data)
    validator.validate_foreign_keys()
    fk_issues = [i for i in validator.report.issues if i.rule.startswith("FK_")]
    assert len(fk_issues) == 0, f"Foreign key integrity violations: {fk_issues}"


def test_duckdb_storage_and_query(raw_data):
    normalized = normalize_all_data(raw_data)
    repo = LogisticsRepository()
    repo.initialize_database(normalized)
    
    df = repo.query_df("SELECT count(*) as count FROM shipments")
    assert df.iloc[0]["count"] >= 500

