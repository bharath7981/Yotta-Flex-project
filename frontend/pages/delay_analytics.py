"""Page 4: Delay Analytics & Root Causes"""
import streamlit as st
import plotly.express as px
import pandas as pd


def render_page(data):
    st.markdown('<div class="main-header">Delay Intelligence & Network Bottlenecks</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Aggregated delay patterns, operational root causes, and transport mode analytics</div>', unsafe_allow_html=True)

    shipments = data["shipments"]
    deliv = shipments[shipments["actual_delivery_at"].notna()].copy()
    deliv["delay_hours"] = (pd.to_datetime(deliv["actual_delivery_at"], utc=True) - pd.to_datetime(deliv["planned_delivery_at"], utc=True)).dt.total_seconds() / 3600.0

    st.info(
        "**Target Definition Clarity**: Delay Intelligence separates **Schedule Delay** "
        "(`actual_delivery_at > planned_delivery_at`, primary predictive ML target) from **Contractual SLA Breach** "
        "(`actual_delivery_at > promised_delivery_at + grace_period`, commercial penalty metric)."
    )

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Delay Hours Distribution (Delivered Shipments)")
        fig_hist = px.histogram(
            deliv,
            x="delay_hours",
            nbins=30,
            color_discrete_sequence=["#1f4e79"],
            labels={"delay_hours": "Delivery Delay vs Planned Schedule (Hours)"}
        )
        fig_hist.add_vline(x=0, line_dash="dash", line_color="green", annotation_text="Planned Delivery Boundary")
        st.plotly_chart(fig_hist, use_container_width=True)

    with col2:
        st.subheader("Operational Delay Root Causes")
        exps = data.get("delay_explanations", pd.DataFrame())
        if not exps.empty:
            cause_counts = exps["reason_code"].value_counts().reset_index()
            cause_counts.columns = ["Root Cause", "Frequency"]
            fig_causes = px.bar(
                cause_counts,
                x="Frequency",
                y="Root Cause",
                orientation="h",
                color="Frequency",
                color_continuous_scale="Reds"
            )
            st.plotly_chart(fig_causes, use_container_width=True)
        else:
            st.info("No delay explanations available.")

    st.markdown("---")

    col3, col4 = st.columns(2)
    with col3:
        st.subheader("Delay by Service Level")
        service_delays = deliv.groupby("service_level")["delay_hours"].mean().reset_index()
        fig_serv = px.bar(
            service_delays,
            x="service_level",
            y="delay_hours",
            color="service_level",
            labels={"delay_hours": "Avg Delay (h)", "service_level": "Service Level"}
        )
        st.plotly_chart(fig_serv, use_container_width=True)

    with col4:
        st.subheader("Transport Mode Performance")
        legs = data.get("shipment_legs", pd.DataFrame())
        if not legs.empty:
            mode_counts = legs["transport_mode"].value_counts().reset_index()
            mode_counts.columns = ["Transport Mode", "Segment Volume"]
            fig_mode = px.pie(mode_counts, names="Transport Mode", values="Segment Volume", hole=0.35)
            st.plotly_chart(fig_mode, use_container_width=True)

