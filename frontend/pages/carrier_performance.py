"""Page 8: Carrier Performance Intelligence
Evaluates carrier SLA compliance, on-time delivery rates, transit variability, and operational reliability.
"""

import streamlit as st
import plotly.express as px
import pandas as pd


def render_page(data):
    st.markdown('<div class="main-header">Carrier Performance Intelligence</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Carrier scorecard, on-time reliability ratings, SLA breach rates, and transit mode benchmarks</div>', unsafe_allow_html=True)

    carriers = data.get("carriers")
    shipments = data.get("shipments")
    if carriers is None or carriers.empty or shipments is None:
        st.warning("Carrier performance data not available.")
        return

    ships = shipments.copy()
    car_df = carriers.copy()

    # Aggregate actual shipment performance by carrier
    deliv = ships[ships["actual_delivery_at"].notna()].copy()
    if deliv.empty:
        deliv = ships.copy()

    delay_col = "is_delayed" if "is_delayed" in deliv.columns else "delay_hours"
    deliv["delay_flag"] = deliv[delay_col].astype(bool) if delay_col == "is_delayed" else deliv[delay_col] > 0
    deliv["ontime_flag"] = ~deliv["delay_flag"]

    perf = deliv.groupby("carrier_id").agg(
        volume=("shipment_id", "count"),
        actual_ontime_rate=("ontime_flag", "mean"),
        actual_avg_delay=("delay_hours", "mean"),
        sla_breach_rate=("is_sla_breached", lambda x: (x == 1).mean() if "is_sla_breached" in deliv.columns else 0.0)
    ).reset_index()

    scorecard = car_df.merge(perf, on="carrier_id", how="left").fillna({
        "volume": 0,
        "actual_ontime_rate": 0.85,
        "actual_avg_delay": 0.0,
        "sla_breach_rate": 0.0
    })

    # High-level KPIs
    col1, col2, col3, col4 = st.columns(4)
    best_carrier = scorecard.sort_values("actual_ontime_rate", ascending=False).iloc[0]["carrier_name"]
    avg_net_ontime = round(float(scorecard["actual_ontime_rate"].mean() * 100), 1)
    avg_net_delay = round(float(scorecard["actual_avg_delay"].mean()), 1)
    active_carriers = len(scorecard)

    col1.metric("Active Carriers", f"{active_carriers}")
    col2.metric("Network On-Time Rate", f"{avg_net_ontime}%")
    col3.metric("Network Avg Delay", f"{avg_net_delay} hrs")
    col4.metric("Top Performing Carrier", best_carrier)

    st.markdown("---")

    # Carrier Comparison Charts
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("On-Time Delivery Rate by Carrier")
        fig_ontime = px.bar(
            scorecard.sort_values("actual_ontime_rate", ascending=True),
            x="actual_ontime_rate",
            y="carrier_name",
            orientation="h",
            color="actual_ontime_rate",
            color_continuous_scale="Greens",
            title="Actual On-Time Rate (%)",
            labels={"actual_ontime_rate": "On-Time Rate", "carrier_name": "Carrier"}
        )
        st.plotly_chart(fig_ontime, use_container_width=True)

    with c2:
        st.subheader("Carrier Risk Quadrant: Reliability vs Delay")
        fig_quad = px.scatter(
            scorecard,
            x="actual_ontime_rate",
            y="actual_avg_delay",
            size="volume",
            color="primary_mode",
            hover_name="carrier_name",
            title="Carrier Reliability Profile (Size = Volume Handled)",
            labels={"actual_ontime_rate": "On-Time Rate", "actual_avg_delay": "Average Delay (Hours)"}
        )
        st.plotly_chart(fig_quad, use_container_width=True)

    st.markdown("---")
    st.subheader("Comprehensive Carrier Scorecard")
    display_df = scorecard[[
        "carrier_id", "carrier_name", "primary_mode", "volume",
        "actual_ontime_rate", "actual_avg_delay", "sla_breach_rate",
        "reliability_score"
    ]].copy()

    st.dataframe(
        display_df.style.format({
            "volume": "{:d}",
            "actual_ontime_rate": "{:.1%}",
            "actual_avg_delay": "{:.1f} hrs",
            "sla_breach_rate": "{:.1%}",
            "reliability_score": "{:.2f}"
        }),
        use_container_width=True
    )


if __name__ == "__main__":
    import sys
    from pathlib import Path
    _root = Path(__file__).resolve().parents[2]
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    from frontend.utils.data_loader import load_dashboard_data
    from frontend.utils.styles import CUSTOM_CSS
    try:
        st.set_page_config(page_title="Carrier Performance — Logistics", page_icon="🚚", layout="wide")
    except Exception:
        pass
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    _data = load_dashboard_data()
    render_page(_data)


