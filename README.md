# Logistics ETA Prediction & Delay Intelligence Platform

A production-grade, end-to-end logistics monitoring, predictive ETA forecasting, delay risk intelligence, and anomaly detection platform.

---

## 1. Project Overview & Business Value

In high-velocity freight logistics networks, unexpected transit disruptions, terminal queue congestion, severe weather hazards, and telematics data quality defects trigger severe customer dissatisfaction and contractual SLA breach penalties.

This platform bridges the gap between raw logistics telematics and proactive operations management:
- **Accurate Point-in-Time ETA Predictions**: Predicts P50 (median) and P90 (conservative) ETAs using gradient-boosted ML models with zero future lookahead data leakage.
- **Calibrated Delay Risk Classification**: Flags shipments likely to miss promised delivery deadlines into risk tiers (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
- **Authoritative SLA Enforcement**: Strictly computes delivery delays against contractual promised times and grace periods:
  $$\text{delay\_hours} = \max(0, \text{actual\_delivery\_at} - \text{promised\_delivery\_at} - \text{grace\_period\_hours})$$
- **Deterministic Delay Explainability**: Attributes delay causes to concrete telematics evidence (weather events, facility gate queues, carrier dwell).
- **Automated Anomaly Detection**: Benchmarks detectors against supervised ground truth across 4 mandatory categories (ingestion inversion, route breaks, future leakage, and status reconciliation conflicts).
- **12-Page Operations Dashboard**: Comprehensive Streamlit Control Tower with interactive maps, time-series charts, and time-travel replay.
- **Enterprise REST API**: 16 endpoints with full Pydantic data contract validation.
- **Deterministic Synthetic Data Generation**: Supports both `--mode starter` (500 shipments) and `--mode full` (50,000 shipments) with fixed-seed dual-run reproducibility.

---

## 2. System Architecture

```text
Synthetic Generator (src/data_generation/) ───► Dual Modes: Starter (500) | Full (50,000)
                    │
                    ▼
       16 Relational Lake Entities (data/existing/ & data/generated/)
                    │
                    ▼
       Data Lake Validation (53 Rules) (src/data/validator.py)
                    │
                    ▼
     DuckDB Analytical Lakehouse (data/analytics/logistics.duckdb)
                    │
       ┌────────────┴────────────┐
       ▼                         ▼
Point-in-Time Features     Intelligence Engines
  (src/features/)            (src/anomaly/, src/intelligence/, src/data/sla.py)
       │                         │
       ▼                         │
ML Models (src/models/)          │
  - GBDT ETA Regressor (P50/P90) │
  - Delay Risk Classifier        │
       │                         │
       └────────────┬────────────┘
                    │
                    ▼
          FastAPI Backend (app/) ──► 16 Production REST Endpoints
                    │
                    ▼
    12-Page Streamlit Operations Control Tower (frontend/)
```

---

## 3. Technology Stack

- **Runtime**: Python 3.11+
- **Analytical Storage**: DuckDB
- **Data Engineering**: Pandas, NumPy
- **Machine Learning**: Scikit-Learn (HistGradientBoosting, RandomForest), Joblib
- **API Framework**: FastAPI, Pydantic, Starlette, Uvicorn
- **Frontend & Visualization**: Streamlit, Plotly Express & Graph Objects
- **Testing & Quality**: Pytest, Streamlit `AppTest`

---

## 4. Quickstart Guide

### 4.1 Prerequisites & Installation
Ensure you are using system Python 3.11+:
```powershell
pip install -r requirements.txt
```

### 4.2 Generate Synthetic Data
Generate the deterministic starter dataset (500 shipments, 15 facilities, 8 carriers, 45 disruptions) with random seed `20261022`:
```powershell
python -m data.generate_dataset --mode starter --seed 20261022 --force
```

### 4.3 Initialize DuckDB & Analytical Lakehouse
Load CSV tables, validate 53 lake integrity rules, compute derived attributes, and populate DuckDB:
```powershell
python -m src.data.initialize
```

### 4.4 Export Datasets & Standalone SQL Scripts
Generate CSV, JSON, and standalone SQL schema/seed scripts:
```powershell
python -m src.data.exporter
```

### 4.5 Launch FastAPI Backend
```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
- Interactive OpenAPI Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- ReDoc Docs: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### 4.6 Launch Streamlit Control Tower
```powershell
streamlit run frontend/streamlit_app.py
```
- Web Interface: [http://localhost:8501](http://localhost:8501)

---

## 5. Streamlit Control Tower — 12-Page Map

| Page | Title | Purpose |
|---|---|---|
| **Page 1** | `Executive Overview` | Network-wide KPI cards, volume trends, on-time rates |
| **Page 2** | `Shipment Control Tower` | Real-time shipment status board, delay filters, carrier filter |
| **Page 3** | `Shipment Intelligence` | Single shipment deep dive, legs timeline, ETA prediction comparison |
| **Page 4** | `Delay Analytics & Root Cause`| Root-cause delay attribution, weather vs congestion breakdown |
| **Page 5** | `Anomaly Intelligence` | Ground-truth benchmark audit, detected telematics defects |
| **Page 6** | `Weather Disruption Monitoring`| Meteorological hazard tracking, corridor impact hours |
| **Page 7** | `Facility Congestion Monitoring`| Hub queue depths, dwell wait times, bottleneck rankings |
| **Page 8** | `Carrier Performance` | Carrier reliability scorecard, risk quadrant, on-time benchmarks |
| **Page 9** | `Facility Operations` | Gate throughput capacity, terminal dwell time series |
| **Page 10** | `Model Performance & Calibration`| ETA regression error curves (MAE/RMSE), classifier ROC & calibration |
| **Page 11** | `Shipment Replay (Point-in-Time)`| Interactive time slider reconstructing past system states |
| **Page 12** | `Data Quality & Lake Validation` | Live 53-rule lake validation matrix, integrity audit console |

---

## 6. FastAPI REST Endpoints — 16 Routes

1. `GET /shipments` — Paginated shipments list with filters
2. `GET /shipments/{shipment_id}` — Single shipment details
3. `GET /shipments/{shipment_id}/legs` — Sequential legs belonging to shipment
4. `GET /shipments/{shipment_id}/events` — Chronological tracking scans
5. `GET /shipments/{shipment_id}/eta-history` — Historical point-in-time ETA snapshots
6. `GET /shipments/{shipment_id}/delay-reasons` — Delay causes attributed to shipment
7. `GET /carriers` — Master freight carriers and historical reliability
8. `GET /facilities` — Logistics facilities and throughput capacities
9. `GET /facilities/{facility_id}/queues` — Terminal gate queue time series
10. `GET /weather-events` — Weather hazard windows along corridors
11. `GET /routes` — Master transit corridors and standard transit hours
12. `GET /analytics/eta-performance` — Model error metrics (MAE, RMSE, P90)
13. `GET /analytics/delay-performance` — Delay rates by carrier, route, service level
14. `GET /analytics/anomalies` — Detected anomalies summary vs ground truth
15. `GET /validation/summary` — 53-rule validation summary
16. `GET /health` — Service health check and database connectivity

---

## 7. Testing & Verification

Run the complete test suite (78 tests covering all 22 specification areas):
```powershell
python -m pytest tests/ -v
```

Run the reproducibility verification harness:
```powershell
python -m src.data_generation.reproducibility
```

Verify standalone SQL database reconstruction:
```powershell
python -c "import duckdb; con = duckdb.connect(':memory:'); con.execute(open('data/exports/sql/schema.sql').read()); con.execute(open('data/exports/sql/seed_data.sql').read()); print('Shipments restored:', con.execute('SELECT count(*) FROM shipments').fetchone()[0])"
```

---

## 8. Documentation Index

- [Architecture & Data Flow](docs/ARCHITECTURE.md)
- [Data Dictionary (16 Entities)](docs/DATA_DICTIONARY.md)
- [Entity-Relationship Diagram & Constraints](docs/ENTITY_RELATIONSHIPS.md)
- [Business Rules & SLA Specification](docs/BUSINESS_RULES.md)
- [ETA Methodology & Zero Leakage Principle](docs/ETA_METHODOLOGY.md)
- [Anomaly Catalog & Benchmark Specifications](docs/ANOMALY_CATALOG.md)
- [Model Evaluation & Metrics](docs/MODEL_EVALUATION.md)
- [53 Data Lake Validation Rules](docs/VALIDATION_RULES.md)
- [Synthetic Data Generation Guide](docs/DATA_GENERATION.md)
- [API Documentation & Schemas](docs/API_DOCUMENTATION.md)
- [Reproducibility Verification Report](docs/REPRODUCIBILITY.md)
- [Source Code Manifest](docs/SOURCE_MANIFEST.md)
