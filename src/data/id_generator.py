"""Deterministic ID Conventions Module
Adheres strictly to Master Build Specifications for Logistics Platform:
- Shipment: SHP-2026-000001
- ShipmentLeg: LEG-SHP-2026-000001-01
- TrackingEvent: EVT-SHP-2026-000001-000001
- ETAEstimate: ETA-SHP-2026-000001-YYYYMMDDHHMMSS
- DelayReason: DLY-2026-000001
- Route: RTE-2026-000001
- Facility: FAC-2026-000001
- Carrier: CAR-2026-000001
- FacilityQueue: QUE-2026-000001
- WeatherEvent: WTH-2026-000001
- CarrierCalendar: CCAL-2026-000001
- FacilityCalendar: FCAL-2026-000001
- ShipmentStatusHistory: SSH-2026-000001
- RouteChangeHistory: RCH-2026-000001
- ShipmentDelayReason: SDR-2026-000001
- Anomaly: ANOM-2026-000001
"""

from datetime import datetime
import pandas as pd


YEAR_PREFIX = "2026"


def format_shipment_id(seq: int) -> str:
    """Format: SHP-2026-000001"""
    return f"SHP-{YEAR_PREFIX}-{seq:06d}"


def format_leg_id(shipment_id: str, leg_seq: int) -> str:
    """Format: LEG-SHP-2026-000001-01"""
    return f"LEG-{shipment_id}-{leg_seq:02d}"


def format_tracking_event_id(shipment_id: str, event_seq: int) -> str:
    """Format: EVT-SHP-2026-000001-000001"""
    return f"EVT-{shipment_id}-{event_seq:06d}"


def format_eta_id(shipment_id: str, snap_time: datetime | pd.Timestamp | str) -> str:
    """Format: ETA-SHP-2026-000001-20261022103000"""
    if isinstance(snap_time, str):
        snap_time = pd.to_datetime(snap_time, utc=True)
    ts_str = snap_time.strftime("%Y%m%d%H%M%S")
    return f"ETA-{shipment_id}-{ts_str}"


def format_delay_reason_id(seq: int) -> str:
    """Format: DLY-2026-000001"""
    return f"DLY-{YEAR_PREFIX}-{seq:06d}"


def format_route_id(seq: int) -> str:
    """Format: RTE-2026-000001"""
    return f"RTE-{YEAR_PREFIX}-{seq:06d}"


def format_facility_id(seq: int) -> str:
    """Format: FAC-2026-000001"""
    return f"FAC-{YEAR_PREFIX}-{seq:06d}"


def format_carrier_id(seq: int) -> str:
    """Format: CAR-2026-000001"""
    return f"CAR-{YEAR_PREFIX}-{seq:06d}"


def format_queue_id(seq: int) -> str:
    """Format: QUE-2026-000001"""
    return f"QUE-{YEAR_PREFIX}-{seq:06d}"


def format_weather_id(seq: int) -> str:
    """Format: WTH-2026-000001"""
    return f"WTH-{YEAR_PREFIX}-{seq:06d}"


def format_carrier_cal_id(seq: int) -> str:
    """Format: CCAL-2026-000001"""
    return f"CCAL-{YEAR_PREFIX}-{seq:06d}"


def format_facility_cal_id(seq: int) -> str:
    """Format: FCAL-2026-000001"""
    return f"FCAL-{YEAR_PREFIX}-{seq:06d}"


def format_status_history_id(seq: int) -> str:
    """Format: SSH-2026-000001"""
    return f"SSH-{YEAR_PREFIX}-{seq:06d}"


def format_route_change_id(seq: int) -> str:
    """Format: RCH-2026-000001"""
    return f"RCH-{YEAR_PREFIX}-{seq:06d}"


def format_shipment_delay_reason_id(seq: int) -> str:
    """Format: SDR-2026-000001"""
    return f"SDR-{YEAR_PREFIX}-{seq:06d}"


def format_anomaly_id(seq: int) -> str:
    """Format: ANOM-2026-000001"""
    return f"ANOM-{YEAR_PREFIX}-{seq:06d}"

