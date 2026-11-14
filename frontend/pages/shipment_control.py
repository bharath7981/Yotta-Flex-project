"""Page 2: Shipment Control Tower"""
import streamlit as st
import pandas as pd


def render_page(data):
    st.markdown('<div class="main-header">Shipment Control Tower</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Multi-attribute filterable dispatch ledger and real-time monitoring</div>', unsafe_allow_html=True)

    shipments = data["shipments"].copy()

    # Filter Bar
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        statuses = ["ALL"] + sorted(shipments["current_status"].unique().tolist())
        selected_status = st.selectbox("Status Filter", statuses)
    with f2:
        carriers = ["ALL"] + sorted(shipments["carrier_id"].unique().tolist())
        selected_carrier = st.selectbox("Carrier Filter", carriers)
    with f3:
        services = ["ALL"] + sorted(shipments["service_level"].unique().tolist())
        selected_service = st.selectbox("Service Level", services)
    with f4:
        search_query = st.text_input("Search Shipment ID / City", "")

    # Apply Filters
    df = shipments
    if selected_status != "ALL":
        df = df[df["current_status"] == selected_status]
    if selected_carrier != "ALL":
        df = df[df["carrier_id"] == selected_carrier]
    if selected_service != "ALL":
        df = df[df["service_level"] == selected_service]
    if search_query:
        mask = (
            df["shipment_id"].str.contains(search_query, case=False, na=False) |
            df["origin_city"].str.contains(search_query, case=False, na=False) |
            df["destination_city"].str.contains(search_query, case=False, na=False)
        )
        df = df[mask]

    st.write(f"Showing **{len(df):,}** of **{len(shipments):,}** shipments")

    # Display Table with interactive selection
    display_cols = [
        "shipment_id", "current_status", "service_level", "carrier_id",
        "origin_city", "destination_city", "distance_km",
        "planned_delivery_at", "actual_delivery_at"
    ]

    event = st.dataframe(
        df[display_cols],
        use_container_width=True,
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun"
    )

    if event.selection and event.selection.rows:
        selected_idx = event.selection.rows[0]
        selected_ship_id = df.iloc[selected_idx]["shipment_id"]
        st.session_state["selected_shipment_id"] = selected_ship_id
        st.success(f"Selected Shipment **{selected_ship_id}**. Navigate to 'Shipment Intelligence' or 'Shipment Replay' to investigate.")

