"""Weather Disruption API Routes"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
import pandas as pd
from app.dependencies import get_cached_data
from src.api.schemas.weather import WeatherEventItem, WeatherListResponse

router = APIRouter(tags=["Weather"])


@router.get("/weather-events", response_model=WeatherListResponse)
@router.get("/weather", response_model=WeatherListResponse)
def list_weather_events(
    severity: Optional[str] = None,
    weather_type: Optional[str] = None,
    limit: int = 100,
    data=Depends(get_cached_data)
):
    n_limit = limit if isinstance(limit, int) else 100
    df = data.get("weather_events")
    if df is None or df.empty:
        df = data.get("weather_forecasts")
    if df is None or df.empty:
        return WeatherListResponse(total=0, weather_events=[])

    subset = df.copy()
    if severity:
        subset = subset[subset["severity"].astype(str).str.upper() == severity.upper()]
    if weather_type:
        subset = subset[subset["weather_type"].astype(str).str.upper() == weather_type.upper()]

    subset = subset.head(n_limit)
    items = []
    for _, row in subset.iterrows():
        w_id = str(row.get("weather_id", row.get("event_id", row.get("forecast_id", ""))))
        items.append(WeatherEventItem(
            weather_id=w_id,
            facility_id=str(row["facility_id"]) if pd.notna(row.get("facility_id")) else None,
            route_id=str(row["route_id"]) if pd.notna(row.get("route_id")) else None,
            weather_type=str(row.get("weather_type", "CLEAR")),
            severity=str(row.get("severity", "LOW")),
            started_at=str(row.get("started_at", row.get("valid_from", ""))),
            ended_at=str(row.get("ended_at", row.get("valid_to", ""))),
            impact_delay_hours=float(row.get("impact_delay_hours", 0.0)),
            visibility_km=float(row["visibility_km"]) if pd.notna(row.get("visibility_km")) else None,
            wind_speed_kmh=float(row["wind_speed_kmh"]) if pd.notna(row.get("wind_speed_kmh")) else None,
            precipitation_mm=float(row["precipitation_mm"]) if pd.notna(row.get("precipitation_mm")) else None,
        ))

    return WeatherListResponse(
        total=len(items),
        weather_events=items
    )
