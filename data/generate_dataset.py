"""
Logistics Dataset Generator
============================
Generates a realistic synthetic logistics dataset for the ETA Prediction & Delay Intelligence Platform.
All timestamps are UTC ISO-8601 strings.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
from pathlib import Path

np.random.seed(42)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "existing")
os.makedirs(OUTPUT_DIR, exist_ok=True)

NUM_SHIPMENTS = 500
NUM_CARRIERS = 8
NUM_FACILITIES = 15
BASE_DATE = datetime(2026, 6, 1)
END_DATE = datetime(2026, 10, 31)

def ts(dt):
    """Format datetime to ISO string."""
    if isinstance(dt, pd.Timestamp):
        dt = dt.to_pydatetime().replace(tzinfo=None)
    if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def generate_carriers():
    carriers = []
    names = ["FastFreight","GlobalExpress","SteadyHaul","SwiftLogistics",
             "ReliableCarriers","OceanBridge","AirPrime","RailConnect"]
    modes = ["TRUCK","AIR","RAIL","TRUCK","TRUCK","OCEAN","AIR","RAIL"]
    for i,(name,mode) in enumerate(zip(names,modes)):
        carriers.append({
            "carrier_id": f"CAR-{i+1:03d}",
            "carrier_name": name,
            "primary_mode": mode,
            "on_time_rate": round(np.random.uniform(0.65,0.95),3),
            "avg_delay_hours": round(np.random.uniform(2,24),1),
            "reliability_score": round(np.random.uniform(0.6,0.98),3),
            "transit_variability_hours": round(np.random.uniform(1,12),1),
        })
    df = pd.DataFrame(carriers)
    df.to_csv(os.path.join(OUTPUT_DIR,"carriers.csv"),index=False)
    return df

def generate_facilities(network="us"):
    facilities = []
    if network == "india":
        cities = [
            ("Mumbai","IN",19.07,72.87),("Delhi","IN",28.70,77.10),
            ("Bengaluru","IN",12.97,77.59),("Hyderabad","IN",17.38,78.48),
            ("Chennai","IN",13.08,80.27),("Kolkata","IN",22.57,88.36),
            ("Ahmedabad","IN",23.02,72.57),("Pune","IN",18.52,73.85),
            ("Jaipur","IN",26.91,75.78),("Surat","IN",21.17,72.83),
            ("Lucknow","IN",26.84,80.94),("Nagpur","IN",21.14,79.08),
            ("Indore","IN",22.71,75.85),("Coimbatore","IN",11.01,76.95),
            ("Kochi","IN",9.93,76.26),
        ]
    else:
        cities = [
            ("New York","US",40.71,-74.01),("Los Angeles","US",34.05,-118.24),
            ("Chicago","US",41.88,-87.63),("Houston","US",29.76,-95.37),
            ("Miami","US",25.76,-80.19),("Seattle","US",47.61,-122.33),
            ("Dallas","US",32.78,-96.80),("Atlanta","US",33.75,-84.39),
            ("Denver","US",39.74,-104.99),("Phoenix","US",33.45,-112.07),
            ("Philadelphia","US",39.95,-75.17),("San Francisco","US",37.77,-122.42),
            ("Boston","US",42.36,-71.06),("Detroit","US",42.33,-83.05),
            ("Memphis","US",35.15,-90.05),
        ]
    types = ["ORIGIN_HUB","DISTRIBUTION_CENTER","SORTING_FACILITY","CROSS_DOCK","DESTINATION_HUB"]*3
    for i,(city,country,lat,lon) in enumerate(cities):
        facilities.append({
            "facility_id": f"FAC-{i+1:03d}",
            "facility_name": f"{city} {types[i].replace('_',' ').title()}",
            "facility_type": types[i],
            "city": city, "country": country,
            "latitude": lat, "longitude": lon,
            "processing_capacity_per_hour": int(np.random.uniform(50,200)),
            "avg_processing_time_hours": round(np.random.uniform(1,6),1),
        })
    df = pd.DataFrame(facilities)
    df.to_csv(os.path.join(OUTPUT_DIR,"facilities.csv"),index=False)
    return df

def generate_shipments(carriers_df, facilities_df, n_shipments=NUM_SHIPMENTS):
    shipments = []
    service_levels = ["STANDARD","EXPRESS","PRIORITY","ECONOMY"]
    sla_hours = {"STANDARD":120,"EXPRESS":48,"PRIORITY":24,"ECONOMY":168}
    statuses = ["IN_TRANSIT","DELIVERED","DELAYED","AT_FACILITY","CANCELLED"]
    status_weights = [0.20,0.55,0.12,0.08,0.05]
    for i in range(n_shipments):
        created = BASE_DATE + timedelta(hours=np.random.uniform(0,(END_DATE-BASE_DATE).total_seconds()/3600))
        service = np.random.choice(service_levels, p=[0.4,0.3,0.15,0.15])
        carrier = carriers_df.sample(1).iloc[0]
        fac_indices = np.random.choice(len(facilities_df),2,replace=False)
        origin = facilities_df.iloc[fac_indices[0]]
        dest = facilities_df.iloc[fac_indices[1]]
        dist_km = round(np.sqrt((origin["latitude"]-dest["latitude"])**2+(origin["longitude"]-dest["longitude"])**2)*111,1)
        planned_transit = sla_hours[service]*np.random.uniform(0.5,0.85)
        planned_delivery = created + timedelta(hours=planned_transit)
        promised_delivery = created + timedelta(hours=sla_hours[service])
        status = np.random.choice(statuses, p=status_weights)
        actual_delivery = None
        if status == "DELIVERED":
            delay = np.random.choice([0,1], p=[carrier["on_time_rate"],1-carrier["on_time_rate"]])
            if delay:
                actual_delivery = planned_delivery + timedelta(hours=np.random.uniform(1,carrier["avg_delay_hours"]*2))
            else:
                actual_delivery = planned_delivery - timedelta(hours=np.random.uniform(0,planned_transit*0.1))
        weight_kg = round(np.random.uniform(0.5,500),1)
        num_legs = np.random.randint(2,6)
        shipments.append({
            "shipment_id": f"SHP-{i+1:05d}",
            "created_at": ts(created),
            "service_level": service,
            "carrier_id": carrier["carrier_id"],
            "origin_facility_id": origin["facility_id"],
            "destination_facility_id": dest["facility_id"],
            "origin_city": origin["city"],
            "destination_city": dest["city"],
            "weight_kg": weight_kg,
            "distance_km": dist_km,
            "num_legs": num_legs,
            "planned_transit_hours": round(planned_transit,1),
            "planned_delivery_at": ts(planned_delivery),
            "promised_delivery_at": ts(promised_delivery),
            "actual_delivery_at": ts(actual_delivery) if actual_delivery else None,
            "current_status": status,
            "sla_hours": sla_hours[service],
        })
    df = pd.DataFrame(shipments)
    df.to_csv(os.path.join(OUTPUT_DIR,"shipments.csv"),index=False)
    return df

def generate_shipment_legs(shipments_df, facilities_df):
    legs = []
    transport_modes = ["TRUCK","AIR","RAIL","OCEAN"]
    for _, ship in shipments_df.iterrows():
        n_legs = ship["num_legs"]
        created = datetime.strptime(ship["created_at"],"%Y-%m-%dT%H:%M:%SZ")
        available = facilities_df[~facilities_df["facility_id"].isin([ship["origin_facility_id"],ship["destination_facility_id"]])]
        n_intermediate = min(n_legs-1, len(available))
        intermediates = available.sample(min(n_intermediate, len(available))) if n_intermediate > 0 else pd.DataFrame()
        chain = [ship["origin_facility_id"]]
        for _,fac in intermediates.iterrows():
            chain.append(fac["facility_id"])
        chain.append(ship["destination_facility_id"])
        transit_per_leg = ship["planned_transit_hours"]/len(chain)
        current_time = created
        for j in range(len(chain)-1):
            dep_time = current_time + timedelta(hours=np.random.uniform(0.5,3))
            arr_time = dep_time + timedelta(hours=transit_per_leg*np.random.uniform(0.8,1.3))
            actual_dep = None
            actual_arr = None
            leg_status = "PLANNED"
            if ship["current_status"] in ["DELIVERED","DELAYED","IN_TRANSIT","AT_FACILITY"]:
                elapsed_fraction = min(1.0, j/max(len(chain)-2,1))
                if ship["current_status"] == "DELIVERED" or (elapsed_fraction < 0.7 and ship["current_status"] != "CANCELLED"):
                    actual_dep = dep_time + timedelta(hours=np.random.uniform(-0.5,2))
                    actual_arr = arr_time + timedelta(hours=np.random.uniform(-1,4))
                    leg_status = "COMPLETED"
                elif ship["current_status"] == "IN_TRANSIT" and j == len(chain)-2:
                    actual_dep = dep_time + timedelta(hours=np.random.uniform(-0.5,2))
                    leg_status = "IN_TRANSIT"
            mode = np.random.choice(transport_modes, p=[0.5,0.2,0.2,0.1])
            legs.append({
                "leg_id": f"{ship['shipment_id']}-LEG-{j+1:02d}",
                "shipment_id": ship["shipment_id"],
                "leg_sequence": j+1,
                "origin_facility_id": chain[j],
                "destination_facility_id": chain[j+1],
                "transport_mode": mode,
                "planned_departure_at": ts(dep_time),
                "planned_arrival_at": ts(arr_time),
                "actual_departure_at": ts(actual_dep) if actual_dep else None,
                "actual_arrival_at": ts(actual_arr) if actual_arr else None,
                "leg_status": leg_status,
                "distance_km": round(ship["distance_km"]/(len(chain)-1),1),
            })
            current_time = arr_time
    df = pd.DataFrame(legs)
    df.to_csv(os.path.join(OUTPUT_DIR,"shipment_legs.csv"),index=False)
    return df

def generate_tracking_events(shipments_df, legs_df):
    events = []
    evt_id = 0
    for _, ship in shipments_df.iterrows():
        ship_legs = legs_df[legs_df["shipment_id"]==ship["shipment_id"]].sort_values("leg_sequence")
        for _, leg in ship_legs.iterrows():
            if leg["leg_status"] in ["COMPLETED","IN_TRANSIT"]:
                if pd.notna(leg["actual_departure_at"]):
                    dep_time = datetime.strptime(leg["actual_departure_at"],"%Y-%m-%dT%H:%M:%SZ")
                else:
                    dep_time = datetime.strptime(leg["planned_departure_at"],"%Y-%m-%dT%H:%M:%SZ")
                ingestion_delay = timedelta(minutes=np.random.uniform(1,120))
                evt_id += 1
                events.append({
                    "event_id": f"EVT-{evt_id:06d}",
                    "shipment_id": ship["shipment_id"],
                    "leg_id": leg["leg_id"],
                    "event_type": "DEPARTURE",
                    "event_time": ts(dep_time),
                    "ingested_at": ts(dep_time+ingestion_delay),
                    "facility_id": leg["origin_facility_id"],
                    "description": f"Departed from {leg['origin_facility_id']}",
                    "carrier_id": ship["carrier_id"],
                })
                if leg["leg_status"]=="COMPLETED" and pd.notna(leg["actual_arrival_at"]):
                    arr_time = datetime.strptime(leg["actual_arrival_at"],"%Y-%m-%dT%H:%M:%SZ")
                    ingestion_delay = timedelta(minutes=np.random.uniform(1,120))
                    evt_id += 1
                    events.append({
                        "event_id": f"EVT-{evt_id:06d}",
                        "shipment_id": ship["shipment_id"],
                        "leg_id": leg["leg_id"],
                        "event_type": "ARRIVAL",
                        "event_time": ts(arr_time),
                        "ingested_at": ts(arr_time+ingestion_delay),
                        "facility_id": leg["destination_facility_id"],
                        "description": f"Arrived at {leg['destination_facility_id']}",
                        "carrier_id": ship["carrier_id"],
                    })
        if ship["current_status"]=="DELIVERED" and pd.notna(ship["actual_delivery_at"]):
            del_time = datetime.strptime(ship["actual_delivery_at"],"%Y-%m-%dT%H:%M:%SZ")
            ingestion_delay = timedelta(minutes=np.random.uniform(1,60))
            evt_id += 1
            events.append({
                "event_id": f"EVT-{evt_id:06d}",
                "shipment_id": ship["shipment_id"],
                "leg_id": ship_legs.iloc[-1]["leg_id"] if len(ship_legs)>0 else None,
                "event_type": "DELIVERED",
                "event_time": ts(del_time),
                "ingested_at": ts(del_time+ingestion_delay),
                "facility_id": ship["destination_facility_id"],
                "description": "Shipment delivered",
                "carrier_id": ship["carrier_id"],
            })
    df = pd.DataFrame(events)
    df.to_csv(os.path.join(OUTPUT_DIR,"tracking_events.csv"),index=False)
    return df

def generate_eta_snapshots(shipments_df):
    snapshots = []
    snap_id = 0
    for _, ship in shipments_df.iterrows():
        created = datetime.strptime(ship["created_at"],"%Y-%m-%dT%H:%M:%SZ")
        planned_del = datetime.strptime(ship["planned_delivery_at"],"%Y-%m-%dT%H:%M:%SZ")
        n_snaps = np.random.randint(3,9)
        total_hours = (planned_del-created).total_seconds()/3600
        for j in range(n_snaps):
            snap_id += 1
            fraction = (j+1)/(n_snaps+1)
            snap_time = created + timedelta(hours=total_hours*fraction)
            true_remaining = max(0,(planned_del-snap_time).total_seconds()/3600)
            noise = np.random.normal(0,true_remaining*0.15)
            predicted_remaining = max(0,true_remaining+noise)
            predicted_delivery = snap_time + timedelta(hours=predicted_remaining)
            data_cutoff = snap_time - timedelta(minutes=np.random.uniform(0,30))
            snapshots.append({
                "eta_id": f"ETA-{snap_id:06d}",
                "shipment_id": ship["shipment_id"],
                "snapshot_time": ts(snap_time),
                "planned_delivery_at": ts(planned_del),
                "predicted_delivery_at": ts(predicted_delivery),
                "predicted_remaining_hours": round(predicted_remaining,2),
                "prediction_method": np.random.choice(["PLANNED","RULE_BASED","ML_MODEL"],p=[0.2,0.4,0.4]),
                "model_version": "v1.0",
                "data_cutoff_at": ts(data_cutoff),
                "max_ingested_at_used": ts(data_cutoff),
                "confidence_score": round(np.random.uniform(0.5,0.95),3),
            })
    df = pd.DataFrame(snapshots)
    df.to_csv(os.path.join(OUTPUT_DIR,"eta_snapshots.csv"),index=False)
    return df

def generate_facility_queues(facilities_df):
    queues = []
    q_id = 0
    for _, fac in facilities_df.iterrows():
        current = BASE_DATE
        while current < END_DATE:
            q_id += 1
            base_queue = np.random.poisson(fac["processing_capacity_per_hour"]*0.3)
            hour_factor = 1+0.5*np.sin(current.hour*np.pi/12)
            queue_len = max(0,int(base_queue*hour_factor+np.random.normal(0,5)))
            utilization = min(1.0,queue_len/max(fac["processing_capacity_per_hour"],1))
            avg_wait = round(queue_len/max(fac["processing_capacity_per_hour"],1)*60,1)
            disrupted = np.random.random() < 0.02
            queues.append({
                "queue_id": f"Q-{q_id:07d}",
                "facility_id": fac["facility_id"],
                "observed_at": ts(current),
                "ingested_at": ts(current+timedelta(minutes=np.random.uniform(1,15))),
                "queue_length": queue_len,
                "avg_waiting_time_minutes": avg_wait,
                "utilization": round(utilization,3),
                "is_disrupted": disrupted,
                "disruption_reason": "CAPACITY_OVERLOAD" if disrupted and utilization>0.8 else ("EQUIPMENT_FAILURE" if disrupted else None),
            })
            current += timedelta(hours=4)
    df = pd.DataFrame(queues)
    df.to_csv(os.path.join(OUTPUT_DIR,"facility_queues.csv"),index=False)
    return df

def generate_weather(facilities_df):
    forecasts = []
    observations = []
    fc_id = 0
    ob_id = 0
    severities = ["NONE","LOW","MODERATE","SEVERE","EXTREME"]
    for _, fac in facilities_df.iterrows():
        current = BASE_DATE
        while current < END_DATE:
            fc_id += 1
            severity = np.random.choice(severities, p=[0.5,0.25,0.15,0.07,0.03])
            issued = current - timedelta(hours=np.random.uniform(6,48))
            forecasts.append({
                "forecast_id": f"WF-{fc_id:07d}",
                "facility_id": fac["facility_id"],
                "valid_from": ts(current),
                "valid_to": ts(current+timedelta(hours=12)),
                "issued_at": ts(issued),
                "severity": severity,
                "precipitation_mm": round(np.random.exponential(2) if severity!="NONE" else 0,1),
                "wind_speed_kmh": round(np.random.uniform(0,30)+(30 if severity in ["SEVERE","EXTREME"] else 0),1),
                "temperature_c": round(np.random.normal(20,10),1),
                "weather_type": np.random.choice(["CLEAR","RAIN","SNOW","STORM","FOG"],p=[0.4,0.25,0.15,0.1,0.1]),
                "is_disruptive": severity in ["SEVERE","EXTREME"],
            })
            ob_id += 1
            obs_severity = severity if np.random.random()<0.7 else np.random.choice(severities,p=[0.5,0.25,0.15,0.07,0.03])
            observations.append({
                "observation_id": f"WO-{ob_id:07d}",
                "facility_id": fac["facility_id"],
                "observed_at": ts(current),
                "ingested_at": ts(current+timedelta(minutes=np.random.uniform(5,60))),
                "severity": obs_severity,
                "precipitation_mm": round(np.random.exponential(2) if obs_severity!="NONE" else 0,1),
                "wind_speed_kmh": round(np.random.uniform(0,30)+(30 if obs_severity in ["SEVERE","EXTREME"] else 0),1),
                "temperature_c": round(np.random.normal(20,10),1),
                "weather_type": np.random.choice(["CLEAR","RAIN","SNOW","STORM","FOG"]),
            })
            current += timedelta(hours=12)
    pd.DataFrame(forecasts).to_csv(os.path.join(OUTPUT_DIR,"weather_forecasts.csv"),index=False)
    pd.DataFrame(observations).to_csv(os.path.join(OUTPUT_DIR,"weather_observations.csv"),index=False)
    return pd.DataFrame(forecasts), pd.DataFrame(observations)

def generate_route_changes(shipments_df):
    changes = []
    rc_id = 0
    changed_ships = shipments_df.sample(frac=0.10, random_state=42)
    reasons = ["WEATHER_REROUTE","FACILITY_CLOSURE","CARRIER_SCHEDULE_CHANGE","CUSTOMS_DELAY","CAPACITY_ISSUE"]
    for _, ship in changed_ships.iterrows():
        rc_id += 1
        created = datetime.strptime(ship["created_at"],"%Y-%m-%dT%H:%M:%SZ")
        change_time = created + timedelta(hours=np.random.uniform(6,ship["planned_transit_hours"]*0.7))
        changes.append({
            "change_id": f"RC-{rc_id:04d}",
            "shipment_id": ship["shipment_id"],
            "change_type": np.random.choice(reasons),
            "changed_at": ts(change_time),
            "recorded_at": ts(change_time+timedelta(minutes=np.random.uniform(5,60))),
            "description": "Route change due to operational requirement",
            "impact_hours": round(np.random.uniform(1,24),1),
        })
    df = pd.DataFrame(changes)
    df.to_csv(os.path.join(OUTPUT_DIR,"route_changes.csv"),index=False)
    return df

def generate_disruptions(facilities_df):
    disruptions = []
    d_id = 0
    types = ["WEATHER","EQUIPMENT","LABOR","CAPACITY","SYSTEM"]
    for _, fac in facilities_df.iterrows():
        n_d = np.random.randint(0,5)
        for _ in range(n_d):
            d_id += 1
            start = BASE_DATE + timedelta(hours=np.random.uniform(0,(END_DATE-BASE_DATE).total_seconds()/3600))
            duration = timedelta(hours=np.random.uniform(2,48))
            disruptions.append({
                "disruption_id": f"DIS-{d_id:04d}",
                "facility_id": fac["facility_id"],
                "disruption_type": np.random.choice(types),
                "severity": np.random.choice(["LOW","MODERATE","HIGH","CRITICAL"]),
                "started_at": ts(start),
                "ended_at": ts(start+duration),
                "reported_at": ts(start+timedelta(minutes=np.random.uniform(10,120))),
                "description": "Operational disruption at facility",
                "impact_description": "Potential delays for shipments through this facility",
            })
    df = pd.DataFrame(disruptions)
    df.to_csv(os.path.join(OUTPUT_DIR,"disruptions.csv"),index=False)
    return df

def generate_ground_truth_anomalies(shipments_df, legs_df, events_df, eta_df):
    anomalies = []
    a_id = 0
    # A: Event ingestion-time confusion
    confused = events_df.sample(min(20,len(events_df)), random_state=42)
    for _, evt in confused.iterrows():
        a_id += 1
        anomalies.append({
            "anomaly_id": f"ANOM-{a_id:04d}","entity_type":"tracking_event",
            "entity_id": evt["event_id"],"shipment_id": evt["shipment_id"],
            "issue_type":"EVENT_INGESTION_CONFUSION","severity":"MEDIUM",
            "description":"Event ingestion time is suspicious relative to event time",
            "expected_behavior":"Ingestion time should be after event time","injected":True,
        })
    # B: Impossible route order
    broken = shipments_df.sample(min(15,len(shipments_df)), random_state=43)
    for _, ship in broken.iterrows():
        sl = legs_df[legs_df["shipment_id"]==ship["shipment_id"]].sort_values("leg_sequence")
        if len(sl)>=2:
            a_id += 1
            anomalies.append({
                "anomaly_id": f"ANOM-{a_id:04d}","entity_type":"shipment_leg",
                "entity_id": sl.iloc[0]["leg_id"],"shipment_id": ship["shipment_id"],
                "issue_type":"IMPOSSIBLE_ROUTE_ORDER","severity":"HIGH",
                "description":"Leg destination does not match next leg origin",
                "expected_behavior":"Consecutive legs should have matching facility transitions","injected":True,
            })
    # C: Future-data leakage
    leaky = eta_df.sample(min(15,len(eta_df)), random_state=44)
    for _, eta in leaky.iterrows():
        a_id += 1
        anomalies.append({
            "anomaly_id": f"ANOM-{a_id:04d}","entity_type":"eta_snapshot",
            "entity_id": eta["eta_id"],"shipment_id": eta["shipment_id"],
            "issue_type":"FUTURE_DATA_LEAKAGE","severity":"CRITICAL",
            "description":"ETA prediction may have used data not yet available at snapshot time",
            "expected_behavior":"All data used must have ingested_at <= snapshot_time","injected":True,
        })
    # D: Delivered but in-transit
    intransit = shipments_df[shipments_df["current_status"]=="IN_TRANSIT"]
    sample_it = intransit.sample(min(10,len(intransit)), random_state=45)
    for _, ship in sample_it.iterrows():
        a_id += 1
        anomalies.append({
            "anomaly_id": f"ANOM-{a_id:04d}","entity_type":"shipment",
            "entity_id": ship["shipment_id"],"shipment_id": ship["shipment_id"],
            "issue_type":"DELIVERED_BUT_IN_TRANSIT","severity":"HIGH",
            "description":"Shipment has a delivery event but status shows IN_TRANSIT",
            "expected_behavior":"Delivered shipments should have DELIVERED status","injected":True,
        })
    df = pd.DataFrame(anomalies)
    df.to_csv(os.path.join(OUTPUT_DIR,"ground_truth_anomalies.csv"),index=False)
    return df

def inject_anomalies(events_df, legs_df, eta_df, shipments_df, anomalies_df):
    """Inject actual data issues matching ground truth labels."""
    events_df = events_df.copy()
    legs_df = legs_df.copy()
    eta_df = eta_df.copy()
    
    # A: ingested_at BEFORE event_time
    for _, anom in anomalies_df[anomalies_df["issue_type"]=="EVENT_INGESTION_CONFUSION"].iterrows():
        idx = events_df[events_df["event_id"]==anom["entity_id"]].index
        if len(idx)>0:
            evt_time = datetime.strptime(events_df.loc[idx[0],"event_time"],"%Y-%m-%dT%H:%M:%SZ")
            events_df.loc[idx[0],"ingested_at"] = ts(evt_time - timedelta(hours=np.random.uniform(1,24)))
    
    # B: Break route continuity
    for _, anom in anomalies_df[anomalies_df["issue_type"]=="IMPOSSIBLE_ROUTE_ORDER"].iterrows():
        sl = legs_df[legs_df["shipment_id"]==anom["shipment_id"]].sort_values("leg_sequence")
        if len(sl)>=2:
            idx = sl.index[0]
            all_facs = legs_df["origin_facility_id"].unique()
            next_origin = legs_df.loc[sl.index[1],"origin_facility_id"]
            options = [f for f in all_facs if f != next_origin]
            if options:
                legs_df.loc[idx,"destination_facility_id"] = np.random.choice(options)
    
    # C: max_ingested_at_used > snapshot_time
    for _, anom in anomalies_df[anomalies_df["issue_type"]=="FUTURE_DATA_LEAKAGE"].iterrows():
        idx = eta_df[eta_df["eta_id"]==anom["entity_id"]].index
        if len(idx)>0:
            snap_time = datetime.strptime(eta_df.loc[idx[0],"snapshot_time"],"%Y-%m-%dT%H:%M:%SZ")
            eta_df.loc[idx[0],"max_ingested_at_used"] = ts(snap_time + timedelta(hours=np.random.uniform(1,12)))
            eta_df.loc[idx[0],"data_cutoff_at"] = ts(snap_time + timedelta(hours=np.random.uniform(0.5,6)))
    
    # D: Add delivery events to IN_TRANSIT shipments
    dit = anomalies_df[anomalies_df["issue_type"]=="DELIVERED_BUT_IN_TRANSIT"]
    max_evt = int(events_df["event_id"].str.extract(r'(\d+)')[0].astype(int).max())
    new_events = []
    for _, anom in dit.iterrows():
        ship = shipments_df[shipments_df["shipment_id"]==anom["shipment_id"]]
        if len(ship)>0:
            ship = ship.iloc[0]
            max_evt += 1
            del_time = datetime.strptime(ship["created_at"],"%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=ship["planned_transit_hours"])
            new_events.append({
                "event_id": f"EVT-{max_evt:06d}",
                "shipment_id": ship["shipment_id"],
                "leg_id": None,
                "event_type": "DELIVERED",
                "event_time": ts(del_time),
                "ingested_at": ts(del_time+timedelta(minutes=np.random.uniform(5,30))),
                "facility_id": ship["destination_facility_id"],
                "description": "Shipment delivered",
                "carrier_id": ship["carrier_id"],
            })
    if new_events:
        events_df = pd.concat([events_df, pd.DataFrame(new_events)], ignore_index=True)
    
    events_df.to_csv(os.path.join(OUTPUT_DIR,"tracking_events.csv"),index=False)
    legs_df.to_csv(os.path.join(OUTPUT_DIR,"shipment_legs.csv"),index=False)
    eta_df.to_csv(os.path.join(OUTPUT_DIR,"eta_snapshots.csv"),index=False)
    return events_df, legs_df, eta_df

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Logistics Dataset Generator")
    parser.add_argument("--mode", choices=["starter", "full"], default="starter", help="starter (500) or full (50,000)")
    parser.add_argument("--shipments", type=int, default=None, help="Explicit shipment count override")
    parser.add_argument("--seed", type=int, default=20261022, help="Random seed for reproducibility (default: 20261022)")
    parser.add_argument("--network", choices=["us", "india"], default="us", help="Facility geographic network")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory")
    parser.add_argument("--force", action="store_true", help="Force overwrite existing dataset in data/existing")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    if args.output_dir:
        target_dir = Path(args.output_dir)
        dirs_to_write = [target_dir]
    elif args.force:
        dirs_to_write = [project_root / "data" / "existing", project_root / "data" / "generated"]
    else:
        dirs_to_write = [project_root / "data" / "generated", project_root / "data" / "existing"]

    import shutil
    from src.data_generation.generator_pipeline import run_generation_pipeline
    primary_dir = dirs_to_write[0]
    run_generation_pipeline(
        mode=args.mode,
        seed=args.seed,
        shipment_override=args.shipments,
        network=args.network,
        output_dir=primary_dir
    )

    # Sync to secondary directories if multiple
    if len(dirs_to_write) > 1:
        for secondary in dirs_to_write[1:]:
            secondary.mkdir(parents=True, exist_ok=True)
            for file_path in primary_dir.glob("*.csv"):
                shutil.copy2(file_path, secondary / file_path.name)
            for file_path in primary_dir.glob("*.json"):
                shutil.copy2(file_path, secondary / file_path.name)

if __name__ == "__main__":
    main()
