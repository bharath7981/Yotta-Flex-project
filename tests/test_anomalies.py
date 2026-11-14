"""Unit Tests for Anomaly Detection, Edge Cases, and Ground Truth Benchmarking"""
import pytest
import pandas as pd
from datetime import datetime, timezone
from src.anomaly.detectors import AnomalyDetector
from src.anomaly.evaluator import evaluate_anomalies
from src.data.loader import load_all_data


@pytest.fixture(scope="module")
def data():
    return load_all_data()


def test_four_anomaly_detectors(data):
    det = AnomalyDetector(data)
    
    a1 = det.detect_ingestion_confusion()
    assert len(a1) == 20, f"Expected 20 ingestion anomalies, found {len(a1)}"
    
    a2 = det.detect_impossible_route()
    assert len(a2) == 15, f"Expected 15 impossible route anomalies, found {len(a2)}"
    
    a3 = det.detect_future_leakage()
    assert len(a3) == 15, f"Expected 15 future leakage anomalies, found {len(a3)}"
    
    a4 = det.detect_delivered_but_intransit()
    assert len(a4) == 10, f"Expected 10 delivered-intransit anomalies, found {len(a4)}"


def test_ground_truth_benchmark_evaluation(data):
    det = AnomalyDetector(data)
    detected_df = det.run_all_detectors()
    gt_df = data["ground_truth_anomalies"]
    
    eval_res = evaluate_anomalies(detected_df, gt_df)
    assert eval_res["overall"]["precision"] == 1.0
    assert eval_res["overall"]["recall"] == 1.0
    assert eval_res["overall"]["f1_score"] == 1.0


# ── Negative & Near-Miss Boundary Tests ──────────────────────────────────────

def test_ingestion_boundary_near_miss():
    """Event where ingested_at == event_time is NOT an anomaly."""
    clean_events = pd.DataFrame([{
        "event_id": "EVT-CLEAN-01",
        "shipment_id": "SHP-001",
        "event_type": "DEPARTURE",
        "event_time": "2026-06-01T12:00:00Z",
        "ingested_at": "2026-06-01T12:00:00Z",  # exact same timestamp
    }])
    mock_data = {"tracking_events": clean_events}
    det = AnomalyDetector(mock_data)
    anomalies = det.detect_ingestion_confusion()
    assert len(anomalies) == 0, "Exact timestamp match should not flag ingestion confusion"


def test_single_leg_route_not_flagged():
    """Single leg shipment cannot have route order discontinuity."""
    single_leg = pd.DataFrame([{
        "leg_id": "LEG-SINGLE",
        "shipment_id": "SHP-SINGLE",
        "leg_sequence": 1,
        "origin_facility_id": "FAC-001",
        "destination_facility_id": "FAC-002",
        "leg_status": "COMPLETED",
    }])
    mock_data = {"shipment_legs": single_leg}
    det = AnomalyDetector(mock_data)
    anomalies = det.detect_impossible_route()
    assert len(anomalies) == 0, "Single-leg shipment should not flag route discontinuity"


def test_cancelled_legs_excluded_from_continuity():
    """Legs marked CANCELLED should not cause broken continuity in active chain."""
    legs = pd.DataFrame([
        {
            "leg_id": "LEG-01", "shipment_id": "SHP-CANC", "leg_sequence": 1,
            "origin_facility_id": "FAC-001", "destination_facility_id": "FAC-002",
            "leg_status": "COMPLETED"
        },
        {
            "leg_id": "LEG-02-CANC", "shipment_id": "SHP-CANC", "leg_sequence": 2,
            "origin_facility_id": "FAC-999", "destination_facility_id": "FAC-888",
            "leg_status": "CANCELLED"
        },
        {
            "leg_id": "LEG-03", "shipment_id": "SHP-CANC", "leg_sequence": 3,
            "origin_facility_id": "FAC-002", "destination_facility_id": "FAC-003",
            "leg_status": "COMPLETED"
        },
    ])
    mock_data = {"shipment_legs": legs}
    det = AnomalyDetector(mock_data)
    anomalies = det.detect_impossible_route()
    assert len(anomalies) == 0, "Cancelled intermediate leg should be excluded from active chain check"


def test_future_leakage_boundary_near_miss():
    """Snapshot where max_ingested_at_used == snapshot_time is NOT leakage."""
    clean_etas = pd.DataFrame([{
        "eta_id": "ETA-CLEAN",
        "shipment_id": "SHP-001",
        "snapshot_time": "2026-06-01T15:00:00Z",
        "max_ingested_at_used": "2026-06-01T15:00:00Z",  # exact boundary
        "data_cutoff_at": "2026-06-01T15:00:00Z",
    }])
    mock_data = {"eta_snapshots": clean_etas}
    det = AnomalyDetector(mock_data)
    anomalies = det.detect_future_leakage()
    assert len(anomalies) == 0, "Exact boundary cutoff should not flag future leakage"


def test_delivered_state_consistency_clean():
    """Shipment marked DELIVERED with DELIVERED event is consistent (NOT anomalous)."""
    shipments = pd.DataFrame([{
        "shipment_id": "SHP-DELIV-OK",
        "current_status": "DELIVERED",
        "actual_delivery_at": "2026-06-02T10:00:00Z",
    }])
    events = pd.DataFrame([{
        "event_id": "EVT-DELIV-OK",
        "shipment_id": "SHP-DELIV-OK",
        "event_type": "DELIVERED",
    }])
    mock_data = {"shipments": shipments, "tracking_events": events}
    det = AnomalyDetector(mock_data)
    anomalies = det.detect_delivered_but_intransit()
    assert len(anomalies) == 0, "Properly marked DELIVERED shipment should not flag mismatch"
