"""Streamlit Cached Data Loader"""
import os
from pathlib import Path
from typing import Dict, Any
import pandas as pd
import streamlit as st

from src.data.loader import load_all_data
from src.data.normalizer import normalize_all_data

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ANALYTICS_DIR = PROJECT_ROOT / "data" / "analytics"


@st.cache_data(ttl=600)
def load_dashboard_data() -> Dict[str, pd.DataFrame]:
    """Load all necessary tables with parsed timestamps and normalized SLA columns."""
    raw_data = load_all_data()
    data = normalize_all_data(raw_data)

    # Analytics tables
    anom_path = ANALYTICS_DIR / "detected_anomalies.csv"
    if anom_path.exists():
        data["detected_anomalies"] = pd.read_csv(anom_path)
    elif "ground_truth_anomalies" in data:
        data["detected_anomalies"] = data["ground_truth_anomalies"].copy()

    exc_path = ANALYTICS_DIR / "exceptions.csv"
    if exc_path.exists():
        data["exceptions"] = pd.read_csv(exc_path)

    exp_path = ANALYTICS_DIR / "delay_explanations.csv"
    if exp_path.exists():
        data["delay_explanations"] = pd.read_csv(exp_path)

    return data
