"""Page 6: Facility Operations & Congestion Management"""
import streamlit as st
import plotly.express as px
import pandas as pd


def render_page(data):
    st.markdown('<div class="main-header">Facility Operations & Hub Congestion</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Terminal queue dynamics, dwell waiting times, and active capacity disruptions</div>', unsafe_allow_html=True)

    facilities = data["facilities"]
    queues = data["facility_queues"].copy()
    queues["observed_at"] = pd.to_datetime(queues["observed_at"])

    # Facility Selector
    fac_names = facilities["facility_name"].tolist()
    fac_ids = facilities["facility_id"].tolist()
    fac_dict = dict(zip(fac_names, fac_ids))

    selected_name = st.selectbox("Select Logistics Facility / Hub", fac_names)
    selected_id = fac_dict[selected_name]

    fac_info = facilities[facilities["facility_id"] == selected_id].iloc[0]
    fac_queues = queues[queues["facility_id"] == selected_id].sort_values("observed_at")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Facility Type", fac_info["facility_type"])
    col2.metric("Location", f"{fac_info['city']}, {fac_info['country']}")
    col3.metric("Hourly Capacity", f"{fac_info['processing_capacity_per_hour']} units")
    col4.metric("Avg Process Time", f"{fac_info['avg_processing_time_hours']} hours")

    st.markdown("---")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Queue Depth Over Time")
        fig_q = px.line(
            fac_queues.tail(100),
            x="observed_at",
            y="queue_length",
            title=f"Queue Length (Recent Observations) — {selected_name}",
            labels={"queue_length": "Queued Shipments", "observed_at": "Timestamp"}
        )
        st.plotly_chart(fig_q, use_container_width=True)

    with c2:
        st.subheader("Capacity Utilization Rate")
        fig_u = px.area(
            fac_queues.tail(100),
            x="observed_at",
            y="utilization",
            title=f"Utilization Rate — {selected_name}",
            labels={"utilization": "Capacity Utilization (0.0 - 1.0)", "observed_at": "Timestamp"}
        )
        fig_u.add_hline(y=0.85, line_dash="dash", line_color="red", annotation_text="Congestion Threshold")
        st.plotly_chart(fig_u, use_container_width=True)

    st.markdown("---")
    st.subheader("Active Operational Disruptions")
    disruptions = data.get("disruptions", pd.DataFrame())
    if not disruptions.empty:
        fac_dis = disruptions[disruptions["facility_id"] == selected_id]
        if not fac_dis.empty:
            st.dataframe(fac_dis[["disruption_id", "disruption_type", "severity", "started_at", "ended_at", "description"]], use_container_width=True, hide_index=True)
        else:
            st.success("No active operational disruptions reported at this facility.")
    else:
        st.info("No disruptions data available.")


if __name__ == "__main__":
    import sys
    from pathlib import Path
    _root = Path(__file__).resolve().parents[2]
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    from frontend.utils.data_loader import load_dashboard_data
    from frontend.utils.styles import CUSTOM_CSS
    try:
        st.set_page_config(page_title="Facility Operations — Logistics", page_icon="🚚", layout="wide")
    except Exception:
        pass
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    _data = load_dashboard_data()
    render_page(_data)


