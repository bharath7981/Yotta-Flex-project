"""Master Data Generation Module
Generates all 7 Master Data Entities:
1. Carriers
2. Facilities
3. Routes
4. ServiceLevels
5. DelayReasons
6. CarrierCalendars
7. FacilityCalendars
"""

from datetime import datetime, date
import numpy as np
import pandas as pd

from src.data.id_generator import (
    format_carrier_id,
    format_facility_id,
    format_route_id,
    format_delay_reason_id,
    format_carrier_cal_id,
    format_facility_cal_id,
)


def generate_service_levels() -> pd.DataFrame:
    """Generate the authoritative ServiceLevel master table."""
    records = [
        {
            "service_level_id": "PRIORITY",
            "service_level_name": "Priority Express Delivery",
            "promised_transit_hours": 24.0,
            "grace_period_hours": 0.5,
            "priority_tier": 1,
            "description": "Next-day urgent freight with 30-minute SLA grace window.",
        },
        {
            "service_level_id": "EXPRESS",
            "service_level_name": "Expedited 2-Day Freight",
            "promised_transit_hours": 48.0,
            "grace_period_hours": 1.0,
            "priority_tier": 2,
            "description": "Two-day expedited transport with 1-hour SLA grace window.",
        },
        {
            "service_level_id": "STANDARD",
            "service_level_name": "Standard Regional Ground",
            "promised_transit_hours": 120.0,
            "grace_period_hours": 2.0,
            "priority_tier": 3,
            "description": "Standard 5-day scheduled transit with 2-hour SLA grace window.",
        },
        {
            "service_level_id": "ECONOMY",
            "service_level_name": "Economy Deferred Freight",
            "promised_transit_hours": 168.0,
            "grace_period_hours": 4.0,
            "priority_tier": 4,
            "description": "Deferred 7-day economical transport with 4-hour SLA grace window.",
        },
    ]
    return pd.DataFrame(records)


def generate_delay_reasons() -> pd.DataFrame:
    """Generate the authoritative DelayReason master table."""
    reasons = [
        ("WEATHER_DISRUPTION", "ENVIRONMENTAL", "Severe convective storms, snowstorms, flooding, or gale winds impeding transit."),
        ("FACILITY_CONGESTION", "OPERATIONAL", "Inbound sorting facility or cross-dock queue exceeding 90% utilization."),
        ("CARRIER_DELAY", "CARRIER", "Mechanical breakdown, driver hours-of-service limits, or fleet scheduling shortfall."),
        ("ROUTE_CHANGE", "NETWORK", "En-route detour caused by road closures, rail bridge maintenance, or airspace blocks."),
        ("CUSTOMS_DELAY", "CUSTOMS", "Regulatory inspection or import documentation hold at border clearing checkpoint."),
        ("MISSED_CONNECTION", "OPERATIONAL", "Inbound feeder leg arrived past hub departure cutoff window."),
        ("OPERATIONAL_HOLD", "OPERATIONAL", "Security audit, weight reconciliation, or hazmat containment inspection."),
        ("UNKNOWN", "OTHER", "Unclassified transit delay pending telemetry reconciliation."),
    ]
    records = []
    for i, (code, cat, desc) in enumerate(reasons, start=1):
        records.append({
            "reason_id": format_delay_reason_id(i),
            "reason_code": code,
            "reason_category": cat,
            "description": desc,
        })
    return pd.DataFrame(records)


def generate_carriers(rng: np.random.Generator, n_carriers: int = 8) -> pd.DataFrame:
    """Generate Carrier master table."""
    names = [
        "FastFreight Express", "GlobalAir Cargo", "SteadyHaul Logistics",
        "SwiftFleet Transport", "ReliableCarriers National", "OceanBridge Intermodal",
        "AirPrime Direct", "RailConnect Freight", "ApexTrans Continental",
        "MetroHaul Urban", "NordicRoute Freight", "PinnacleLogistics"
    ]
    modes = ["TRUCK", "AIR", "TRUCK", "TRUCK", "RAIL", "OCEAN", "AIR", "RAIL", "TRUCK", "TRUCK", "TRUCK", "AIR"]
    records = []
    count = max(8, n_carriers)
    for i in range(count):
        name = names[i % len(names)]
        if i >= len(names):
            name = f"{name} #{i+1}"
        mode = modes[i % len(modes)]
        records.append({
            "carrier_id": format_carrier_id(i + 1),
            "carrier_name": name,
            "primary_mode": mode,
            "on_time_rate": round(float(rng.uniform(0.70, 0.94)), 4),
            "avg_delay_hours": round(float(rng.uniform(2.0, 18.0)), 2),
            "reliability_score": round(float(rng.uniform(0.72, 0.98)), 4),
            "transit_variability_hours": round(float(rng.uniform(1.0, 8.0)), 2),
            "is_active": True,
        })
    return pd.DataFrame(records)


def generate_facilities(rng: np.random.Generator, n_facilities: int = 15, network: str = "us") -> pd.DataFrame:
    """Generate Facility master table."""
    us_cities = [
        ("New York", "US", 40.7128, -74.0060), ("Los Angeles", "US", 34.0522, -118.2437),
        ("Chicago", "US", 41.8781, -87.6298), ("Houston", "US", 29.7604, -95.3698),
        ("Miami", "US", 25.7617, -80.1918), ("Seattle", "US", 47.6062, -122.3321),
        ("Dallas", "US", 32.7767, -96.7970), ("Atlanta", "US", 33.7490, -84.3880),
        ("Denver", "US", 39.7392, -104.9903), ("Phoenix", "US", 33.4484, -112.0740),
        ("Philadelphia", "US", 39.9526, -75.1652), ("San Francisco", "US", 37.7749, -122.4194),
        ("Boston", "US", 42.3601, -71.0589), ("Detroit", "US", 42.3314, -83.0458),
        ("Memphis", "US", 35.1495, -90.0490), ("Minneapolis", "US", 44.9778, -93.2650),
        ("Charlotte", "US", 35.2271, -80.8431), ("Salt Lake City", "US", 40.7608, -111.8910),
        ("Kansas City", "US", 39.0997, -94.5786), ("Indianapolis", "US", 39.7684, -86.1581),
    ]
    india_cities = [
        ("Mumbai", "IN", 19.0760, 72.8777), ("Delhi", "IN", 28.7041, 77.1025),
        ("Bengaluru", "IN", 12.9716, 77.5946), ("Hyderabad", "IN", 17.3850, 78.4867),
        ("Chennai", "IN", 13.0827, 80.2707), ("Kolkata", "IN", 22.5726, 88.3639),
        ("Ahmedabad", "IN", 23.0225, 72.5714), ("Pune", "IN", 18.5204, 73.8567),
        ("Jaipur", "IN", 26.9124, 75.7873), ("Surat", "IN", 21.1702, 72.8311),
        ("Lucknow", "IN", 26.8467, 80.9462), ("Nagpur", "IN", 21.1458, 79.0882),
        ("Indore", "IN", 22.7196, 75.8577), ("Coimbatore", "IN", 11.0168, 76.9558),
        ("Kochi", "IN", 9.9312, 76.2673), ("Visakhapatnam", "IN", 17.6868, 83.2185),
    ]

    base_cities = india_cities if network == "india" else us_cities
    types = ["ORIGIN_HUB", "DISTRIBUTION_CENTER", "SORTING_FACILITY", "CROSS_DOCK", "DESTINATION_HUB"]
    records = []

    for i in range(n_facilities):
        c_name, country, lat, lon = base_cities[i % len(base_cities)]
        f_type = types[i % len(types)]
        suffix = f"Hub {i+1}" if i >= len(base_cities) else f_type.replace("_", " ").title()
        
        # Add slight jitter for duplicate cities in large setups
        lat_jitter = float(rng.normal(0, 0.08)) if i >= len(base_cities) else 0.0
        lon_jitter = float(rng.normal(0, 0.08)) if i >= len(base_cities) else 0.0

        records.append({
            "facility_id": format_facility_id(i + 1),
            "facility_name": f"{c_name} {suffix}",
            "facility_type": f_type,
            "city": c_name,
            "country": country,
            "latitude": round(lat + lat_jitter, 4),
            "longitude": round(lon + lon_jitter, 4),
            "processing_capacity_per_hour": int(rng.integers(60, 250)),
            "avg_processing_time_hours": round(float(rng.uniform(1.0, 5.0)), 2),
        })
    return pd.DataFrame(records)


def generate_routes(facilities_df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Generate Route master network connecting facilities."""
    fac_ids = facilities_df["facility_id"].tolist()
    fac_lookup = facilities_df.set_index("facility_id")
    records = []
    route_seq = 1

    # Connect hub networks: if <= 30 facilities, connect all pairs
    for i, orig_id in enumerate(fac_ids):
        dests = [d for d in fac_ids if d != orig_id]
        if len(fac_ids) <= 30:
            chosen_dests = dests
        else:
            sample_size = min(len(dests), 15)
            chosen_dests = rng.choice(dests, size=sample_size, replace=False)
        for dest_id in chosen_dests:
            orig = fac_lookup.loc[orig_id]
            dest = fac_lookup.loc[dest_id]
            # Haversine distance approximate
            d_km = round(float(np.sqrt((orig["latitude"] - dest["latitude"])**2 + (orig["longitude"] - dest["longitude"])**2) * 111.0), 1)
            d_km = max(50.0, d_km)
            mode = "AIR" if d_km > 1800 else ("RAIL" if d_km > 800 and rng.random() > 0.5 else "TRUCK")
            speed = 700.0 if mode == "AIR" else (55.0 if mode == "RAIL" else 65.0)
            transit_h = round(d_km / speed, 1)

            records.append({
                "route_id": format_route_id(route_seq),
                "origin_facility_id": orig_id,
                "destination_facility_id": dest_id,
                "standard_transit_hours": transit_h,
                "distance_km": d_km,
                "primary_transport_mode": mode,
                "is_congested": bool(rng.random() < 0.12),
            })
            route_seq += 1
    return pd.DataFrame(records)


def generate_carrier_calendars(carriers_df: pd.DataFrame) -> pd.DataFrame:
    """Generate CarrierCalendar operational windows."""
    records = []
    for i, row in enumerate(carriers_df.itertuples(), start=1):
        c_id = row.carrier_id
        records.append({
            "calendar_id": format_carrier_cal_id(i),
            "carrier_id": c_id,
            "operating_days": "MON-SAT" if row.primary_mode == "TRUCK" else "ALL",
            "opening_time": "06:00:00",
            "closing_time": "22:00:00",
            "holidays": "2026-07-04,2026-09-07,2026-11-26,2026-12-25",
            "non_operating_windows": "SUN:00:00-06:00" if row.primary_mode == "TRUCK" else "NONE",
            "effective_start_date": "2026-01-01T00:00:00Z",
            "effective_end_date": "2026-12-31T23:59:59Z",
        })
    return pd.DataFrame(records)


def generate_facility_calendars(facilities_df: pd.DataFrame) -> pd.DataFrame:
    """Generate FacilityCalendar operational windows."""
    records = []
    for i, row in enumerate(facilities_df.itertuples(), start=1):
        f_id = row.facility_id
        records.append({
            "calendar_id": format_facility_cal_id(i),
            "facility_id": f_id,
            "operating_days": "ALL" if row.facility_type in ["ORIGIN_HUB", "DESTINATION_HUB"] else "MON-SAT",
            "opening_time": "00:00:00" if row.facility_type in ["ORIGIN_HUB", "DESTINATION_HUB"] else "05:00:00",
            "closing_time": "23:59:59" if row.facility_type in ["ORIGIN_HUB", "DESTINATION_HUB"] else "23:00:00",
            "processing_capacity": row.processing_capacity_per_hour,
            "holidays": "2026-07-04,2026-12-25",
            "maintenance_closures": "2026-08-15:02:00-06:00",
            "effective_start_date": "2026-01-01T00:00:00Z",
            "effective_end_date": "2026-12-31T23:59:59Z",
        })
    return pd.DataFrame(records)
