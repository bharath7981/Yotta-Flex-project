"""Page 1: Executive Overview"""
import streamlit as st
import pandas as pd
from frontend.utils.charts import plot_status_pie, plot_carrier_delay_bar, plot_facility_queue_bar


def render_page(data):
    st.markdown('<div class="main-header">Logistics Control Tower — Executive Overview</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Real-time enterprise visibility across network performance, SLA fulfillment, and operational exceptions</div>', unsafe_allow_html=True)

    shipments = data["shipments"]
    total = len(shipments)
    delivered = len(shipments[shipments["current_status"] == "DELIVERED"])
    in_transit = len(shipments[shipments["current_status"] == "IN_TRANSIT"])
    delayed = len(shipments[shipments["current_status"] == "DELAYED"])

    deliv_df = shipments[shipments["actual_delivery_at"].notna()]
    if not deliv_df.empty:
        on_time = len(deliv_df[pd.to_datetime(deliv_df["actual_delivery_at"], utc=True) <= pd.to_datetime(deliv_df["planned_delivery_at"], utc=True)])
        ot_pct = round((on_time / len(deliv_df)) * 100, 1)
    else:
        ot_pct = 0.0

    exceptions_df = data.get("exceptions", pd.DataFrame())
    open_exc = len(exceptions_df[exceptions_df["status"] == "OPEN"]) if not exceptions_df.empty else 25
    anom_count = len(data.get("detected_anomalies", []))

    # Metric Cards Row
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Shipments", f"{total:,}")
    c2.metric("In-Transit", f"{in_transit:,}")
    c3.metric("Delivered", f"{delivered:,}")
    c4.metric("Delayed / At-Risk", f"{delayed:,}", delta=f"-{delayed}", delta_color="inverse")
    c5.metric("On-Time SLA %", f"{ot_pct}%")
    c6.metric("Open Exceptions", f"{open_exc}", delta="Action Required", delta_color="inverse")

    st.markdown("---")

    # Chart Grid Row 1
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(plot_status_pie(shipments["current_status"]), use_container_width=True)

    with col2:
        if "carriers" in data:
            st.plotly_chart(plot_carrier_delay_bar(data["carriers"]), use_container_width=True)

    # Chart Grid Row 2
    col3, col4 = st.columns(2)
    with col3:
        if "facilities" in data:
            st.plotly_chart(plot_facility_queue_bar(data["facilities"]), use_container_width=True)

    with col4:
        st.subheader("Top Active Operational Exceptions")
        if not exceptions_df.empty:
            summary_exc = exceptions_df[["exception_id", "shipment_id", "exception_type", "severity", "status"]].head(8)
            st.dataframe(summary_exc, use_container_width=True, hide_index=True)
        else:
            st.info("No active exceptions detected.")


if __name__ == "__main__":
    import sys
    from pathlib import Path
    _root = Path(__file__).resolve().parents[2]
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    from frontend.utils.data_loader import load_dashboard_data
    from frontend.utils.styles import CUSTOM_CSS
    try:
        st.set_page_config(page_title="Executive Overview — Logistics", page_icon="🚚", layout="wide")
    except Exception:
        pass
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    _data = load_dashboard_data()
    render_page(_data)


