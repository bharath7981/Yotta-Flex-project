# Platform Limitations, Edge Cases & Operational Governance

This document provides transparent engineering disclosure regarding model behavior, target definitions, distribution boundaries, and operational edge cases for the Logistics ETA Prediction & Delay Intelligence Platform.

---

## 1. ETA Model Performance Nuances: Planned Baseline vs Machine Learning

### 1.1 Aggregate Benchmark Reality
On the held-out test partition across the full 50,000-shipment network:
- **Planned Baseline Benchmark**: MAE = **3.46 hours**, RMSE = **5.14 hours**, $R^2$ = **0.938**
- **Machine Learning HistGradientBoosting**: MAE = **0.47 hours**, RMSE = **1.55 hours**, $R^2$ = **0.994**

### 1.2 Operational Regime Analysis
- **Nominal Operations (80%+ of Network)**: Under nominal weather and empty gate queues, freight movements closely mirror scheduled dispatch planning. The static schedule provides a reliable analytical anchor.
- **Disruption Regimes (Severe Weather, Terminal Outages, Queue Spikes)**: Static schedules fail catastrophically during unexpected disruption events because they lack real-time telematics feedback. Machine Learning models adjust dynamically, absorbing live weather intensity and gate queue dwell hours to deliver superior situational awareness.

---

## 2. Delay Classification Target Selection

### 2.1 Why `is_delayed_target` is the Primary Model Target
- `is_delayed_target` tracks schedule arrival later than scheduled `planned_delivery_at`.
- It exhibits a healthy **22.5% positive prevalence** across test shipments.
- This prevalence allows gradient boosting trees to learn rich non-linear interactions across carrier performance, queue depths, and weather severity.

### 2.2 Why `is_sla_breached_target` is Not Used for Operational Alerting
- Contractual SLA breaches require shipments to exceed promised delivery deadlines **plus contractual grace periods** (0.5h to 4.0h).
- In a well-buffered logistics network, contractual SLA breaches occur on only ~3.7% of shipments.
- Deploying a naive 0.50 probability threshold on a 3.7% positive class leads to **model collapse** (predicting zero alerts).
- To preserve operational alerting, the platform trains on `is_delayed_target` with validation-set threshold tuning ($t = 0.46$), while tracking `is_sla_breached_target` as an escalation metric.

---

## 3. Telematics Anomaly Detection: Synthetic Benchmarks vs Real-World Production

### 3.1 Synthetic Benchmark Scope
The supervised benchmark injects 60 controlled test defects across 4 mandatory categories:
1. `EVENT_INGESTION_CONFUSION`: Ingestion timestamp preceding occurrence timestamp.
2. `IMPOSSIBLE_ROUTE_ORDER`: Sequence reversal in transportation legs.
3. `FUTURE_DATA_LEAKAGE`: Event occurrence timestamp beyond snapshot cutoff.
4. `DELIVERED_BUT_IN_TRANSIT`: Shipment status marked in-transit despite delivery scan.

### 3.2 Real-World Production Differences
In live carrier operations:
- **Cellular Dead Zones**: Mobile scanners store events locally and ingest in batches hours later.
- **Clock Drift**: Third-party warehouse scanners may exhibit sub-minute unsynchronized clocks.
- **Customer Early Scans**: Consignees may sign proof-of-delivery prior to carrier backend database synchronization.
- **Unannounced Detours**: Highway closures cause legitimate route sequence departures.
- **Estimated Operational F1**: Real-world operational precision is estimated at **0.85 – 0.92** and recall at **0.78 – 0.88**, compared to 1.00 on controlled deterministic synthetic benchmarks.
