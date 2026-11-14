"""Exceptions API Routes"""
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
import pandas as pd

from src.api.schemas.exception import OperationalExceptionItem, ExceptionStatusUpdate
from src.exceptions.engine import ExceptionEngine

router = APIRouter(prefix="/exceptions", tags=["Exceptions"])
PROJECT_ROOT = Path(__file__).resolve().parents[3]
EXC_CSV = PROJECT_ROOT / "data" / "analytics" / "exceptions.csv"


@router.get("", response_model=List[OperationalExceptionItem])
def list_exceptions(
    status: Optional[str] = Query(None, description="OPEN, ACKNOWLEDGED, RESOLVED"),
    exception_type: Optional[str] = None
):
    if not EXC_CSV.exists():
        engine = ExceptionEngine()
        df = engine.generate_all_exceptions()
    else:
        df = pd.read_csv(EXC_CSV)

    if status:
        df = df[df["status"] == status.upper()]
    if exception_type:
        df = df[df["exception_type"] == exception_type.upper()]

    return df.to_dict(orient="records")


@router.patch("/{exception_id}/status", response_model=OperationalExceptionItem)
def update_exception_status(exception_id: str, body: ExceptionStatusUpdate):
    valid_statuses = ["OPEN", "ACKNOWLEDGED", "RESOLVED"]
    if body.status.upper() not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    engine = ExceptionEngine()
    updated = engine.update_exception_status(exception_id, body.status.upper())
    if not updated:
        raise HTTPException(status_code=404, detail=f"Exception {exception_id} not found")

    return updated

