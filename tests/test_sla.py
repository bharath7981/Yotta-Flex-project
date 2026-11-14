"""SLA Tests — covers all required edge cases per Phase 2 spec."""

import pytest
import pandas as pd
from datetime import datetime, timedelta, timezone
from src.data.sla import (
    get_sla_rule, get_promised_delivery, is_sla_breached,
    compute_sla_columns, SLA_RULES
)


def ts(dt: datetime) -> pd.Timestamp:
    return pd.Timestamp(dt.replace(tzinfo=timezone.utc))


BASE = datetime(2026, 1, 1, 0, 0, 0)


# ── get_sla_rule ────────────────────────────────────────────────────────────

def test_sla_rules_all_levels():
    for level in ["PRIORITY", "EXPRESS", "STANDARD", "ECONOMY"]:
        rule = get_sla_rule(level)
        assert "promised_hours" in rule
        assert "grace_hours" in rule
        assert rule["promised_hours"] > 0
        assert rule["grace_hours"] >= 0


def test_sla_rule_case_insensitive():
    assert get_sla_rule("priority") == get_sla_rule("PRIORITY")
    assert get_sla_rule("Express") == get_sla_rule("EXPRESS")


def test_sla_rule_unknown_level_returns_default():
    rule = get_sla_rule("UNKNOWN_TIER")
    assert rule["promised_hours"] > 0  # falls back to default


# ── get_promised_delivery ───────────────────────────────────────────────────

def test_promised_delivery_priority():
    created = ts(BASE)
    promised = get_promised_delivery(created, "PRIORITY")
    expected = created + timedelta(hours=24)
    assert promised == expected


def test_promised_delivery_economy():
    created = ts(BASE)
    promised = get_promised_delivery(created, "ECONOMY")
    expected = created + timedelta(hours=168)
    assert promised == expected


# ── is_sla_breached ─────────────────────────────────────────────────────────

def _setup_express():
    created = ts(BASE)
    rule = get_sla_rule("EXPRESS")
    promised = get_promised_delivery(created, "EXPRESS")
    grace = rule["grace_hours"]
    return promised, grace


def test_exactly_at_promised_delivery():
    """Exactly at promised delivery time — within grace, so NOT a breach."""
    promised, grace = _setup_express()
    actual = promised  # exactly on time
    result = is_sla_breached(actual, promised, grace, "DELIVERED")
    assert result == 0, "Delivery exactly at promised time should NOT breach SLA"


def test_exactly_at_grace_boundary():
    """Exactly at grace-period boundary — still on time."""
    promised, grace = _setup_express()
    actual = promised + timedelta(hours=grace)  # exactly at deadline
    result = is_sla_breached(actual, promised, grace, "DELIVERED")
    assert result == 0, "Delivery exactly at grace boundary should NOT breach SLA"


def test_one_minute_after_grace():
    """1 minute after grace period ends — BREACH."""
    promised, grace = _setup_express()
    actual = promised + timedelta(hours=grace) + timedelta(minutes=1)
    result = is_sla_breached(actual, promised, grace, "DELIVERED")
    assert result == 1, "Delivery 1 minute after grace should breach SLA"


def test_early_delivery():
    """Delivered before promised time — no breach."""
    promised, grace = _setup_express()
    actual = promised - timedelta(hours=5)
    result = is_sla_breached(actual, promised, grace, "DELIVERED")
    assert result == 0, "Early delivery should not breach SLA"


def test_delayed_delivery():
    """Delivered well after grace — definite breach."""
    promised, grace = _setup_express()
    actual = promised + timedelta(hours=grace + 10)
    result = is_sla_breached(actual, promised, grace, "DELIVERED")
    assert result == 1, "Delivery 10h after grace should breach SLA"


def test_unresolved_shipment():
    """No actual delivery time, status IN_TRANSIT — result must be None."""
    promised, grace = _setup_express()
    result = is_sla_breached(None, promised, grace, "IN_TRANSIT")
    assert result is None, "Unresolved shipment SLA breach must be None"


def test_cancelled_shipment():
    """Cancelled shipment — excluded from SLA measurement."""
    promised, grace = _setup_express()
    actual = promised + timedelta(hours=100)  # would be a breach if measured
    result = is_sla_breached(actual, promised, grace, "CANCELLED")
    assert result is None, "Cancelled shipment must not be classified as breached"


# ── compute_sla_columns ─────────────────────────────────────────────────────

def _make_shipment_row(service_level, status, actual_offset_hours=None):
    """Helper: build a minimal shipment DataFrame row."""
    created = BASE
    rows = [{
        "shipment_id": "SHP-TEST",
        "service_level": service_level,
        "created_at": ts(created).isoformat(),
        "planned_delivery_at": ts(created + timedelta(hours=48)).isoformat(),
        "actual_delivery_at": (
            ts(created + timedelta(hours=actual_offset_hours)).isoformat()
            if actual_offset_hours is not None else None
        ),
        "current_status": status,
    }]
    return pd.DataFrame(rows)


def test_compute_sla_columns_breach():
    df = _make_shipment_row("EXPRESS", "DELIVERED", actual_offset_hours=50)  # 50h > 48+1=49h
    result = compute_sla_columns(df)
    assert result.iloc[0]["is_sla_breached"] == 1


def test_compute_sla_columns_no_breach():
    df = _make_shipment_row("EXPRESS", "DELIVERED", actual_offset_hours=48)  # 48h < 49h
    result = compute_sla_columns(df)
    assert result.iloc[0]["is_sla_breached"] == 0


def test_compute_sla_columns_unresolved():
    df = _make_shipment_row("STANDARD", "IN_TRANSIT", actual_offset_hours=None)
    result = compute_sla_columns(df)
    assert pd.isna(result.iloc[0]["is_sla_breached"])


def test_compute_sla_columns_cancelled():
    df = _make_shipment_row("PRIORITY", "CANCELLED", actual_offset_hours=50)
    result = compute_sla_columns(df)
    assert pd.isna(result.iloc[0]["is_sla_breached"])


def test_compute_sla_columns_adds_promised_delivery():
    df = _make_shipment_row("STANDARD", "DELIVERED", actual_offset_hours=100)
    result = compute_sla_columns(df)
    rule = get_sla_rule("STANDARD")
    expected_promised = ts(BASE) + timedelta(hours=rule["promised_hours"])
    assert result.iloc[0]["promised_delivery_at"] == expected_promised

