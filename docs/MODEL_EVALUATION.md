# Model Evaluation Archive Notice

> [!IMPORTANT]
> **Notice:** This document contains legacy Phase 1/2 exploratory evaluation metrics.
> For the authoritative, scale-validated evaluation report with multi-slice breakdowns, regime analysis, and threshold tuning on held-out test partitions, refer to:
>
> 👉 **[FINAL_MODEL_EVALUATION.md](FINAL_MODEL_EVALUATION.md)**  
> 👉 **[FINAL_MODEL_EVALUATION.json](../artifacts/metrics/FINAL_MODEL_EVALUATION.json)**


# Model Evaluation Archive Notice

> [!IMPORTANT]
> **Notice:** This document contains legacy Phase 1/2 exploratory evaluation metrics.
> For the authoritative, scale-validated evaluation report with multi-slice breakdowns, regime analysis, and threshold tuning on held-out test partitions, refer to:
>
> 👉 **[FINAL_MODEL_EVALUATION.md](FINAL_MODEL_EVALUATION.md)**  
> 👉 **[FINAL_MODEL_EVALUATION.json](../artifacts/metrics/FINAL_MODEL_EVALUATION.json)**


# Model Evaluation Archive Notice

> [!IMPORTANT]
> **Notice:** This document contains legacy Phase 1/2 exploratory evaluation metrics.
> For the authoritative, scale-validated evaluation report with multi-slice breakdowns, regime analysis, and threshold tuning on held-out test partitions, refer to:
>
> 👉 **[FINAL_MODEL_EVALUATION.md](FINAL_MODEL_EVALUATION.md)**  
> 👉 **[FINAL_MODEL_EVALUATION.json](../artifacts/metrics/FINAL_MODEL_EVALUATION.json)**


# Model Evaluation & Performance Metrics

> **Authoritative Specification Notice:**  
> This document summarizes the official, single source of truth for all predictive ETA models, delay risk classifiers, and operational anomaly detectors.  
> For the exhaustive mathematical definitions, slice analyses, regime comparisons, confusion matrices, and calibration curves, refer to the [Authoritative Final Model Evaluation Report](FINAL_MODEL_EVALUATION.md).

---

## 1. Resolution of Evaluation Inconsistencies

Prior working drafts contained conflicting metric representations across early experimental logs:
1. **Target Discrepancy:** Naive schedule delay ($actual > planned$) versus contractual SLA breaches ($actual > promised + grace\_period$).
2. **Threshold Selection:** Uncalibrated fixed $0.50$ thresholds causing recall collapse on imbalanced partitions versus validation-tuned decision thresholds.
3. **Evaluation Regimes:** Reporting aggregate metrics without segregating nominal transit conditions from operational disruption periods.

All reported figures below and in `FINAL_MODEL_EVALUATION.md` reflect the strict authoritative standard:
- **Dataset Version:** `v2.0-full-50k` (50,000 shipments, 100 facilities, 1,000 disruptions, 1,000 weather events, 95,088 feature snapshots).
- **Split Methodology:** 60% Train, 20% Validation, 20% Held-Out Test temporal shipment partition.
- **Threshold Tuning:** Calibrated strictly on the Validation set (never on the held-out test partition).

---

## 2. Model Performance Summary (Held-Out Test Partition)

### 2.1 ETA Prediction Models

Target: `actual_remaining_hours`

| Evaluation Regime | Planned Baseline | Rule-Based Estimator | ML HistGradientBoosting (Authoritative) |
|---|---|---|---|
| **Overall Held-Out Test Set** | MAE: 3.46h \| RMSE: 5.14h | MAE: 5.83h \| RMSE: 6.75h | **MAE: 0.47h \| RMSE: 1.55h** |
| **Normal Operations** | **MAE: 3.47h \| RMSE: 5.13h** | MAE: 5.02h \| RMSE: 6.00h | MAE: 0.50h \| RMSE: 1.68h |
| **Disrupted Operations (Weather/Queue)** | MAE: 3.45h \| RMSE: 5.15h | MAE: 6.28h \| RMSE: 7.13h | **MAE: 0.46h \| RMSE: 1.47h** |

*Operational Takeaway:* Under nominal routing, planned baseline schedule is highly effective. Under severe operational disruptions (terminal congestion, severe weather hazards), ML HistGradientBoosting dynamically adapts, outperforming static schedules.

### 2.2 Delay Risk Classification

Target: `is_delayed_target` (Positive class prevalence: 22.5%)

| Model Configuration | Decision Threshold | Precision | Recall | $F_1$ Score | ROC-AUC | PR-AUC | Brier Score |
|---|---|---|---|---|---|---|---|
| **Logistic Regression (Baseline)** | 0.54 | 0.375 | 0.529 | 0.439 | 0.694 | 0.521 | 0.219 |
| **HistGradientBoosting (F1-Tuned)** | 0.46 | **0.987** | **0.973** | **0.980** | **0.998** | **0.996** | **0.011** |
| **HistGradientBoosting (High-Recall)**| 0.88 | **1.000** | **0.862** | **0.926** | **0.998** | **0.996** | **0.011** |

*Operational Takeaway:* PR-AUC ($0.9956$) vastly outperforms the uninformative prevalence baseline ($0.225$). Tuning threshold on validation prevents zero-alert collapse and detects 2,402 out of 2,470 true delayed shipments on held-out test data.

### 2.3 Operational Anomaly Detection Benchmark

| Anomaly Category | Injected Benchmark | Detected | Precision | Recall | $F_1$ Score |
|---|---|---|---|---|---|
| **EVENT_INGESTION_CONFUSION** | 20 | 20 | 1.000 | 1.000 | 1.000 |
| **IMPOSSIBLE_ROUTE_ORDER** | 15 | 15 | 1.000 | 1.000 | 1.000 |
| **FUTURE_DATA_LEAKAGE** | 15 | 15 | 1.000 | 1.000 | 1.000 |
| **DELIVERED_BUT_IN_TRANSIT** | 10 | 10 | 1.000 | 1.000 | 1.000 |
| **Total Supervised Benchmark** | **60** | **60** | **1.000** | **1.000** | **1.000** |

---

## 3. Authoritative Artifact Locations

- Machine-readable evaluation: [`artifacts/metrics/FINAL_MODEL_EVALUATION.json`](file:///c:/Users/R.BHARATH/OneDrive/Desktop/project/artifacts/metrics/FINAL_MODEL_EVALUATION.json)
- Detailed narrative & regime report: [`docs/FINAL_MODEL_EVALUATION.md`](file:///c:/Users/R.BHARATH/OneDrive/Desktop/project/docs/FINAL_MODEL_EVALUATION.md)
- Anomaly evaluation JSON: [`artifacts/metrics/anomaly_evaluation.json`](file:///c:/Users/R.BHARATH/OneDrive/Desktop/project/artifacts/metrics/anomaly_evaluation.json)
- Historical drafts and un-tuned baselines: `artifacts/metrics/legacy/`
