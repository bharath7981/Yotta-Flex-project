"""Page 6: Weather Disruption Monitoring
Monitors meteorological disruptions across the facility network and transit corridors.
"""

import streamlit as st
import plotly.express as px
import pandas as pd


def render_page(data):
    st.markdown('<div class="main-header">Weather Disruption Monitoring</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Real-time corridor and terminal weather hazard tracking, severity assessment, and delay impact analytics</div>', unsafe_allow_html=True)

    weather_df = data.get("weather_events")
    if weather_df is None or weather_df.empty:
        weather_df = data.get("weather_forecasts")
    if weather_df is None or weather_df.empty:
        st.warning("No weather disruption events found in data lake.")
        return

    df = weather_df.copy()
    time_col = "started_at" if "started_at" in df.columns else "valid_from"
    df["started_at_dt"] = pd.to_datetime(df[time_col], utc=True)

    # Top KPI Metrics
    total_events = len(df)
    severe_events = len(df[df["severity"].astype(str).str.upper().isin(["HIGH", "CRITICAL", "SEVERE"])])
    total_impact_hours = round(float(df["impact_delay_hours"].sum()), 1) if "impact_delay_hours" in df.columns else 0.0
    impacted_facilities = df["facility_id"].nunique() if "facility_id" in df.columns else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Weather Events", f"{total_events:,}")
    col2.metric("Severe / Critical Hazards", f"{severe_events:,}")
    col3.metric("Facilities Impacted", f"{impacted_facilities}")
    col4.metric("Est. Delay Impact", f"{total_impact_hours:,} hrs")

    st.markdown("---")

    # Severity and Type Breakdown
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Disruptions by Weather Type")
        fig_type = px.pie(
            df,
            names="weather_type",
            values="impact_delay_hours" if "impact_delay_hours" in df.columns else None,
            title="Total Delay Impact by Hazard Type",
            color_discrete_sequence=px.colors.qualitative.Prism
        )
        st.plotly_chart(fig_type, use_container_width=True)

    with c2:
        st.subheader("Severity Distribution")
        fig_sev = px.histogram(
            df,
            x="severity",
            color="severity",
            title="Event Frequency by Severity Level",
            color_discrete_map={"LOW": "green", "MODERATE": "orange", "HIGH": "red", "CRITICAL": "darkred"}
        )
        st.plotly_chart(fig_sev, use_container_width=True)

    st.markdown("---")
    st.subheader("Temporal Event Timeline & Impact")
    fig_scatter = px.scatter(
        df,
        x="started_at_dt",
        y="impact_delay_hours" if "impact_delay_hours" in df.columns else "severity",
        color="severity",
        size="impact_delay_hours" if "impact_delay_hours" in df.columns else None,
        hover_data=["weather_type", "facility_id", "route_id"] if "facility_id" in df.columns else ["weather_type"],
        title="Weather Hazard Timeline vs Imparted Delay Hours",
        labels={"started_at_dt": "Observation Start Time", "impact_delay_hours": "Attributed Delay (Hours)"}
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

    st.markdown("---")
    st.subheader("Detailed Weather Events Ledger")
    display_cols = [c for c in ["weather_id", "weather_type", "severity", "facility_id", "route_id", "started_at", "ended_at", "impact_delay_hours", "visibility_km", "wind_speed_kmh"] if c in df.columns]
    sorted_df = df.sort_values("started_at_dt", ascending=False)
    st.dataframe(sorted_df[display_cols], use_container_width=True)
