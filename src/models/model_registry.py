"""Model registry – save, load, list, and inspect trained models."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib

MODELS_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "models"


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def save_model(
    model: Any,
    metadata: Dict[str, Any],
    path: Optional[str | Path] = None,
    model_name: Optional[str] = None,
) -> Path:
    """Persist a model and its metadata via joblib.

    Parameters
    ----------
    model : fitted estimator (or pipeline)
    metadata : dict with keys like feature_names, metrics, train_date …
    path : explicit save path; if *None*, derives from *model_name*.
    model_name : used when *path* is None.

    Returns
    -------
    Path where the model bundle was saved.
    """
    if path is None:
        if model_name is None:
            raise ValueError("Provide path or model_name")
        _ensure_dir(MODELS_DIR)
        path = MODELS_DIR / f"{model_name}.joblib"
    else:
        path = Path(path)
        _ensure_dir(path.parent)

    # Store train_date if not already present
    metadata.setdefault("train_date", datetime.now(timezone.utc).isoformat())
    metadata.setdefault("model_name", model_name or path.stem)

    bundle = {"model": model, "metadata": metadata}
    joblib.dump(bundle, path)

    # Also save metadata as JSON sidecar for easy inspection
    meta_path = path.with_suffix(".meta.json")
    _serialisable = _make_serialisable(metadata)
    with open(meta_path, "w") as f:
        json.dump(_serialisable, f, indent=2, default=str)

    return path


def load_model(path: str | Path) -> Tuple[Any, Dict[str, Any]]:
    """Load a model bundle.  Returns (model, metadata)."""
    path = Path(path)
    bundle = joblib.load(path)
    return bundle["model"], bundle["metadata"]


def list_models(directory: Optional[str | Path] = None) -> List[str]:
    """Return names of saved models in *directory* (defaults to artifacts/models/)."""
    d = Path(directory) if directory else MODELS_DIR
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.joblib"))


def get_model_metadata(model_name: str, directory: Optional[str | Path] = None) -> Dict[str, Any]:
    """Read the metadata sidecar for *model_name*."""
    d = Path(directory) if directory else MODELS_DIR
    meta_path = d / f"{model_name}.meta.json"
    if meta_path.exists():
        with open(meta_path) as f:
            return json.load(f)
    # Fall back to loading from joblib bundle
    joblib_path = d / f"{model_name}.joblib"
    if joblib_path.exists():
        _, metadata = load_model(joblib_path)
        return metadata
    raise FileNotFoundError(f"No model found: {model_name} in {d}")


# ---- helpers ----

def _make_serialisable(obj: Any) -> Any:
    """Recursively convert numpy / non-JSON types so json.dump works."""
    import numpy as np

    if isinstance(obj, dict):
        return {k: _make_serialisable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serialisable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj
