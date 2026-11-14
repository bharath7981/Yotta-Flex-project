"""As-Of Temporal Filtering Module
Provides Point-in-Time view helpers to prevent future data leakage.
Filters datasets strictly by knowledge available at a specific snapshot timestamp.

Key principle:
  Every method filters by BOTH the wall-clock occurrence time AND the ingestion/
  availability time, ensuring the view reflects only information that could
  physically have been known at `as_of_time`.

Carrier performance:
  Computed from COMPLETED shipments (actual_delivery_at is known) that completed
  BEFORE as_of_time, excluding the current shipment. Uses Bayesian smoothing
  with a minimum sample size to avoid extreme estimates for rarely-used carriers.
"""

from typing import Dict, Optional
import numpy as np
import pandas as pd


# Minimum completed shipments before we trust carrier stats (Bayesian shrinkage)
_CARRIER_MIN_SAMPLES = 5
_CARRIER_GLOBAL_ON_TIME_RATE = 0.80   # prior mean for on-time rate
_CARRIER_GLOBAL_AVG_DELAY = 10.0      # prior mean for avg delay hours


class AsOfView:
    """Helper to query operational tables strictly as of a cutoff timestamp."""

    def __init__(self, data: Dict[str, pd.DataFrame]):
        self.data = data
        self._pre_index()

    @staticmethod
    def _to_dt(val):
        return pd.to_datetime(val, utc=True)

    def _pre_index(self):
        """Pre-parse datetimes and index tables by entity for high-throughput temporal slicing."""
        # 1. Tracking events
        if "tracking_events" in self.data and not self.data["tracking_events"].empty:
            te = self.data["tracking_events"].copy()
            te["_ingested_dt"] = pd.to_datetime(te["ingested_at"], utc=True)
            te["_event_dt"] = pd.to_datetime(te["event_time"], utc=True)
            self._events_by_ship = dict(tuple(te.groupby("shipment_id")))
        else:
            self._events_by_ship = {}

        # 2. Facility queues
        if "facility_queues" in self.data and not self.data["facility_queues"].empty:
            fq = self.data["facility_queues"].copy()
            fq["_observed_dt"] = pd.to_datetime(fq["observed_at"], utc=True)
            fq["_ingested_dt"] = pd.to_datetime(fq["ingested_at"], utc=True)
            self._queues_by_fac = {
                f_id: group.sort_values("_observed_dt")
                for f_id, group in fq.groupby("facility_id")
            }
        else:
            self._queues_by_fac = {}

        # 3. Weather forecasts
        if "weather_forecasts" in self.data and not self.data["weather_forecasts"].empty:
            wf = self.data["weather_forecasts"].copy()
            wf["_issued_dt"] = pd.to_datetime(wf["issued_at"], utc=True)
            wf["_valid_from_dt"] = pd.to_datetime(wf["valid_from"], utc=True)
            wf["_valid_to_dt"] = pd.to_datetime(wf["valid_to"], utc=True)
            self._wf_by_fac = {
                f_id: group.sort_values("_issued_dt")
                for f_id, group in wf.groupby("facility_id")
            }
        else:
            self._wf_by_fac = {}

        # 4. Route changes
        if "route_changes" in self.data and not self.data["route_changes"].empty:
            rc = self.data["route_changes"].copy()
            rc["_recorded_dt"] = pd.to_datetime(rc["recorded_at"], utc=True)
            self._rc_by_ship = dict(tuple(rc.groupby("shipment_id")))
        else:
            self._rc_by_ship = {}

        # 5. Disruptions
        if "disruptions" in self.data and not self.data["disruptions"].empty:
            dis = self.data["disruptions"].copy()
            dis["_reported_dt"] = pd.to_datetime(dis["reported_at"], utc=True)
            dis["_started_dt"] = pd.to_datetime(dis["started_at"], utc=True)
            dis["_ended_dt"] = pd.to_datetime(dis["ended_at"], utc=True)
            self._dis_by_fac = dict(tuple(dis.groupby("facility_id")))
        else:
            self._dis_by_fac = {}

        # 6. Completed shipments by carrier (pre-sorted by actual_delivery_at)
        if "shipments" in self.data and not self.data["shipments"].empty:
            shipments = self.data["shipments"].copy()
            actual_dt = pd.to_datetime(shipments["actual_delivery_at"], utc=True, errors="coerce")
            planned_dt = pd.to_datetime(shipments["planned_delivery_at"], utc=True, errors="coerce")
            mask_done = actual_dt.notna()
            completed = shipments[mask_done].copy()
            completed["_actual_dt"] = actual_dt[mask_done]
            completed["_delay_hours"] = (actual_dt[mask_done] - planned_dt[mask_done]).dt.total_seconds() / 3600.0
            completed["_is_on_time"] = (completed["_delay_hours"] <= 0).astype(int)
            self._completed_by_carrier = {
                c_id: group.sort_values("_actual_dt")
                for c_id, group in completed.groupby("carrier_id")
            }
        else:
            self._completed_by_carrier = {}

    # ── Tracking Events ─────────────────────────────────────────────────────

    def get_tracking_events(self, shipment_id: str, as_of_time: pd.Timestamp) -> pd.DataFrame:
        as_of_time = self._to_dt(as_of_time)
        events = self._events_by_ship.get(shipment_id)
        if events is None or events.empty:
            return pd.DataFrame(columns=self.data["tracking_events"].columns)
        # Require BOTH ingested_at <= as_of_time AND event_time <= as_of_time
        # to prevent future occurrence leakage while preserving legitimate delayed ingestion
        mask = (events["_ingested_dt"] <= as_of_time) & (events["_event_dt"] <= as_of_time)
        return events[mask].sort_values("ingested_at")

    # ── Facility Queues ─────────────────────────────────────────────────────

    def get_facility_queue(self, facility_id: str, as_of_time: pd.Timestamp) -> Optional[pd.Series]:
        as_of_time = self._to_dt(as_of_time)
        queues = self._queues_by_fac.get(facility_id)
        if queues is None or queues.empty:
            return None
        mask = (queues["_observed_dt"] <= as_of_time) & (queues["_ingested_dt"] <= as_of_time)
        subset = queues[mask]
        if subset.empty:
            return None
        return subset.iloc[-1]

    # ── Weather Forecasts ───────────────────────────────────────────────────

    def get_weather_forecast(self, facility_id: str, as_of_time: pd.Timestamp) -> Optional[pd.Series]:
        as_of_time = self._to_dt(as_of_time)
        wf = self._wf_by_fac.get(facility_id)
        if wf is None or wf.empty:
            return None
        mask = (
            (wf["_issued_dt"] <= as_of_time) &
            (wf["_valid_from_dt"] <= as_of_time) &
            (wf["_valid_to_dt"] >= as_of_time)
        )
        subset = wf[mask]
        if subset.empty:
            return None
        return subset.iloc[-1]

    # ── Route Changes ───────────────────────────────────────────────────────

    def get_route_changes(self, shipment_id: str, as_of_time: pd.Timestamp) -> pd.DataFrame:
        as_of_time = self._to_dt(as_of_time)
        rc = self._rc_by_ship.get(shipment_id)
        if rc is None or rc.empty:
            return pd.DataFrame(columns=self.data.get("route_changes", pd.DataFrame()).columns)
        mask = rc["_recorded_dt"] <= as_of_time
        return rc[mask]

    # ── Disruptions ─────────────────────────────────────────────────────────

    def get_disruptions(self, facility_id: str, as_of_time: pd.Timestamp) -> pd.DataFrame:
        as_of_time = self._to_dt(as_of_time)
        dis = self._dis_by_fac.get(facility_id)
        if dis is None or dis.empty:
            return pd.DataFrame(columns=self.data.get("disruptions", pd.DataFrame()).columns)
        mask = (
            (dis["_reported_dt"] <= as_of_time) &
            (dis["_started_dt"] <= as_of_time) &
            (dis["_ended_dt"] >= as_of_time)
        )
        return dis[mask]

    # ── Carrier Performance (Temporal) ──────────────────────────────────────

    def get_carrier_performance(
        self,
        carrier_id: str,
        as_of_time: pd.Timestamp,
        exclude_shipment_id: Optional[str] = None,
    ) -> dict:
        """
        Compute carrier performance metrics from historically completed shipments.

        Uses only:
          - Shipments with actual_delivery_at < as_of_time (outcome known before snapshot)
          - Shipments assigned to this carrier
          - Excludes `exclude_shipment_id` to prevent target leakage

        Applies Bayesian shrinkage toward global priors when sample size < threshold:
          on_time_rate = (n_on_time + k*mu_prior) / (n + k)   where k = min_samples
          avg_delay    = weighted mean toward global prior

        Returns dict with keys:
          carrier_on_time_rate, carrier_avg_delay_hours, carrier_reliability,
          carrier_sample_size
        """
        df_carrier = self._completed_by_carrier.get(carrier_id)
        if df_carrier is None or df_carrier.empty:
            return {
                "carrier_on_time_rate": _CARRIER_GLOBAL_ON_TIME_RATE,
                "carrier_avg_delay_hours": _CARRIER_GLOBAL_AVG_DELAY,
                "carrier_reliability": _CARRIER_GLOBAL_ON_TIME_RATE,
                "carrier_sample_size": 0,
            }

        as_of_time = self._to_dt(as_of_time)
        mask = df_carrier["_actual_dt"] < as_of_time
        if exclude_shipment_id:
            mask = mask & (df_carrier["shipment_id"] != exclude_shipment_id)

        completed = df_carrier[mask]
        n = len(completed)

        if n == 0:
            return {
                "carrier_on_time_rate": _CARRIER_GLOBAL_ON_TIME_RATE,
                "carrier_avg_delay_hours": _CARRIER_GLOBAL_AVG_DELAY,
                "carrier_reliability": _CARRIER_GLOBAL_ON_TIME_RATE,
                "carrier_sample_size": 0,
            }

        n_on_time = int(completed["_is_on_time"].sum())

        # Bayesian shrinkage for on-time rate
        k = _CARRIER_MIN_SAMPLES
        smoothed_on_time_rate = (n_on_time + k * _CARRIER_GLOBAL_ON_TIME_RATE) / (n + k)

        # Average delay (only over delayed shipments, or 0 if none)
        delayed_hours = completed["_delay_hours"][completed["_delay_hours"] > 0]
        raw_avg_delay = float(delayed_hours.mean()) if len(delayed_hours) > 0 else 0.0
        smoothed_avg_delay = (raw_avg_delay * n + _CARRIER_GLOBAL_AVG_DELAY * k) / (n + k)

        return {
            "carrier_on_time_rate": round(float(smoothed_on_time_rate), 4),
            "carrier_avg_delay_hours": round(float(smoothed_avg_delay), 2),
            "carrier_reliability": round(float(smoothed_on_time_rate), 4),
            "carrier_sample_size": n,
        }
