"""Page 3: Shipment Intelligence & Deep Dive"""
import streamlit as st
import pandas as pd
from frontend.utils.charts import plot_event_ingestion_timeline, plot_eta_history


def render_page(data):
    st.markdown('<div class="main-header">Shipment Intelligence & Investigation</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Lifecycle tracing, event occurrence vs. ingestion audit, and ETA historical progression</div>', unsafe_allow_html=True)

    shipments = data["shipments"]
    all_ship_ids = sorted(shipments["shipment_id"].tolist())

    default_idx = 0
    if "selected_shipment_id" in st.session_state and st.session_state["selected_shipment_id"] in all_ship_ids:
        default_idx = all_ship_ids.index(st.session_state["selected_shipment_id"])

    shipment_id = st.selectbox("Select Shipment ID to Inspect", all_ship_ids, index=default_idx)
    st.session_state["selected_shipment_id"] = shipment_id

    ship = shipments[shipments["shipment_id"] == shipment_id].iloc[0]

    # Header KPI block
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Status", ship["current_status"])
    col2.metric("Route", f"{ship['origin_city']} -> {ship['destination_city']}")
    col3.metric("Carrier / Service", f"{ship['carrier_id']} ({ship['service_level']})")
    col4.metric("Distance / Weight", f"{ship['distance_km']:.0f} km / {ship['weight_kg']} kg")

    st.markdown("---")

    # Tabs for organized investigation
    tab1, tab2, tab3, tab4 = st.tabs([
        "Lifecycle Timeline & Ingestion Audit",
        "Point-in-Time ETA History",
        "Root Cause Delay Explanations",
        "Active Exceptions & Interventions"
    ])

    with tab1:
        st.subheader("Event Occurrence vs. System Ingestion Analysis")
        st.caption("Data Source: tracking_events.csv | Evaluates ingestion delay and temporal anomalies")
        events = data["tracking_events"][data["tracking_events"]["shipment_id"] == shipment_id]
        if not events.empty:
            events_sorted = events.sort_values("ingested_at")
            st.plotly_chart(plot_event_ingestion_timeline(events_sorted), use_container_width=True)
            st.markdown("#### Event Ledger (Ordered by Ingestion Time)")
            st.dataframe(events_sorted[["event_id", "event_type", "event_time", "ingested_at", "facility_id", "description"]], use_container_width=True, hide_index=True)
        else:
            st.warning("No tracking events recorded for this shipment.")

        st.markdown("#### Shipment Leg Routing Chain")
        legs = data["shipment_legs"][data["shipment_legs"]["shipment_id"] == shipment_id].sort_values("leg_sequence")
        st.dataframe(legs[["leg_sequence", "leg_id", "origin_facility_id", "destination_facility_id", "transport_mode", "leg_status", "planned_departure_at", "planned_arrival_at"]], use_container_width=True, hide_index=True)

    with tab2:
        st.subheader("Historical ETA Revision Tracking")
        etas = data["eta_snapshots"][data["eta_snapshots"]["shipment_id"] == shipment_id].sort_values("snapshot_time")
        if not etas.empty:
            st.plotly_chart(plot_eta_history(etas, ship["planned_delivery_at"], ship.get("actual_delivery_at")), use_container_width=True)
            st.dataframe(etas[["eta_id", "snapshot_time", "predicted_remaining_hours", "predicted_delivery_at", "prediction_method", "confidence_score"]], use_container_width=True, hide_index=True)
        else:
            st.info("No ETA prediction snapshots recorded for this shipment.")

    with tab3:
        st.subheader("Deterministic Root Cause Evidence")
        explanations = data.get("delay_explanations", pd.DataFrame())
        if not explanations.empty:
            ship_exps = explanations[explanations["shipment_id"] == shipment_id]
            if not ship_exps.empty:
                for _, exp in ship_exps.iterrows():
                    with st.expander(f"[{exp['severity']}] {exp['reason_code']}: {exp['reason_description']}", expanded=True):
                        st.write(f"**Supporting Event IDs**: `{exp.get('supporting_event_ids', 'N/A')}`")
                        st.write(f"**Supporting Facilities**: `{exp.get('supporting_facility_ids', 'N/A')}`")
                        st.write(f"**Timestamp**: {exp.get('evidence_timestamp', 'N/A')}")
            else:
                st.success("No operational delay root causes flagged for this shipment.")
        else:
            st.info("Delay explanation engine analytics not precomputed.")

    with tab4:
        st.subheader("Operational Exceptions")
        exceptions = data.get("exceptions", pd.DataFrame())
        if not exceptions.empty:
            ship_exc = exceptions[exceptions["shipment_id"] == shipment_id]
            if not ship_exc.empty:
                for _, exc in ship_exc.iterrows():
                    st.warning(f"**{exc['exception_type']}** ({exc['severity']}): {exc['description']}")
                    st.info(f"**Action Recommended**: {exc['recommended_action']}")
            else:
                st.success("Zero exceptions open on this shipment.")
        else:
            st.info("No exceptions registered.")

