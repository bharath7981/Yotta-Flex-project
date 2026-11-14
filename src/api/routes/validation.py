"""Validation API Route"""
import json
from pathlib import Path
from fastapi import APIRouter, Depends
from app.dependencies import get_cached_data
from src.data.validator import DataValidator

router = APIRouter(prefix="/validation", tags=["Validation"])
PROJECT_ROOT = Path(__file__).resolve().parents[3]
VAL_JSON = PROJECT_ROOT / "reports" / "validation_summary.json"


@router.get("/summary")
def get_validation_summary(data=Depends(get_cached_data)):
    if VAL_JSON.exists():
        try:
            with open(VAL_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    validator = DataValidator(data, allow_expected_anomalies=True)
    report = validator.run_all()
    return {
        "status": "PASSED" if report.is_valid else "FAILED",
        "total_checks": report.total_checks,
        "passed_checks": report.passed_checks,
        "failed_checks": report.failed_checks,
        "warning_checks": report.warning_checks,
        "issues": [issue.to_dict() for issue in report.issues]
    }

