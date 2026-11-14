"""Plotly Chart Generators for Logistics Operations"""
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import List, Dict, Any


def plot_status_pie(status_series: pd.Series) -> go.Figure:
    counts = status_series.value_counts().reset_index()
    counts.columns = ["Status", "Count"]
    fig = px.pie(
        counts,
        names="Status",
        values="Count",
        title="Shipment Lifecycle Status Distribution",
        color="Status",
        color_discrete_map={
            "DELIVERED": "#2ecc71",
            "IN_TRANSIT": "#3498db",
            "DELAYED": "#e74c3c",
            "AT_FACILITY": "#f39c12",
            "CANCELLED": "#95a5a6"
        },
        hole=0.4
    )
    fig.update_layout(margin=dict(t=40, b=10, l=10, r=10))
    return fig


def plot_carrier_delay_bar(carrier_df: pd.DataFrame) -> go.Figure:
    fig = px.bar(
        carrier_df,
        x="carrier_name",
        y="avg_delay_hours",
        color="on_time_rate",
        color_continuous_scale="Viridis",
        title="Carrier Average Delay (Hours) & On-Time Rate",
        labels={"avg_delay_hours": "Avg Delay (h)", "carrier_name": "Carrier", "on_time_rate": "On-Time Rate"}
    )
    fig.update_layout(margin=dict(t=40, b=20, l=10, r=10))
    return fig


def plot_facility_queue_bar(fac_df: pd.DataFrame) -> go.Figure:
    top_q = fac_df.sort_values("processing_capacity_per_hour", ascending=False)
    fig = px.bar(
        top_q,
        x="facility_name",
        y="processing_capacity_per_hour",
        title="Facility Processing Capacity (Units / Hour)",
        color="facility_type"
    )
    fig.update_layout(margin=dict(t=40, b=40, l=10, r=10), xaxis_tickangle=-45)
    return fig


def plot_event_ingestion_timeline(events_df: pd.DataFrame) -> go.Figure:
    """Timeline comparing event occurrence time vs system ingestion time."""
    df = events_df.copy()
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["ingested_at"] = pd.to_datetime(df["ingested_at"])
    df["delay_minutes"] = (df["ingested_at"] - df["event_time"]).dt.total_seconds() / 60.0

    fig = go.Figure()

    # Normal events
    normal = df[df["delay_minutes"] >= 0]
    fig.add_trace(go.Scatter(
        x=normal["event_time"],
        y=normal["ingested_at"],
        mode="markers",
        name="Standard Ingestion",
        marker=dict(size=10, color="#1f4e79"),
        text=[f"Event: {e}<br>Delay: {d:.1f}m" for e, d in zip(normal["event_id"], normal["delay_minutes"])]
    ))

    # Anomaly events (ingested before occurred)
    confused = df[df["delay_minutes"] < 0]
    if not confused.empty:
        fig.add_trace(go.Scatter(
            x=confused["event_time"],
            y=confused["ingested_at"],
            mode="markers",
            name="Anomaly: Ingestion Confusion",
            marker=dict(size=14, color="#e74c3c", symbol="diamond"),
            text=[f"ANOMALY {e}<br>Ingested {abs(d):.1f}m BEFORE event" for e, d in zip(confused["event_id"], confused["delay_minutes"])]
        ))

    # Reference diagonal line (event_time == ingested_at)
    min_t = min(df["event_time"].min(), df["ingested_at"].min())
    max_t = max(df["event_time"].max(), df["ingested_at"].max())
    fig.add_trace(go.Scatter(
        x=[min_t, max_t],
        y=[min_t, max_t],
        mode="lines",
        name="Real-time Boundary (Event = Ingested)",
        line=dict(color="gray", dash="dash")
    ))

    fig.update_layout(
        title="Event Occurrence Time vs. System Ingestion Time",
        xaxis_title="Actual Event Time",
        yaxis_title="System Ingested Time",
        margin=dict(t=40, b=20, l=20, r=20)
    )
    return fig


def plot_eta_history(eta_df: pd.DataFrame, planned_delivery_time: str, actual_delivery_time: str = None) -> go.Figure:
    df = eta_df.copy()
    df["snapshot_time"] = pd.to_datetime(df["snapshot_time"])
    df["predicted_delivery_at"] = pd.to_datetime(df["predicted_delivery_at"])

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["snapshot_time"],
        y=df["predicted_delivery_at"],
        mode="lines+markers",
        name="Predicted Delivery Time",
        line=dict(color="#2980b9", width=3),
        marker=dict(size=8)
    ))

    min_x = df["snapshot_time"].min()
    max_x = df["snapshot_time"].max()

    if planned_delivery_time and not pd.isna(planned_delivery_time):
        plan_dt = pd.to_datetime(planned_delivery_time)
        fig.add_trace(go.Scatter(
            x=[min_x, max_x],
            y=[plan_dt, plan_dt],
            mode="lines",
            line=dict(color="#f39c12", width=2, dash="dot"),
            name=f"Planned SLA ({plan_dt.strftime('%b %d %H:%M')})"
        ))

    if actual_delivery_time and not pd.isna(actual_delivery_time):
        act_dt = pd.to_datetime(actual_delivery_time)
        fig.add_trace(go.Scatter(
            x=[min_x, max_x],
            y=[act_dt, act_dt],
            mode="lines",
            line=dict(color="#27ae60", width=2, dash="solid"),
            name=f"Actual Delivery ({act_dt.strftime('%b %d %H:%M')})"
        ))

    fig.update_layout(
        title="Point-in-Time ETA Progression Across Lifecycle",
        xaxis_title="Prediction Snapshot Time",
        yaxis_title="Estimated Delivery Timestamp",
        margin=dict(t=40, b=20, l=20, r=20)
    )
    return fig

