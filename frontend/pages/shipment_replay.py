"""Page 8: Shipment Replay & Point-in-Time Investigation"""
from datetime import datetime, timezone, timedelta
import streamlit as st
import pandas as pd
from src.features.asof import AsOfView


def render_page(data):
    st.markdown('<div class="main-header">Shipment Replay & Historical Reconstruction</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Interactive time-travel investigation: reconstruct system knowledge strictly as of any historical timestamp</div>', unsafe_allow_html=True)

    shipments = data["shipments"]
    all_ship_ids = sorted(shipments["shipment_id"].tolist())

    default_idx = 0
    if "selected_shipment_id" in st.session_state and st.session_state["selected_shipment_id"] in all_ship_ids:
        default_idx = all_ship_ids.index(st.session_state["selected_shipment_id"])

    shipment_id = st.selectbox("Select Shipment for Replay Analysis", all_ship_ids, index=default_idx)
    st.session_state["selected_shipment_id"] = shipment_id

    ship = shipments[shipments["shipment_id"] == shipment_id].iloc[0]

    # Determine timeline boundaries
    t_start = pd.to_datetime(ship["created_at"], utc=True)
    if pd.notna(ship.get("actual_delivery_at")):
        t_end = pd.to_datetime(ship["actual_delivery_at"], utc=True)
    else:
        t_end = pd.to_datetime(ship["planned_delivery_at"], utc=True)

    total_hours = max(1.0, (t_end - t_start).total_seconds() / 3600.0)

    # Time Slider
    elapsed_hours = st.slider(
        "Simulation Time Slider (Hours Elapsed Since Creation)",
        min_value=0.0,
        max_value=float(total_hours),
        value=float(total_hours * 0.5),
        step=1.0
    )

    as_of_time = t_start + timedelta(hours=elapsed_hours)

    st.info(f"**As-Of Snapshot Time**: `{as_of_time.strftime('%Y-%m-%d %H:%M:%S UTC')}` (Elapsed: **{elapsed_hours:.1f}** hours / Progress: **{min(100.0, (elapsed_hours/total_hours)*100):.1f}%**)")

    asof = AsOfView(data)

    # Reconstruct Point-in-Time Knowledge
    events_known = asof.get_tracking_events(shipment_id, as_of_time)
    route_changes_known = asof.get_route_changes(shipment_id, as_of_time)

    # Determine state as of time
    if events_known.empty:
        state_known = "REGISTERED / AT_ORIGIN"
        curr_facility = ship["origin_facility_id"]
    else:
        last_evt = events_known.iloc[-1]
        state_known = f"LAST SCANNED: {last_evt['event_type']} at {last_evt['facility_id']}"
        curr_facility = last_evt["facility_id"]

    q_known = asof.get_facility_queue(curr_facility, as_of_time)
    wf_known = asof.get_weather_forecast(curr_facility, as_of_time)

    # Top metrics known at that time
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Known System State", state_known)
    c2.metric("Events Ingested", len(events_known))
    c3.metric("Facility Queue", f"{q_known['queue_length'] if q_known is not None else 0} units")
    c4.metric("Weather Condition", f"{wf_known['weather_type'] if wf_known is not None else 'CLEAR'}")

    st.markdown("---")

    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("Events Ingested Into System (<= Snapshot Time)")
        if not events_known.empty:
            st.dataframe(
                events_known[["event_id", "event_type", "event_time", "ingested_at", "facility_id", "description"]],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("No tracking events had been ingested into the platform by this timestamp.")

    with col_right:
        st.subheader("Point-in-Time Reconstructed ETA")
        # Find snapshot closest to as_of_time
        etas = data["eta_snapshots"][data["eta_snapshots"]["shipment_id"] == shipment_id]
        if not etas.empty:
            etas_copy = etas.copy()
            etas_copy["snap_dt"] = pd.to_datetime(etas_copy["snapshot_time"], utc=True)
            past_snaps = etas_copy[etas_copy["snap_dt"] <= as_of_time]
            if not past_snaps.empty:
                latest_snap = past_snaps.sort_values("snap_dt").iloc[-1]
                st.success(f"**Authoritative Predicted ETA**: {latest_snap['predicted_delivery_at']}")
                st.write(f"Remaining Hours Estimate: **{latest_snap['predicted_remaining_hours']:.1f}** hours")
                st.write(f"Prediction Method: `{latest_snap['prediction_method']}` ({latest_snap['model_version']})")
                st.write(f"Confidence Score: **{latest_snap['confidence_score']:.1%}**")
            else:
                st.info("Shipment planned schedule active; first automated ETA snapshot pending at this timestamp.")
        else:
            st.info("No snapshots available.")

        st.subheader("Route Changes Known (<= Snapshot Time)")
        if not route_changes_known.empty:
            st.dataframe(route_changes_known[["change_id", "change_type", "recorded_at", "impact_hours"]], use_container_width=True, hide_index=True)
        else:
            st.write("No route alterations were known to the system by this timestamp.")

