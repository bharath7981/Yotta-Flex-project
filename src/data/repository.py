"""Data Repository Module
Provides DuckDB storage and analytical querying capabilities for the Logistics Platform.
Supports all 16 Relational Core and Supporting Entities:
1. carriers
2. facilities
3. routes
4. service_levels
5. delay_reasons
6. carrier_calendars
7. facility_calendars
8. shipments
9. shipment_legs
10. shipment_status_history
11. route_change_history
12. shipment_delay_reasons
13. tracking_events
14. weather_events (and weather_forecasts)
15. facility_queues
16. eta_estimates (and eta_snapshots)
"""

import os
from typing import Dict, Any, List, Optional
import duckdb
import pandas as pd
from src.data.loader import load_all_data
from src.data.normalizer import normalize_all_data


def get_db_path() -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    analytics_dir = os.path.join(base_dir, "data", "analytics")
    os.makedirs(analytics_dir, exist_ok=True)
    return os.path.join(analytics_dir, "logistics.duckdb")


class LogisticsRepository:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_db_path()

    def get_connection(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(self.db_path)

    def initialize_database(self, normalized_data: Optional[Dict[str, pd.DataFrame]] = None):
        """Load normalized DataFrames into DuckDB tables."""
        if normalized_data is None:
            raw = load_all_data()
            normalized_data = normalize_all_data(raw)

        conn = self.get_connection()
        try:
            for table_name, df in normalized_data.items():
                conn.register(f"temp_{table_name}", df)
                conn.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM temp_{table_name}")
                conn.unregister(f"temp_{table_name}")
            print(f"DuckDB initialized successfully with {len(normalized_data)} tables at {self.db_path}")
        finally:
            conn.close()

    def query_df(self, query: str, params: Optional[List[Any]] = None) -> pd.DataFrame:
        """Execute analytical SQL query and return pandas DataFrame."""
        conn = self.get_connection()
        try:
            if params:
                return conn.execute(query, params).df()
            return conn.execute(query).df()
        finally:
            conn.close()

    def get_shipment(self, shipment_id: str) -> Optional[Dict[str, Any]]:
        df = self.query_df("SELECT * FROM shipments WHERE shipment_id = ?", [shipment_id])
        if len(df) == 0:
            return None
        return df.iloc[0].to_dict()

    def get_shipment_legs(self, shipment_id: str) -> pd.DataFrame:
        return self.query_df("SELECT * FROM shipment_legs WHERE shipment_id = ? ORDER BY leg_sequence", [shipment_id])

    def get_tracking_events(self, shipment_id: str) -> pd.DataFrame:
        return self.query_df("SELECT * FROM tracking_events WHERE shipment_id = ? ORDER BY event_time", [shipment_id])

    def get_eta_history(self, shipment_id: str) -> pd.DataFrame:
        # Check if eta_estimates table exists, fallback to eta_snapshots
        table = "eta_estimates" if "eta_estimates" in self.get_tables() else "eta_snapshots"
        order_col = "prediction_timestamp" if table == "eta_estimates" else "snapshot_time"
        return self.query_df(f"SELECT * FROM {table} WHERE shipment_id = ? ORDER BY {order_col}", [shipment_id])

    def get_shipment_delay_reasons(self, shipment_id: str) -> pd.DataFrame:
        if "shipment_delay_reasons" in self.get_tables() and "delay_reasons" in self.get_tables():
            return self.query_df(
                """
                SELECT sdr.*, dr.reason_code, dr.reason_category, dr.description as reason_description
                FROM shipment_delay_reasons sdr
                JOIN delay_reasons dr ON sdr.reason_id = dr.reason_id
                WHERE sdr.shipment_id = ?
                """,
                [shipment_id]
            )
        return pd.DataFrame()

    def get_carriers(self) -> pd.DataFrame:
        return self.query_df("SELECT * FROM carriers ORDER BY carrier_name")

    def get_facilities(self) -> pd.DataFrame:
        return self.query_df("SELECT * FROM facilities ORDER BY facility_name")

    def get_facility_queues(self, facility_id: str) -> pd.DataFrame:
        return self.query_df("SELECT * FROM facility_queues WHERE facility_id = ? ORDER BY observed_at DESC", [facility_id])

    def get_weather_events(self, facility_id: Optional[str] = None) -> pd.DataFrame:
        table = "weather_events" if "weather_events" in self.get_tables() else "weather_forecasts"
        time_col = "started_at" if table == "weather_events" else "valid_from"
        if facility_id:
            return self.query_df(f"SELECT * FROM {table} WHERE facility_id = ? ORDER BY {time_col} DESC", [facility_id])
        return self.query_df(f"SELECT * FROM {table} ORDER BY {time_col} DESC")

    def get_routes(self) -> pd.DataFrame:
        if "routes" in self.get_tables():
            return self.query_df("SELECT * FROM routes")
        return pd.DataFrame()

    def get_tables(self) -> List[str]:
        """List all tables in database."""
        df = self.query_df("SHOW TABLES")
        return df.iloc[:, 0].tolist() if not df.empty else []


if __name__ == "__main__":
    repo = LogisticsRepository()
    repo.initialize_database()
    shipments = repo.query_df("SELECT count(*) as count FROM shipments")
    print(f"Total shipments in DuckDB: {shipments.iloc[0]['count']}")
