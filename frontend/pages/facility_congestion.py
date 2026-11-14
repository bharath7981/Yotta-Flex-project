"""Page 7: Facility Congestion Monitoring
Monitors terminal queue depths, gate congestion levels, dwell waiting times, and bottleneck hubs.
"""

import streamlit as st
import plotly.express as px
import pandas as pd


def render_page(data):
    st.markdown('<div class="main-header">Facility Congestion Monitoring</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Cross-network terminal queue dynamics, gate dwell times, and bottleneck hub identification</div>', unsafe_allow_html=True)

    facilities = data.get("facilities")
    queues = data.get("facility_queues")
    if facilities is None or queues is None or queues.empty:
        st.warning("Facility queue monitoring data not available.")
        return

    q_df = queues.copy()
    q_df["observed_at_dt"] = pd.to_datetime(q_df["observed_at"], utc=True)
    
    # Normalize wait time and congestion level if derived
    if "wait_time_hours" not in q_df.columns:
        if "avg_waiting_time_minutes" in q_df.columns:
            q_df["wait_time_hours"] = q_df["avg_waiting_time_minutes"] / 60.0
        elif "expected_processing_delay_hours" in q_df.columns:
            q_df["wait_time_hours"] = q_df["expected_processing_delay_hours"]
        else:
            q_df["wait_time_hours"] = 0.0

    if "congestion_level" not in q_df.columns:
        if "utilization" in q_df.columns:
            q_df["congestion_level"] = q_df["utilization"].apply(
                lambda u: "CRITICAL" if u >= 0.90 else ("HIGH" if u >= 0.75 else ("MODERATE" if u >= 0.50 else "NORMAL"))
            )
        else:
            q_df["congestion_level"] = "NORMAL"

    merged = q_df.merge(facilities, on="facility_id", how="left")

    # Aggregate Metrics
    avg_queue = round(float(q_df["queue_length"].mean()), 1)
    avg_wait = round(float(q_df["wait_time_hours"].mean()), 2)
    max_queue = int(q_df["queue_length"].max())
    congested_count = len(q_df[q_df["congestion_level"].astype(str).str.upper().isin(["HIGH", "CRITICAL"])])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Network Avg Queue Depth", f"{avg_queue} pkgs")
    col2.metric("Network Avg Dwell / Wait", f"{avg_wait} hrs")
    col3.metric("Peak Queue Observed", f"{max_queue} pkgs")
    col4.metric("Congestion Spikes Detected", f"{congested_count}")

    st.markdown("---")

    # Facility Ranking by Congestion
    st.subheader("Top Congested Facilities by Average Wait Time")
    fac_summary = merged.groupby(["facility_id", "facility_name", "facility_type", "city"]).agg(
        avg_wait_hours=("wait_time_hours", "mean"),
        avg_queue_len=("queue_length", "mean"),
        max_queue_len=("queue_length", "max"),
        observations=("queue_id", "count")
    ).reset_index().sort_values("avg_wait_hours", ascending=False)

    fig_bar = px.bar(
        fac_summary.head(15),
        x="facility_name",
        y="avg_wait_hours",
        color="avg_wait_hours",
        color_continuous_scale="Reds",
        title="Average Wait Time (Hours) by Facility Hub",
        labels={"facility_name": "Facility Name", "avg_wait_hours": "Avg Wait Time (Hours)"}
    )
    fig_bar.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("---")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Congestion Severity Distribution")
        fig_pie = px.pie(
            q_df,
            names="congestion_level",
            title="Observations by Congestion Level",
            color="congestion_level",
            color_discrete_map={"NORMAL": "lightblue", "MODERATE": "orange", "HIGH": "red", "CRITICAL": "darkred"}
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with c2:
        st.subheader("Queue Depth vs Dwell Wait Time")
        fig_scatter = px.scatter(
            merged.sample(min(500, len(merged))),
            x="queue_length",
            y="wait_time_hours",
            color="congestion_level",
            hover_data=["facility_name", "city"],
            title="Queue Length vs Resulting Dwell Time",
            labels={"queue_length": "Queue Depth (Units)", "wait_time_hours": "Wait Time (Hours)"}
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    st.markdown("---")
    st.subheader("Facility Congestion Leaderboard")
    st.dataframe(
        fac_summary.style.format({
            "avg_wait_hours": "{:.2f}",
            "avg_queue_len": "{:.1f}",
            "max_queue_len": "{:d}",
            "observations": "{:d}"
        }),
        use_container_width=True
    )
