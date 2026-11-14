# Logistics Platform Data Dictionary

Comprehensive technical specification of all relational entities, schemas, operational definitions, and target variables.

---

## 1. Distinction: Weather Events vs Operational Disruptions

The platform explicitly distinguishes between two distinct types of disruption records:

### 1.1 `weather_events` (1,000 Records)
- **Nature**: External meteorological phenomena (convective storms, blizzards, heavy rain, gale-force winds, dense fog) impacting transportation corridors and geographical areas.
- **Key Columns**:
  - `weather_id` (PK): `WTH-2026-XXXXXX`
  - `facility_id` (FK): Originating/impacted network terminal hub.
  - `route_id` (FK, Nullable): Correlated transit corridor if applicable.
  - `weather_type`: `RAIN`, `STORM`, `SNOW`, `FOG`, `HIGH_WIND`, `BLIZZARD`.
  - `severity`: `LOW`, `MODERATE`, `SEVERE`, `EXTREME`.
  - `started_at` & `ended_at`: Atmospheric event duration.
  - `forecast_issued_at`: Pre-event meteorology forecast release (6 to 48 hours prior).
  - `observed_at`: Ground telematics station confirmation.
  - `precipitation_mm` & `wind_speed_kmh`: Quantitative atmospheric telemetry.
  - `is_disruptive`: Binary indicator (1 if severity $\ge$ SEVERE or wind $\ge$ 60 km/h).

### 1.2 `disruptions` (1,000 Records)
- **Nature**: Internal and terminal facility operational disruptions (gate system downtime, customs holds, container crane mechanical failures, facility yard congestion, labor shift shortages).
- **Key Columns**:
  - `disruption_id` (PK): `DIS-XXXX`
  - `facility_id` (FK): Affected facility where operational capacity is degraded.
  - `disruption_type`: `CONGESTION`, `EQUIPMENT_FAILURE`, `CUSTOMS_HOLD`, `LABOR_ACTION`, `WEATHER_SLOWDOWN`, `GATE_SYSTEM_DOWN`.
  - `severity`: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.
  - `started_at`, `ended_at`, `reported_at`: Lifecycle timestamps of the operational bottleneck.
  - `description` & `impact_description`: Detailed operational context and throughput impact.

---

## 2. Machine Learning Target Definitions

To eliminate historical evaluation confusion, the platform establishes strict standard terminology:

### 2.1 Primary Predictive Target: `is_delayed_target`
$$\text{is\_delayed\_target} = \mathbb{I}(\text{actual\_delivery\_at} > \text{planned\_delivery\_at})$$
- **Operational Meaning**: Schedule variance. Indicates whether a shipment delivered later than its originally planned schedule.
- **Dataset Prevalence**: **22.5%** in the held-out test partition (2,470 delayed snapshots of 10,970 test snapshots).
- **ML Suitability**: Optimal positive-class volume for training calibrated gradient boosted classifiers, generating actionable early warnings before delays compound.

### 2.2 Secondary Contractual Metric: `is_sla_breached_target`
$$\text{is\_sla\_breached\_target} = \mathbb{I}(\text{actual\_delivery\_at} > \text{promised\_delivery\_at} + \text{grace\_period\_hours})$$
- **Operational Meaning**: Commercial legal penalty breach. Evaluates contractual SLA violations after absorbing service-level grace buffers:
  - `PRIORITY`: 0.5 hours grace
  - `EXPRESS`: 1.0 hours grace
  - `STANDARD`: 2.0 hours grace
  - `ECONOMY`: 4.0 hours grace
- **Dataset Prevalence**: Rare event (~3.7% of shipments). Documented as an escalation KPI rather than a daily alerting model target to prevent model collapse.

---

## 3. Relational Lake Entities & Schemas

### 3.1 Master Entities
1. `service_levels`: SLA commitments, promised transit hours, grace buffers, priority tiers.
2. `carriers`: Freight carriers, operational modes (TRUCK, AIR, RAIL, SEA), on-time ratings.
3. `carrier_calendars`: Working days, holiday calendars, operating hours per carrier.
4. `facilities`: Hubs, distribution centers, cross-dock terminals, capacity per hour.
5. `facility_calendars`: Facility operational operating windows and holiday closures.
6. `routes`: Origin-destination pairs, standard transit hours, geographical distance in km.
7. `delay_reasons`: Taxonomy of delay codes (WEATHER, CONGESTION, CARRIER_DWELL, MECHANICAL, CUSTOMS).

### 3.2 Transactional Entities
8. `shipments`: Core shipment tracking header (50,000 records). Contains origin/destination, timestamps, weight, priority.
9. `shipment_legs`: Multi-modal transportation legs (112,429 records) connecting origin to destination.
10. `tracking_events`: Telematics scan events (327,072 records) with occurrence (`event_time`) and ingestion (`ingested_at`) timestamps.
11. `shipment_status_history`: State machine audit trail (`MANIFESTED` $\to$ `PICKED_UP` $\to$ `IN_TRANSIT` $\to$ `OUT_FOR_DELIVERY` $\to$ `DELIVERED`).
12. `route_change_history` / `route_changes`: Dynamic reroutes executed during transit (3,257 records).
13. `shipment_delay_reasons`: Association of verified root causes with attributed delay hours.
14. `facility_queues`: Periodic gate queue observations (5,700 records), utilization, and wait minutes.
15. `eta_estimates` / `eta_snapshots`: Point-in-time ETA predictions (95,088 records) with snapshot timestamps and data cutoffs.
16. `ground_truth_anomalies`: Labeled anomalies (60 records) for detector benchmarking across 4 mandatory defect categories.
