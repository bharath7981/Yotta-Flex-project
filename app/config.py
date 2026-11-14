"""Application Configuration Settings"""
import os
from pathlib import Path
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "existing"
ANALYTICS_DIR = PROJECT_ROOT / "data" / "analytics"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
MODELS_DIR = ARTIFACTS_DIR / "models"
METRICS_DIR = ARTIFACTS_DIR / "metrics"

class Settings(BaseModel):
    app_name: str = "Logistics ETA & Delay Intelligence Platform"
    version: str = "1.0.0"
    api_prefix: str = "/api"
    duckdb_path: str = str(ANALYTICS_DIR / "logistics.duckdb")

settings = Settings()

