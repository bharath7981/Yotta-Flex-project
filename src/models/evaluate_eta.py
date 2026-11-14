"""Evaluation utilities for ETA and delay models."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
    average_precision_score,
)

METRICS_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "metrics"


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


# ---- ETA regression --------------------------------------------------------

def evaluate_eta_model(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> Dict[str, float]:
    """Return MAE, RMSE, R², MAPE for a regression prediction."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    mae = mean_absolute_error(y_true, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = r2_score(y_true, y_pred)

    # MAPE – guard against zeros
    mask = y_true != 0
    if mask.sum() > 0:
        mape = float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)
    else:
        mape = float("nan")

    return {"MAE": round(mae, 4), "RMSE": round(rmse, 4), "R2": round(r2, 4), "MAPE": round(mape, 2)}


# ---- Delay classification --------------------------------------------------

def evaluate_delay_model(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Return precision, recall, F1, ROC-AUC, PR-AUC, confusion matrix."""
    y_true = np.asarray(y_true, dtype=int)
    y_pred = np.asarray(y_pred, dtype=int)

    metrics: Dict[str, Any] = {
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
    }

    if y_proba is not None:
        y_proba = np.asarray(y_proba, dtype=float)
        if len(np.unique(y_true)) > 1:
            metrics["roc_auc"] = round(float(roc_auc_score(y_true, y_proba)), 4)
            metrics["pr_auc"] = round(float(average_precision_score(y_true, y_proba)), 4)
        else:
            metrics["roc_auc"] = float("nan")
            metrics["pr_auc"] = float("nan")

    cm = confusion_matrix(y_true, y_pred)
    metrics["confusion_matrix"] = cm.tolist()

    return metrics


# ---- Comparison helper ------------------------------------------------------

def compare_methods(results_dict: Dict[str, Dict[str, Any]]) -> pd.DataFrame:
    """Build a comparison DataFrame from {method_name: metrics_dict}."""
    rows = []
    for method, metrics in results_dict.items():
        row = {"method": method}
        for k, v in metrics.items():
            if not isinstance(v, (list, dict, np.ndarray)):
                row[k] = v
        rows.append(row)
    return pd.DataFrame(rows).set_index("method")


# ---- Persistence ------------------------------------------------------------

def save_metrics(
    metrics: Dict[str, Any],
    name: str,
    directory: Optional[str | Path] = None,
) -> Path:
    """Save metrics dict as JSON in artifacts/metrics/."""
    d = Path(directory) if directory else METRICS_DIR
    _ensure_dir(d)
    path = d / f"{name}.json"
    # Make numpy types JSON-safe
    from src.models.model_registry import _make_serialisable
    with open(path, "w") as f:
        json.dump(_make_serialisable(metrics), f, indent=2, default=str)
    return path
