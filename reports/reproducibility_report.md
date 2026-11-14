# Pipeline Reproducibility Verification Report

- **Verification Status:** `PASSED`
- **Seed Used:** `20261022`
- **Mode:** `FULL` (50,000 Shipments)
- **Total Tables Evaluated:** 22
- **File Checksums (SHA-256) Identity:** `100% IDENTICAL`
- **Primary Key Digest Identity:** `100% IDENTICAL`
- **Ground-Truth JSON Identity:** `100% IDENTICAL`

## Table-by-Table Reproducibility Matrix

| Table | Rows (Run A / Run B) | Primary Key Hash | SHA-256 Checksum | Data Equals | Status |
|---|---|---|---|---|---|
| `carrier_calendars` | 12 / 12 | MATCH | MATCH | True | ✅ MATCH |
| `carriers` | 12 / 12 | MATCH | MATCH | True | ✅ MATCH |
| `delay_reasons` | 8 / 8 | MATCH | MATCH | True | ✅ MATCH |
| `disruptions` | 1000 / 1000 | MATCH | MATCH | True | ✅ MATCH |
| `eta_estimates` | 95088 / 95088 | MATCH | MATCH | True | ✅ MATCH |
| `eta_snapshots` | 95088 / 95088 | MATCH | MATCH | True | ✅ MATCH |
| `facilities` | 100 / 100 | MATCH | MATCH | True | ✅ MATCH |
| `facility_calendars` | 100 / 100 | MATCH | MATCH | True | ✅ MATCH |
| `facility_queues` | 5700 / 5700 | MATCH | MATCH | True | ✅ MATCH |
| `ground_truth` | 60 / 60 | MATCH | MATCH | True | ✅ MATCH |
| `ground_truth_anomalies` | 60 / 60 | MATCH | MATCH | True | ✅ MATCH |
| `route_change_history` | 3257 / 3257 | MATCH | MATCH | True | ✅ MATCH |
| `route_changes` | 3257 / 3257 | MATCH | MATCH | True | ✅ MATCH |
| `routes` | 9900 / 9900 | MATCH | MATCH | True | ✅ MATCH |
| `service_levels` | 4 / 4 | MATCH | MATCH | True | ✅ MATCH |
| `shipment_delay_reasons` | 17601 / 17601 | MATCH | MATCH | True | ✅ MATCH |
| `shipment_legs` | 112429 / 112429 | MATCH | MATCH | True | ✅ MATCH |
| `shipment_status_history` | 124962 / 124962 | MATCH | MATCH | True | ✅ MATCH |
| `shipments` | 50000 / 50000 | MATCH | MATCH | True | ✅ MATCH |
| `tracking_events` | 327072 / 327072 | MATCH | MATCH | True | ✅ MATCH |
| `weather_events` | 1000 / 1000 | MATCH | MATCH | True | ✅ MATCH |
| `weather_forecasts` | 1000 / 1000 | MATCH | MATCH | True | ✅ MATCH |

## Ground-Truth Anomaly Consistency
Both runs produced identical ground-truth anomalies with identical injection descriptions, primary key alignments, and target entities.

## Conclusion
The generation pipeline is strictly deterministic when executed with a fixed seed. No non-deterministic floating-point or timestamp leakage was detected across runs.
