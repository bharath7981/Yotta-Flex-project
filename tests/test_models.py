"""Unit Tests for ETA and Delay Prediction Models"""
import pytest
import pandas as pd
from src.models.predict_eta import get_prediction_service, assign_risk_category
from src.models.model_registry import list_models


def test_models_exist_in_registry():
    models = list_models()
    assert "eta_regressor" in models
    assert "delay_classifier" in models


def test_prediction_service_outputs():
    service = get_prediction_service()
    dummy_features = pd.DataFrame([{
        "shipment_id": "SHP-00001",
        "eta_id": "ETA-TEST",
        "snapshot_time": "2026-08-01T12:00:00Z",
        "shipment_age_hours": 10.0,
        "num_legs": 3,
        "weight_kg": 150.0,
        "distance_km": 800.0,
        "planned_transit_hours": 48.0,
        "planned_remaining_hours": 38.0,
        "completed_legs": 1,
        "remaining_legs": 2,
        "progress_pct": 0.33,
        "hours_since_last_event": 2.5,
        "missing_expected_scans": 0,
        "carrier_on_time_rate": 0.88,
        "carrier_avg_delay": 4.5,
        "carrier_reliability": 0.90,
        "current_queue_length": 15,
        "avg_wait_minutes": 20,
        "facility_utilization": 0.50,
        "facility_disrupted": 0,
        "precipitation_mm": 0.0,
        "wind_speed_kmh": 12.0,
        "weather_disruptive": 0,
        "route_changes_count": 0
    }])

    eta_res = service.predict_eta(dummy_features)
    assert len(eta_res) == 1
    assert eta_res.iloc[0]["predicted_remaining_hours"] >= 0

    risk_res = service.predict_delay_risk(dummy_features)
    assert len(risk_res) == 1
    assert 0.0 <= risk_res.iloc[0]["delay_probability"] <= 1.0
    assert risk_res.iloc[0]["delay_risk"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def test_assign_risk_category():
    assert assign_risk_category(0.10) == "LOW"
    assert assign_risk_category(0.35) == "MEDIUM"
    assert assign_risk_category(0.60) == "HIGH"
    assert assign_risk_category(0.85) == "CRITICAL"

