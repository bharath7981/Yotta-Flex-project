"""Anomalies API Routes"""
import json
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends
import pandas as pd

from app.dependencies import get_cached_data
from src.api.schemas.anomaly import AnomalyItem, AnomalySummaryResponse

router = APIRouter(prefix="/anomalies", tags=["Anomalies"])
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ANOM_CSV = PROJECT_ROOT / "data" / "analytics" / "detected_anomalies.csv"
METRICS_JSON = PROJECT_ROOT / "artifacts" / "metrics" / "anomaly_evaluation.json"


@router.get("", response_model=List[AnomalyItem])
def list_anomalies(data=Depends(get_cached_data)):
    if ANOM_CSV.exists():
        df = pd.read_csv(ANOM_CSV)
    else:
        from src.anomaly.detectors import AnomalyDetector
        det = AnomalyDetector(data)
        df = det.run_all_detectors()

    return df.to_dict(orient="records")


@router.get("/summary", response_model=AnomalySummaryResponse)
def get_anomaly_summary(data=Depends(get_cached_data)):
    if ANOM_CSV.exists():
        df = pd.read_csv(ANOM_CSV)
    else:
        from src.anomaly.detectors import AnomalyDetector
        det = AnomalyDetector(data)
        df = det.run_all_detectors()

    by_cat = df["issue_type"].value_counts().to_dict()
    by_sev = df["severity"].value_counts().to_dict()

    bench = None
    if METRICS_JSON.exists():
        with open(METRICS_JSON) as f:
            bench = json.load(f)

    return AnomalySummaryResponse(
        total_detected=len(df),
        by_category=by_cat,
        by_severity=by_sev,
        benchmark_metrics=bench
    )

