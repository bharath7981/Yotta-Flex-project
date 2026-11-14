"""Prediction Schemas"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class ETAPredictionRequest(BaseModel):
    shipment_id: str
    snapshot_time: Optional[str] = None
    custom_features: Optional[Dict[str, float]] = None


class ETAPredictionResponse(BaseModel):
    shipment_id: str
    eta_id: Optional[str] = None
    snapshot_time: str
    planned_delivery_at: Optional[str] = None
    predicted_delivery_at: str
    predicted_remaining_hours: float
    prediction_method: str
    model_version: str
    prediction_timestamp: str
    data_quality_warnings: List[str] = []


class DelayRiskResponse(BaseModel):
    shipment_id: str
    delay_probability: float  # Probability that actual_delivery_at > planned_delivery_at
    delay_risk: str  # LOW, MEDIUM, HIGH, CRITICAL
    target_name: str = "is_delayed_target"
    target_definition: str = (
        "Binary schedule delay indicator: 1 = actual_delivery_at > planned_delivery_at "
        "(schedule variance vs planned delivery; distinct from contractual SLA breach)."
    )
    secondary_contract_label: str = (
        "is_sla_breached_target: actual_delivery_at > promised_delivery_at + grace_hours"
    )
    model_version: str
    prediction_timestamp: str
    data_quality_warnings: List[str] = []

