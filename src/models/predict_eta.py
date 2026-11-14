"""Prediction Service Module
Provides high-level interfaces for generating ETA and Delay Risk predictions.
Automatically applies trained ML pipelines with deterministic fallbacks.
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from src.models.model_registry import load_model, MODELS_DIR

ETA_MODEL_PATH = MODELS_DIR / "eta_regressor.joblib"
DELAY_MODEL_PATH = MODELS_DIR / "delay_classifier.joblib"


def assign_risk_category(prob: float) -> str:
    """Map delay probability to calibrated operational risk tier."""
    if prob < 0.25:
        return "LOW"
    elif prob < 0.50:
        return "MEDIUM"
    elif prob < 0.75:
        return "HIGH"
    else:
        return "CRITICAL"


def _add_engineered_features(df: pd.DataFrame) -> pd.DataFrame:
    """Derive interaction features if missing."""
    df = df.copy()
    if "progress_weighted_remaining" not in df.columns and "planned_remaining_hours" in df.columns:
        prog = df["progress_pct"].clip(0, 1) if "progress_pct" in df.columns else 0.0
        df["progress_weighted_remaining"] = df["planned_remaining_hours"] * (1.0 - prog)
    if "carrier_delay_ratio" not in df.columns and "carrier_avg_delay" in df.columns:
        plan_t = df["planned_transit_hours"].clip(lower=1.0) if "planned_transit_hours" in df.columns else 1.0
        df["carrier_delay_ratio"] = df["carrier_avg_delay"] / plan_t
    if "pace_ratio" not in df.columns and "shipment_age_hours" in df.columns:
        plan_t = df.get("planned_transit_hours", 1.0)
        plan_r = df.get("planned_remaining_hours", 0.0)
        plan_el = (plan_t - plan_r).clip(lower=0.1)
        df["pace_ratio"] = df["shipment_age_hours"] / plan_el
    if "hours_per_leg_planned" not in df.columns and "planned_transit_hours" in df.columns:
        num_l = df["num_legs"].clip(lower=1) if "num_legs" in df.columns else 1
        df["hours_per_leg_planned"] = df["planned_transit_hours"] / num_l
    return df


class PredictionService:
    def __init__(self):
        self.eta_model = None
        self.eta_metadata = {}
        self.delay_model = None
        self.delay_metadata = {}
        self._load_models()

    def _load_models(self):
        if ETA_MODEL_PATH.exists():
            try:
                self.eta_model, self.eta_metadata = load_model(ETA_MODEL_PATH)
            except Exception as e:
                print(f"Warning: Could not load ETA model: {e}")

        if DELAY_MODEL_PATH.exists():
            try:
                self.delay_model, self.delay_metadata = load_model(DELAY_MODEL_PATH)
            except Exception as e:
                print(f"Warning: Could not load Delay model: {e}")

    def predict_eta(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """Predict remaining delivery hours and delivery timestamps."""
        features = _add_engineered_features(features_df)
        
        feature_cols = self.eta_metadata.get("feature_cols", [
            "shipment_age_hours", "num_legs", "weight_kg", "distance_km",
            "planned_transit_hours", "planned_remaining_hours", "completed_legs",
            "remaining_legs", "progress_pct", "hours_since_last_event",
            "missing_expected_scans", "carrier_on_time_rate", "carrier_avg_delay",
            "carrier_reliability", "current_queue_length", "avg_wait_minutes",
            "facility_utilization", "facility_disrupted", "precipitation_mm",
            "wind_speed_kmh", "weather_disruptive", "route_changes_count"
        ])

        # Fill missing cols with 0
        for col in feature_cols:
            if col not in features.columns:
                features[col] = 0.0

        X = features[feature_cols]

        if self.eta_model is not None:
            predicted_hours = self.eta_model.predict(X)
            method = "ML_HIST_GRADIENT_BOOSTING"
            version = "v1.0"
        else:
            # Deterministic rule-based fallback
            predicted_hours = features["planned_remaining_hours"].values * 1.1
            method = "RULE_BASED_FALLBACK"
            version = "rule_v1.0"

        predicted_hours = np.clip(predicted_hours, 0, None)
        features["predicted_remaining_hours"] = np.round(predicted_hours, 2)
        features["prediction_method"] = method
        features["model_version"] = version
        features["prediction_timestamp"] = datetime.now(timezone.utc).isoformat()

        # Compute predicted_delivery_at
        deliv_times = []
        for _, row in features.iterrows():
            snap_time = pd.to_datetime(row["snapshot_time"], utc=True)
            pred_time = snap_time + timedelta(hours=float(row["predicted_remaining_hours"]))
            deliv_times.append(pred_time.isoformat())
        features["predicted_delivery_at"] = deliv_times

        return features[[
            "shipment_id", "eta_id", "snapshot_time", "predicted_remaining_hours",
            "predicted_delivery_at", "prediction_method", "model_version", "prediction_timestamp"
        ]]

    def predict_delay_risk(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """Predict delay probability and operational risk tier."""
        features = _add_engineered_features(features_df)
        feature_cols = self.delay_metadata.get("feature_cols", [
            "shipment_age_hours", "num_legs", "weight_kg", "distance_km",
            "planned_transit_hours", "planned_remaining_hours", "completed_legs",
            "remaining_legs", "progress_pct", "hours_since_last_event",
            "missing_expected_scans", "carrier_on_time_rate", "carrier_avg_delay",
            "carrier_reliability", "current_queue_length", "avg_wait_minutes",
            "facility_utilization", "facility_disrupted", "precipitation_mm",
            "wind_speed_kmh", "weather_disruptive", "route_changes_count"
        ])

        for col in feature_cols:
            if col not in features.columns:
                features[col] = 0.0

        X = features[feature_cols]

        if self.delay_model is not None:
            probas = self.delay_model.predict_proba(X)[:, 1]
            method = "ML_DELAY_CLASSIFIER"
            version = "v1.0"
        else:
            # Rule-based fallback: base prob on remaining time vs delay
            probas = np.where(features["hours_since_last_event"] > 24, 0.7, 0.2)
            method = "RULE_BASED_FALLBACK"
            version = "rule_v1.0"

        features["delay_probability"] = np.round(probas, 4)
        features["delay_risk"] = [assign_risk_category(p) for p in probas]
        features["model_version"] = version
        features["prediction_timestamp"] = datetime.now(timezone.utc).isoformat()

        return features[[
            "shipment_id", "delay_probability", "delay_risk", "model_version", "prediction_timestamp"
        ]]


_service_instance: Optional[PredictionService] = None

def get_prediction_service() -> PredictionService:
    global _service_instance
    if _service_instance is None:
        _service_instance = PredictionService()
    return _service_instance

