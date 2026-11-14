"""Unit Tests for Feature Engineering & Point-in-Time Safety

Includes 8 mandatory regression tests verifying strict temporal filtering across all operational tables:
1. Event ingested before snapshot but occurring after snapshot (clock skew/anomaly).
2. Event occurring before snapshot but ingested after snapshot (un-ingested telemetry).
3. Valid delayed-ingestion event (occurred and ingested before snapshot).
4. Future queue observation.
5. Future weather observation / forecast.
6. Future route-change record.
7. Future carrier outcome (completed after snapshot).
8. Future disruption report.
"""
import pytest
import pandas as pd
from pathlib import Path
from src.features.asof import AsOfView
from src.data.loader import load_all_data

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FEATURES_CSV = PROJECT_ROOT / "data" / "processed" / "features.csv"


@pytest.fixture(scope="module")
def data():
    return load_all_data()


# ── Existing Point-in-Time Checks ──────────────────────────────────────────

def test_asof_view_temporal_boundary(data):
    asof = AsOfView(data)
    cutoff = pd.to_datetime("2026-08-01T00:00:00Z", utc=True)
    
    # Check first available shipment in dataset
    first_ship = data["shipments"]["shipment_id"].iloc[0]
    events = asof.get_tracking_events(first_ship, cutoff)
    for _, evt in events.iterrows():
        assert pd.to_datetime(evt["ingested_at"], utc=True) <= cutoff
        assert pd.to_datetime(evt["event_time"], utc=True) <= cutoff


def test_features_file_exists_and_valid():
    assert FEATURES_CSV.exists(), "Processed features.csv does not exist"
    df = pd.read_csv(FEATURES_CSV)
    assert len(df) > 1000
    assert "shipment_age_hours" in df.columns
    assert "planned_remaining_hours" in df.columns
    assert "carrier_on_time_rate" in df.columns
    
    # Assert raw actual timestamps not in features
    assert "actual_delivery_at" not in df.columns
    assert "actual_arrival_at" not in df.columns


# ── 8 Mandatory Regression Tests for Point-in-Time Boundary Safety ────────

def test_event_ingested_before_snapshot_but_occurring_after_snapshot():
    """
    Regression Test 1:
    An event with ingested_at <= cutoff but event_time > cutoff (e.g. clock skew,
    telemetry corruption, or injected synthetic anomaly).
    Old logic: Checked only ingested_at <= cutoff -> would erroneously return future event!
    New logic: Checks BOTH ingested_at <= cutoff AND event_time <= cutoff -> correctly filters it out.
    """
    cutoff = pd.to_datetime("2026-06-01T12:00:00Z", utc=True)
    fake_data = {
        "tracking_events": pd.DataFrame([{
            "event_id": "EVT-TEST-FUTURE-OCCUR",
            "shipment_id": "SHP-REGRESS-01",
            "event_type": "ARRIVED",
            "event_time": "2026-06-01T14:00:00Z",  # 2 hours in the future
            "ingested_at": "2026-06-01T10:00:00Z",  # ingested 2 hours in past
            "facility_id": "FAC-001"
        }])
    }
    asof = AsOfView(fake_data)
    res = asof.get_tracking_events("SHP-REGRESS-01", cutoff)
    assert len(res) == 0, "Future-occurring event must be strictly excluded even if ingested_at <= cutoff"


def test_event_occurring_before_snapshot_but_ingested_after_snapshot():
    """
    Regression Test 2:
    An event occurred before snapshot, but has NOT been ingested yet at snapshot time
    (ingested_at > cutoff).
    Must NOT be accessible to the model at snapshot_time.
    """
    cutoff = pd.to_datetime("2026-06-01T12:00:00Z", utc=True)
    fake_data = {
        "tracking_events": pd.DataFrame([{
            "event_id": "EVT-TEST-NOT-YET-INGESTED",
            "shipment_id": "SHP-REGRESS-02",
            "event_type": "DEPARTED",
            "event_time": "2026-06-01T10:00:00Z",   # occurred 2 hours prior
            "ingested_at": "2026-06-01T15:00:00Z",  # ingested 3 hours after cutoff
            "facility_id": "FAC-001"
        }])
    }
    asof = AsOfView(fake_data)
    res = asof.get_tracking_events("SHP-REGRESS-02", cutoff)
    assert len(res) == 0, "Event un-ingested at snapshot time must be excluded"


def test_valid_delayed_ingestion_event_included():
    """
    Regression Test 3:
    A legitimate delayed-ingestion event: occurred before cutoff AND ingested before cutoff,
    with ingested_at > event_time (latency = 3 hours).
    Must be successfully preserved.
    """
    cutoff = pd.to_datetime("2026-06-01T12:00:00Z", utc=True)
    fake_data = {
        "tracking_events": pd.DataFrame([{
            "event_id": "EVT-TEST-VALID-DELAYED",
            "shipment_id": "SHP-REGRESS-03",
            "event_type": "IN_TRANSIT",
            "event_time": "2026-06-01T08:00:00Z",   # occurred 4 hours prior
            "ingested_at": "2026-06-01T11:00:00Z",  # ingested 1 hour prior to cutoff
            "facility_id": "FAC-001"
        }])
    }
    asof = AsOfView(fake_data)
    res = asof.get_tracking_events("SHP-REGRESS-03", cutoff)
    assert len(res) == 1, "Legitimate delayed-ingestion event known at cutoff must be included"
    assert res.iloc[0]["event_id"] == "EVT-TEST-VALID-DELAYED"


def test_future_queue_observation():
    """
    Regression Test 4:
    Facility queue observation recorded or observed after cutoff must be excluded.
    Only queue states observed and ingested before cutoff are accessible.
    """
    cutoff = pd.to_datetime("2026-06-01T12:00:00Z", utc=True)
    fake_data = {
        "facility_queues": pd.DataFrame([
            {
                "facility_id": "FAC-QUEUE-01",
                "observed_at": "2026-06-01T11:00:00Z",
                "ingested_at": "2026-06-01T11:05:00Z",
                "queue_length": 12,
                "avg_wait_minutes": 25.0
            },
            {
                "facility_id": "FAC-QUEUE-01",
                "observed_at": "2026-06-01T13:00:00Z",  # Future observation
                "ingested_at": "2026-06-01T13:05:00Z",
                "queue_length": 80,
                "avg_wait_minutes": 120.0
            }
        ])
    }
    asof = AsOfView(fake_data)
    q = asof.get_facility_queue("FAC-QUEUE-01", cutoff)
    assert q is not None
    assert q["queue_length"] == 12, "Future queue observation must not overwrite current queue state"

    # Verify facility with ONLY future observations returns None
    fake_future_only = {
        "facility_queues": pd.DataFrame([{
            "facility_id": "FAC-FUTURE-ONLY",
            "observed_at": "2026-06-01T14:00:00Z",
            "ingested_at": "2026-06-01T14:05:00Z",
            "queue_length": 50,
        }])
    }
    asof_future = AsOfView(fake_future_only)
    assert asof_future.get_facility_queue("FAC-FUTURE-ONLY", cutoff) is None


def test_future_weather_observation():
    """
    Regression Test 5:
    Weather forecasts issued in the future must be excluded.
    Only forecasts issued and valid at or prior to snapshot time are accessible.
    """
    cutoff = pd.to_datetime("2026-06-01T12:00:00Z", utc=True)
    fake_data = {
        "weather_forecasts": pd.DataFrame([
            {
                "facility_id": "FAC-WTH-01",
                "issued_at": "2026-06-01T06:00:00Z",
                "valid_from": "2026-06-01T06:00:00Z",
                "valid_to": "2026-06-01T18:00:00Z",
                "precipitation_mm": 2.0,
                "condition": "CLEAR"
            },
            {
                "facility_id": "FAC-WTH-01",
                "issued_at": "2026-06-01T15:00:00Z",  # Issued in future
                "valid_from": "2026-06-01T15:00:00Z",
                "valid_to": "2026-06-02T03:00:00Z",
                "precipitation_mm": 55.0,
                "condition": "STORM"
            }
        ])
    }
    asof = AsOfView(fake_data)
    wf = asof.get_weather_forecast("FAC-WTH-01", cutoff)
    assert wf is not None
    assert wf["precipitation_mm"] == 2.0, "Must return forecast issued prior to cutoff, not future forecast"

    # Future-only forecast returns None
    future_only = {
        "weather_forecasts": pd.DataFrame([{
            "facility_id": "FAC-FUTURE-WTH",
            "issued_at": "2026-06-01T18:00:00Z",
            "valid_from": "2026-06-01T18:00:00Z",
            "valid_to": "2026-06-02T06:00:00Z",
            "precipitation_mm": 99.0
        }])
    }
    asof_wf_fut = AsOfView(future_only)
    assert asof_wf_fut.get_weather_forecast("FAC-FUTURE-WTH", cutoff) is None


def test_future_route_change_record():
    """
    Regression Test 6:
    Route changes recorded after cutoff must be excluded.
    """
    cutoff = pd.to_datetime("2026-06-01T12:00:00Z", utc=True)
    fake_data = {
        "route_changes": pd.DataFrame([
            {
                "shipment_id": "SHP-RTE-01",
                "change_id": "RC-01",
                "recorded_at": "2026-06-01T09:00:00Z",
                "reason": "INITIAL_REROUTE"
            },
            {
                "shipment_id": "SHP-RTE-01",
                "change_id": "RC-02",
                "recorded_at": "2026-06-01T16:00:00Z",  # Future route change
                "reason": "EMERGENCY_DETOUR"
            }
        ])
    }
    asof = AsOfView(fake_data)
    rc = asof.get_route_changes("SHP-RTE-01", cutoff)
    assert len(rc) == 1
    assert rc.iloc[0]["change_id"] == "RC-01", "Future route change must not be visible"


def test_future_carrier_outcome():
    """
    Regression Test 7:
    Carrier performance must only incorporate shipments whose delivery outcome
    completed BEFORE snapshot time (actual_delivery_at < cutoff).
    Shipments completing in the future must not leak into historical carrier statistics.
    """
    cutoff = pd.to_datetime("2026-06-01T12:00:00Z", utc=True)
    fake_data = {
        "shipments": pd.DataFrame([
            {
                "shipment_id": "SHP-PAST-01",
                "carrier_id": "CAR-001",
                "planned_delivery_at": "2026-05-30T10:00:00Z",
                "actual_delivery_at": "2026-05-30T09:30:00Z",  # Delivered on time in past
                "status": "DELIVERED"
            },
            {
                "shipment_id": "SHP-FUTURE-02",
                "carrier_id": "CAR-001",
                "planned_delivery_at": "2026-06-01T10:00:00Z",
                "actual_delivery_at": "2026-06-01T18:00:00Z",  # Delivered late in FUTURE
                "status": "DELIVERED"
            }
        ])
    }
    asof = AsOfView(fake_data)
    perf = asof.get_carrier_performance("CAR-001", cutoff)
    assert perf["carrier_sample_size"] == 1, "Carrier sample size must exclude future deliveries"


def test_future_disruption_report():
    """
    Regression Test 8:
    Disruptions reported or starting after cutoff must be excluded.
    """
    cutoff = pd.to_datetime("2026-06-01T12:00:00Z", utc=True)
    fake_data = {
        "disruptions": pd.DataFrame([
            {
                "facility_id": "FAC-DIS-01",
                "disruption_id": "DIS-PAST",
                "reported_at": "2026-06-01T08:00:00Z",
                "started_at": "2026-06-01T08:00:00Z",
                "ended_at": "2026-06-01T20:00:00Z",
                "severity": "HIGH"
            },
            {
                "facility_id": "FAC-DIS-01",
                "disruption_id": "DIS-FUTURE",
                "reported_at": "2026-06-01T14:00:00Z",  # Reported in future
                "started_at": "2026-06-01T15:00:00Z",
                "ended_at": "2026-06-01T22:00:00Z",
                "severity": "CRITICAL"
            }
        ])
    }
    asof = AsOfView(fake_data)
    dis = asof.get_disruptions("FAC-DIS-01", cutoff)
    assert len(dis) == 1
    assert dis.iloc[0]["disruption_id"] == "DIS-PAST", "Future disruption report must not be visible"


def test_expired_weather_forecast_excluded():
    """
    Regression Test 9:
    A weather forecast issued in the past whose valid window has expired (valid_to < cutoff)
    must NOT be returned as current weather at snapshot time.
    """
    cutoff = pd.to_datetime("2026-06-01T12:00:00Z", utc=True)
    fake_data = {
        "weather_forecasts": pd.DataFrame([
            {
                "facility_id": "FAC-EXP-01",
                "issued_at": "2026-05-25T06:00:00Z",
                "valid_from": "2026-05-25T06:00:00Z",
                "valid_to": "2026-05-25T18:00:00Z",  # Expired a week ago
                "precipitation_mm": 15.0,
                "severity": "MEDIUM",
                "is_disruptive": 1,
            }
        ])
    }
    asof = AsOfView(fake_data)
    wf = asof.get_weather_forecast("FAC-EXP-01", cutoff)
    assert wf is None, "Expired weather forecast must return None, not stale data"


def test_future_valid_weather_forecast_excluded():
    """
    Regression Test 10:
    A weather forecast issued prior to cutoff but whose validity starts in the future
    (valid_from > cutoff) must NOT be returned as current active weather at snapshot time.
    """
    cutoff = pd.to_datetime("2026-06-01T12:00:00Z", utc=True)
    fake_data = {
        "weather_forecasts": pd.DataFrame([
            {
                "facility_id": "FAC-FUTVAL-01",
                "issued_at": "2026-06-01T10:00:00Z",   # Issued 2 hours ago
                "valid_from": "2026-06-01T14:00:00Z",  # Valid starting 2 hours in FUTURE
                "valid_to": "2026-06-02T02:00:00Z",
                "precipitation_mm": 35.0,
                "severity": "HIGH",
                "is_disruptive": 1,
            }
        ])
    }
    asof = AsOfView(fake_data)
    wf = asof.get_weather_forecast("FAC-FUTVAL-01", cutoff)
    assert wf is None, "Forecast valid only in the future must return None for current snapshot conditions"


def test_target_separation_strictly_enforced():
    """
    Regression Test 11:
    Model training features must never contain ground-truth target columns or post-outcome timestamps.
    """
    from src.models.evaluate_comprehensive import ALL_FEATURE_COLS, BASE_FEATURE_COLS
    from src.features.feature_validator import validate_target_separation, FORBIDDEN_TARGET_COLS
    
    # 1. Direct inclusion test
    for col in FORBIDDEN_TARGET_COLS:
        assert col not in ALL_FEATURE_COLS, f"Target column '{col}' leaked into ALL_FEATURE_COLS!"
        assert col not in BASE_FEATURE_COLS, f"Target column '{col}' leaked into BASE_FEATURE_COLS!"

    # 2. Validator function test
    res = validate_target_separation(ALL_FEATURE_COLS)
    assert res["status"] == "PASSED"
    assert len(res["leaked_target_columns"]) == 0



