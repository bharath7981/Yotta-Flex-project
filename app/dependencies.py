"""FastAPI Dependency Providers"""
from typing import Dict
import pandas as pd
from src.data.loader import load_all_data
from src.data.repository import LogisticsRepository
from src.models.predict_eta import get_prediction_service, PredictionService

_data_cache: Dict[str, pd.DataFrame] = {}
_repo_instance: LogisticsRepository = None


def get_cached_data() -> Dict[str, pd.DataFrame]:
    global _data_cache
    if not _data_cache:
        _data_cache = load_all_data()
    return _data_cache


def get_repository() -> LogisticsRepository:
    global _repo_instance
    if _repo_instance is None:
        _repo_instance = LogisticsRepository()
    return _repo_instance


def get_predictor() -> PredictionService:
    return get_prediction_service()

