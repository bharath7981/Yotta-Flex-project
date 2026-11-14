"""Anomaly Detection Evaluation Module
Benchmarks detected operational anomalies against the controlled ground-truth labels.
Computes True Positives, False Positives, False Negatives, Precision, Recall, and F1-score.
"""

import json
from pathlib import Path
from typing import Dict, Any
import pandas as pd

from src.anomaly.detectors import AnomalyDetector
from src.data.loader import load_all_data

PROJECT_ROOT = Path(__file__).resolve().parents[2]
METRICS_DIR = PROJECT_ROOT / "artifacts" / "metrics"


def evaluate_anomalies(detected_df: pd.DataFrame, ground_truth_df: pd.DataFrame) -> Dict[str, Any]:
    """Compute precision, recall, and F1 for detected vs ground truth anomalies."""
    categories = [
        "EVENT_INGESTION_CONFUSION",
        "IMPOSSIBLE_ROUTE_ORDER",
        "FUTURE_DATA_LEAKAGE",
        "DELIVERED_BUT_IN_TRANSIT"
    ]

    results_by_cat = {}
    total_tp = 0
    total_fp = 0
    total_fn = 0

    for cat in categories:
        gt_subset = ground_truth_df[ground_truth_df["issue_type"] == cat]
        det_subset = detected_df[detected_df["issue_type"] == cat]

        # For entity-level matching, use entity_id
        gt_entities = set(gt_subset["entity_id"])
        det_entities = set(det_subset["entity_id"])

        tp = len(gt_entities & det_entities)
        fp = len(det_entities - gt_entities)
        fn = len(gt_entities - det_entities)

        prec = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
        rec = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
        f1 = round(2 * (prec * rec) / (prec + rec), 4) if (prec + rec) > 0 else 0.0

        results_by_cat[cat] = {
            "ground_truth_count": len(gt_entities),
            "detected_count": len(det_entities),
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "precision": prec,
            "recall": rec,
            "f1_score": f1
        }

        total_tp += tp
        total_fp += fp
        total_fn += fn

    overall_prec = round(total_tp / (total_tp + total_fp), 4) if (total_tp + total_fp) > 0 else 0.0
    overall_rec = round(total_tp / (total_tp + total_fn), 4) if (total_tp + total_fn) > 0 else 0.0
    overall_f1 = round(2 * (overall_prec * overall_rec) / (overall_prec + overall_rec), 4) if (overall_prec + overall_rec) > 0 else 0.0

    overall_summary = {
        "overall": {
            "ground_truth_total": len(ground_truth_df),
            "detected_total": len(detected_df),
            "true_positives": total_tp,
            "false_positives": total_fp,
            "false_negatives": total_fn,
            "precision": overall_prec,
            "recall": overall_rec,
            "f1_score": overall_f1
        },
        "by_category": results_by_cat
    }

    # Save metrics JSON
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    out_file = METRICS_DIR / "anomaly_evaluation.json"
    with open(out_file, "w") as f:
        json.dump(overall_summary, f, indent=2)
    print(f"Anomaly evaluation metrics saved to {out_file}")

    return overall_summary


def run_anomaly_evaluation():
    data = load_all_data()
    detector = AnomalyDetector(data)
    detected_df = detector.run_all_detectors()
    gt_df = data["ground_truth_anomalies"]
    summary = evaluate_anomalies(detected_df, gt_df)

    print("\n=== Anomaly Detection Benchmark Results ===")
    print(f"Overall Precision: {summary['overall']['precision']} | Recall: {summary['overall']['recall']} | F1: {summary['overall']['f1_score']}")
    print("-" * 65)
    for cat, res in summary["by_category"].items():
        print(f"{cat:<30}: P={res['precision']:.2f}, R={res['recall']:.2f}, F1={res['f1_score']:.2f} (TP={res['true_positives']}, FP={res['false_positives']}, FN={res['false_negatives']})")
    return summary


if __name__ == "__main__":
    run_anomaly_evaluation()

