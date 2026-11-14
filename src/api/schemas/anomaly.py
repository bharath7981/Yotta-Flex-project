"""Anomaly Schemas"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class AnomalyItem(BaseModel):
    anomaly_id: str
    entity_type: str
    entity_id: str
    shipment_id: str
    issue_type: str
    severity: str
    detection_rule: str
    evidence: str
    detected_at: str


class AnomalySummaryResponse(BaseModel):
    total_detected: int
    by_category: Dict[str, int]
    by_severity: Dict[str, int]
    benchmark_metrics: Optional[Dict[str, Any]] = None

