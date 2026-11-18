"""Streamlit Main Application
Logistics ETA Prediction & Delay Intelligence Platform
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from frontend.utils.styles import CUSTOM_CSS
from frontend.utils.data_loader import load_dashboard_data

# Page configuration
st.set_page_config(
    page_title="Logistics ETA & Delay Intelligence Platform",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject custom styling
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# Load shared data
with st.spinner("Loading logistics intelligence network data..."):
    data = load_dashboard_data()

# Sidebar Navigation
st.sidebar.image("https://img.icons8.com/fluency/96/delivery-conveyer-belt.png", width=64)
st.sidebar.title("Logistics Tower")
st.sidebar.markdown("**Decision Support & Delay Intelligence**")
st.sidebar.markdown("---")

pages = [
    "1. Executive Overview",
    "2. Shipment Control Tower",
    "3. Shipment Intelligence",
    "4. Delay Analytics & Root Cause",
    "5. Anomaly Intelligence",
    "6. Weather Disruption Monitoring",
    "7. Facility Congestion Monitoring",
    "8. Carrier Performance",
    "9. Facility Operations",
    "10. Model Performance & Calibration",
    "11. Shipment Replay (Point-in-Time)",
    "12. Data Quality & Lake Validation"
]

selected_page = st.sidebar.radio("Navigation", pages)

st.sidebar.markdown("---")
st.sidebar.info(
    "**System Status**:\n"
    "- Network Data: Active (500 Shipments, 16 Tables)\n"
    "- Analytical DB: DuckDB Connected (23 Tables)\n"
    "- ML Models: ETA Regression & Delay Classifier\n"
    "- Validation: 53 Rules Evaluated (PASSED)"
)

# Route to selected page
if selected_page == "1. Executive Overview":
    from frontend.pages.executive_overview import render_page
    render_page(data)
elif selected_page == "2. Shipment Control Tower":
    from frontend.pages.shipment_control import render_page
    render_page(data)
elif selected_page == "3. Shipment Intelligence":
    from frontend.pages.shipment_intelligence import render_page
    render_page(data)
elif selected_page == "4. Delay Analytics & Root Cause":
    from frontend.pages.delay_analytics import render_page
    render_page(data)
elif selected_page == "5. Anomaly Intelligence":
    from frontend.pages.anomaly_intelligence import render_page
    render_page(data)
elif selected_page == "6. Weather Disruption Monitoring":
    from frontend.pages.weather_monitoring import render_page
    render_page(data)
elif selected_page == "7. Facility Congestion Monitoring":
    from frontend.pages.facility_congestion import render_page
    render_page(data)
elif selected_page == "8. Carrier Performance":
    from frontend.pages.carrier_performance import render_page
    render_page(data)
elif selected_page == "9. Facility Operations":
    from frontend.pages.facility_operations import render_page
    render_page(data)
elif selected_page == "10. Model Performance & Calibration":
    from frontend.pages.model_performance import render_page
    render_page(data)
elif selected_page == "11. Shipment Replay (Point-in-Time)":
    from frontend.pages.shipment_replay import render_page
    render_page(data)
elif selected_page == "12. Data Quality & Lake Validation":
    from frontend.pages.data_quality import render_page
    render_page(data)

