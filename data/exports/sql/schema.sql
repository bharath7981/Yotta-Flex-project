-- Logistics Platform Analytical Database DDL
-- Auto-generated Schema Definition

CREATE TABLE IF NOT EXISTS service_levels (
    service_level_id VARCHAR(32) PRIMARY KEY,
    service_level_name VARCHAR(128) NOT NULL,
    promised_transit_hours DOUBLE NOT NULL,
    grace_period_hours DOUBLE NOT NULL,
    priority_tier INTEGER NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS delay_reasons (
    reason_id VARCHAR(32) PRIMARY KEY,
    reason_code VARCHAR(64) NOT NULL UNIQUE,
    reason_category VARCHAR(64) NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS carriers (
    carrier_id VARCHAR(32) PRIMARY KEY,
    carrier_name VARCHAR(128) NOT NULL,
    primary_mode VARCHAR(32) NOT NULL,
    on_time_rate DOUBLE NOT NULL,
    avg_delay_hours DOUBLE NOT NULL,
    reliability_score DOUBLE NOT NULL,
    transit_variability_hours DOUBLE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS facilities (
    facility_id VARCHAR(32) PRIMARY KEY,
    facility_name VARCHAR(128) NOT NULL,
    facility_type VARCHAR(64) NOT NULL,
    city VARCHAR(64) NOT NULL,
    country VARCHAR(32) NOT NULL,
    latitude DOUBLE NOT NULL,
    longitude DOUBLE NOT NULL,
    processing_capacity_per_hour INTEGER NOT NULL,
    avg_processing_time_hours DOUBLE NOT NULL
);

CREATE TABLE IF NOT EXISTS routes (
    route_id VARCHAR(32) PRIMARY KEY,
    origin_facility_id VARCHAR(32) NOT NULL,
    destination_facility_id VARCHAR(32) NOT NULL,
    standard_transit_hours DOUBLE NOT NULL,
    distance_km DOUBLE NOT NULL,
    primary_transport_mode VARCHAR(32) NOT NULL,
    is_congested BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS carrier_calendars (
    calendar_id VARCHAR(32) PRIMARY KEY,
    carrier_id VARCHAR(32) NOT NULL,
    operating_days VARCHAR(64) NOT NULL,
    opening_time VARCHAR(16) NOT NULL,
    closing_time VARCHAR(16) NOT NULL,
    holidays TEXT,
    non_operating_windows TEXT,
    effective_start_date TIMESTAMP NOT NULL,
    effective_end_date TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS facility_calendars (
    calendar_id VARCHAR(32) PRIMARY KEY,
    facility_id VARCHAR(32) NOT NULL,
    operating_days VARCHAR(64) NOT NULL,
    opening_time VARCHAR(16) NOT NULL,
    closing_time VARCHAR(16) NOT NULL,
    processing_capacity INTEGER NOT NULL,
    holidays TEXT,
    maintenance_closures TEXT,
    effective_start_date TIMESTAMP NOT NULL,
    effective_end_date TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS shipments (
    shipment_id VARCHAR(32) PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    carrier_id VARCHAR(32) NOT NULL,
    service_level VARCHAR(32) NOT NULL,
    origin_facility_id VARCHAR(32) NOT NULL,
    destination_facility_id VARCHAR(32) NOT NULL,
    origin_city VARCHAR(64) NOT NULL,
    destination_city VARCHAR(64) NOT NULL,
    weight_kg DOUBLE NOT NULL,
    distance_km DOUBLE NOT NULL,
    num_legs INTEGER NOT NULL,
    planned_transit_hours DOUBLE NOT NULL,
    planned_pickup_at TIMESTAMP NOT NULL,
    planned_delivery_at TIMESTAMP NOT NULL,
    promised_delivery_at TIMESTAMP NOT NULL,
    actual_pickup_at TIMESTAMP,
    actual_delivery_at TIMESTAMP,
    current_status VARCHAR(32) NOT NULL,
    priority VARCHAR(32) NOT NULL,
    route_id VARCHAR(32),
    sla_hours DOUBLE NOT NULL,
    delay_hours DOUBLE DEFAULT 0.0,
    is_delayed BOOLEAN DEFAULT FALSE,
    is_sla_breached INTEGER,
    grace_hours DOUBLE NOT NULL
);

CREATE TABLE IF NOT EXISTS shipment_legs (
    leg_id VARCHAR(32) PRIMARY KEY,
    shipment_id VARCHAR(32) NOT NULL,
    leg_sequence INTEGER NOT NULL,
    route_id VARCHAR(32),
    origin_facility_id VARCHAR(32) NOT NULL,
    destination_facility_id VARCHAR(32) NOT NULL,
    transport_mode VARCHAR(32) NOT NULL,
    planned_departure_at TIMESTAMP NOT NULL,
    planned_arrival_at TIMESTAMP NOT NULL,
    actual_departure_at TIMESTAMP,
    actual_arrival_at TIMESTAMP,
    leg_status VARCHAR(32) NOT NULL,
    distance_km DOUBLE NOT NULL
);

CREATE TABLE IF NOT EXISTS tracking_events (
    event_id VARCHAR(32) PRIMARY KEY,
    shipment_id VARCHAR(32) NOT NULL,
    leg_id VARCHAR(32),
    carrier_id VARCHAR(32) NOT NULL,
    facility_id VARCHAR(32) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    event_time TIMESTAMP NOT NULL,
    ingested_at TIMESTAMP NOT NULL,
    event_location VARCHAR(128),
    event_source VARCHAR(64),
    event_sequence_number INTEGER NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS facility_queues (
    queue_id VARCHAR(32) PRIMARY KEY,
    facility_id VARCHAR(32) NOT NULL,
    observed_at TIMESTAMP NOT NULL,
    ingested_at TIMESTAMP NOT NULL,
    queue_length INTEGER NOT NULL,
    avg_waiting_time_minutes DOUBLE NOT NULL,
    processing_capacity INTEGER NOT NULL,
    utilization DOUBLE NOT NULL,
    expected_processing_delay_hours DOUBLE NOT NULL,
    is_disrupted INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS disruptions (
    disruption_id VARCHAR(32) PRIMARY KEY,
    facility_id VARCHAR(32) NOT NULL,
    disruption_type VARCHAR(64) NOT NULL,
    severity VARCHAR(32) NOT NULL,
    started_at TIMESTAMP NOT NULL,
    ended_at TIMESTAMP,
    reported_at TIMESTAMP NOT NULL,
    description TEXT,
    impact_description TEXT
);

CREATE TABLE IF NOT EXISTS weather_events (
    weather_id VARCHAR(32) PRIMARY KEY,
    facility_id VARCHAR(32) NOT NULL,
    route_id VARCHAR(32),
    weather_type VARCHAR(32) NOT NULL,
    severity VARCHAR(32) NOT NULL,
    started_at TIMESTAMP NOT NULL,
    ended_at TIMESTAMP NOT NULL,
    forecast_issued_at TIMESTAMP NOT NULL,
    observed_at TIMESTAMP NOT NULL,
    precipitation_mm DOUBLE NOT NULL,
    wind_speed_kmh DOUBLE NOT NULL,
    is_disruptive INTEGER NOT NULL,
    source VARCHAR(64)
);

CREATE TABLE IF NOT EXISTS eta_estimates (
    eta_id VARCHAR(64) PRIMARY KEY,
    shipment_id VARCHAR(32) NOT NULL,
    prediction_timestamp TIMESTAMP NOT NULL,
    predicted_arrival_timestamp TIMESTAMP NOT NULL,
    p50_eta TIMESTAMP NOT NULL,
    p90_eta TIMESTAMP NOT NULL,
    estimated_remaining_duration DOUBLE NOT NULL,
    delay_probability DOUBLE NOT NULL,
    confidence_score DOUBLE NOT NULL,
    model_version VARCHAR(64) NOT NULL,
    feature_cutoff_timestamp TIMESTAMP NOT NULL,
    source_event_ids TEXT,
    contributing_weather_event_ids TEXT,
    contributing_queue_observation_ids TEXT,
    explanation TEXT,
    snapshot_time TIMESTAMP,
    planned_delivery_at TIMESTAMP,
    predicted_delivery_at TIMESTAMP,
    predicted_remaining_hours DOUBLE,
    prediction_method VARCHAR(64),
    data_cutoff_at TIMESTAMP,
    max_ingested_at_used TIMESTAMP
);

CREATE TABLE IF NOT EXISTS shipment_status_history (
    history_id VARCHAR(32) PRIMARY KEY,
    shipment_id VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL,
    changed_at TIMESTAMP NOT NULL,
    recorded_at TIMESTAMP NOT NULL,
    reason TEXT,
    updated_by VARCHAR(64)
);

CREATE TABLE IF NOT EXISTS route_change_history (
    history_id VARCHAR(32) PRIMARY KEY,
    shipment_id VARCHAR(32) NOT NULL,
    change_type VARCHAR(64) NOT NULL,
    old_route_id VARCHAR(32),
    new_route_id VARCHAR(32),
    changed_at TIMESTAMP NOT NULL,
    recorded_at TIMESTAMP NOT NULL,
    impact_hours DOUBLE NOT NULL,
    reason TEXT
);

CREATE TABLE IF NOT EXISTS shipment_delay_reasons (
    association_id VARCHAR(32) PRIMARY KEY,
    shipment_id VARCHAR(32) NOT NULL,
    reason_id VARCHAR(32) NOT NULL,
    attributed_delay_hours DOUBLE NOT NULL,
    confidence_score DOUBLE NOT NULL,
    evidence_references TEXT
);