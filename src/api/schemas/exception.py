"""Exception Schemas"""
from typing import List, Optional
from pydantic import BaseModel


class OperationalExceptionItem(BaseModel):
    exception_id: str
    shipment_id: str
    exception_type: str
    severity: str
    description: str
    detected_at: str
    evidence_ids: str
    recommended_action: str
    status: str


class ExceptionStatusUpdate(BaseModel):
    status: str  # OPEN, ACKNOWLEDGED, RESOLVED

