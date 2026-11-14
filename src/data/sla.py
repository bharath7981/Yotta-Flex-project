"""SLA (Service Level Agreement) Rules Module
Single authoritative source for promised delivery time and SLA breach logic.

Business Rules:
  PRIORITY : promised = created_at + 24h,  grace = 0.5h
  EXPRESS  : promised = created_at + 48h,  grace = 1.0h
  STANDARD : promised = created_at + 120h, grace = 2.0h
  ECONOMY  : promised = created_at + 168h, grace = 4.0h

SLA breach definition:
  A DELIVERED shipment breaches SLA when:
    actual_delivery_at > promised_delivery_at + grace_hours

  An unresolved shipment (no actual_delivery_at, status not CANCELLED/DELIVERED)
  is NOT classified as non-delayed — it is left as NULL/unknown.

  A CANCELLED shipment is excluded from SLA breach classification.
"""

from datetime import timedelta
from typing import Optional
import pandas as pd

SLA_RULES = {
    "PRIORITY": {"promised_hours": 24,  "grace_hours": 0.5},
    "EXPRESS":  {"promised_hours": 48,  "grace_hours": 1.0},
    "STANDARD": {"promised_hours": 120, "grace_hours": 2.0},
    "ECONOMY":  {"promised_hours": 168, "grace_hours": 4.0},
}

# Fallback for unknown service levels
_DEFAULT_SLA = {"promised_hours": 120, "grace_hours": 2.0}


def get_sla_rule(service_level: str) -> dict:
    """Return SLA rule dict for a given service level (case-insensitive)."""
    return SLA_RULES.get(str(service_level).upper().strip(), _DEFAULT_SLA)


def get_promised_delivery(created_at: pd.Timestamp, service_level: str) -> pd.Timestamp:
    """Compute the promised delivery timestamp from creation time and service level."""
    rule = get_sla_rule(service_level)
    return created_at + timedelta(hours=rule["promised_hours"])


def is_sla_breached(
    actual_delivery_at: Optional[pd.Timestamp],
    promised_delivery_at: pd.Timestamp,
    grace_hours: float,
    status: str,
) -> Optional[int]:
    """
    Determine whether an SLA breach occurred.

    Returns:
        1  — SLA breached (delivered late beyond grace period)
        0  — SLA met (delivered on time or within grace)
        None — Unresolvable (not yet delivered, or cancelled)

    Rules:
        CANCELLED => None (excluded from SLA measurement)
        actual_delivery_at is NaT / None => None (outcome unknown)
        actual > promised + grace => 1 (breach)
        else => 0 (on time or within grace)
    """
    status_upper = str(status).upper().strip()
    if status_upper == "CANCELLED":
        return None

    if actual_delivery_at is None or pd.isna(actual_delivery_at):
        return None  # Unresolved — cannot determine breach

    deadline = promised_delivery_at + timedelta(hours=grace_hours)
    return int(actual_delivery_at > deadline)


def compute_sla_columns(shipments: pd.DataFrame) -> pd.DataFrame:
    """
    Add SLA columns to the shipments DataFrame.

    Added columns:
        promised_delivery_at   — absolute promised delivery timestamp
        grace_hours            — grace period in hours for this service level
        is_sla_breached        — 1=breach, 0=on-time, None=unknown/cancelled
        hours_to_sla_deadline  — hours from created_at to promised+grace
        sla_breach_hours       — how many hours late (positive=late, negative=early);
                                 NaN for unresolved/cancelled
    """
    df = shipments.copy()

    # Parse timestamps with UTC awareness
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
    df["planned_delivery_at"] = pd.to_datetime(df["planned_delivery_at"], utc=True)
    df["actual_delivery_at"] = pd.to_datetime(df["actual_delivery_at"], utc=True, errors="coerce")

    def _apply_sla(row):
        rule = get_sla_rule(row["service_level"])
        promised = get_promised_delivery(row["created_at"], row["service_level"])
        grace = rule["grace_hours"]
        breach = is_sla_breached(
            actual_delivery_at=row["actual_delivery_at"],
            promised_delivery_at=promised,
            grace_hours=grace,
            status=row["current_status"],
        )

        # Hours from actual to SLA deadline (positive = early/on-time)
        if pd.notna(row["actual_delivery_at"]):
            deadline = promised + timedelta(hours=grace)
            breach_hours = (row["actual_delivery_at"] - deadline).total_seconds() / 3600.0
        else:
            breach_hours = float("nan")

        return pd.Series({
            "promised_delivery_at": promised,
            "grace_hours": grace,
            "is_sla_breached": breach,
            "sla_breach_hours": breach_hours,
        })

    sla_cols = df.apply(_apply_sla, axis=1)
    df["promised_delivery_at"] = sla_cols["promised_delivery_at"]
    df["grace_hours"] = sla_cols["grace_hours"]
    df["is_sla_breached"] = sla_cols["is_sla_breached"]
    df["sla_breach_hours"] = sla_cols["sla_breach_hours"]

    return df

