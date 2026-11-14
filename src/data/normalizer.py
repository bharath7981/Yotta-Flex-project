"""Data Normalizer Module
Enriches and normalizes logistics data structures:
- Computes actual delay hours and delay flags for delivered shipments
- Computes SLA breach status using authoritative SLA rules (src/data/sla.py)
- Standardizes categorical variables

SLA breach definition (documented in src/data/sla.py):
  promised_delivery_at = created_at + SLA_RULES[service_level]["promised_hours"]
  deadline = promised_delivery_at + grace_hours
  is_sla_breached = (actual_delivery_at > deadline) for DELIVERED shipments;
                     None for unresolved or CANCELLED.
"""

from typing import Dict
import pandas as pd

from src.data.sla import compute_sla_columns


def normalize_all_data(raw_data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """Normalize and enrich raw datasets."""
    data = {k: v.copy() for k, v in raw_data.items()}

    # ── Normalize Shipments ──────────────────────────────────────────────────
    shipments = data["shipments"]

    # Parse timestamps
    shipments["created_at"] = pd.to_datetime(shipments["created_at"], utc=True)
    shipments["planned_delivery_at"] = pd.to_datetime(shipments["planned_delivery_at"], utc=True)
    shipments["actual_delivery_at"] = pd.to_datetime(
        shipments["actual_delivery_at"], utc=True, errors="coerce"
    )

    # Delivery indicator
    delivered_mask = shipments["actual_delivery_at"].notna()
    shipments["is_delivered"] = delivered_mask

    # Raw delay (actual vs planned) — kept for historical comparison only
    shipments["delay_hours"] = None
    shipments["is_delayed"] = False
    if delivered_mask.any():
        actual_delay = (
            shipments.loc[delivered_mask, "actual_delivery_at"] -
            shipments.loc[delivered_mask, "planned_delivery_at"]
        ).dt.total_seconds() / 3600.0
        shipments.loc[delivered_mask, "delay_hours"] = actual_delay
        shipments.loc[delivered_mask, "is_delayed"] = actual_delay > 0.0

    # Delay severity category
    def categorize_delay(hours):
        if hours is None or pd.isna(hours):
            return "ON_TIME"
        if hours <= 0:
            return "ON_TIME"
        elif hours <= 4:
            return "MINOR"
        elif hours <= 12:
            return "MODERATE"
        elif hours <= 24:
            return "SEVERE"
        else:
            return "CRITICAL"

    shipments["delay_class"] = shipments["delay_hours"].apply(categorize_delay)

    # ── SLA breach computation (AUTHORITATIVE) ───────────────────────────────
    # Uses per-service-level promised hours + grace periods from sla.py
    sla_df = compute_sla_columns(shipments)
    shipments["promised_delivery_at"] = sla_df["promised_delivery_at"]
    shipments["grace_hours"] = sla_df["grace_hours"]
    shipments["is_sla_breached"] = sla_df["is_sla_breached"]
    shipments["sla_breach_hours"] = sla_df["sla_breach_hours"]

    data["shipments"] = shipments

    # ── Normalize Tracking Events ────────────────────────────────────────────
    events = data["tracking_events"]
    events["event_type"] = events["event_type"].str.upper().str.strip()

    # ── Normalize Shipment Legs ──────────────────────────────────────────────
    legs = data["shipment_legs"]
    legs["transport_mode"] = legs["transport_mode"].str.upper().str.strip()

    return data
