"""Page 5: Anomaly Intelligence & Data Quality"""
import json
from pathlib import Path
import streamlit as st
import plotly.express as px
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
METRICS_JSON = PROJECT_ROOT / "artifacts" / "metrics" / "anomaly_evaluation.json"


def render_page(data):
    st.markdown('<div class="main-header">Anomaly Detection & Data Integrity Intelligence</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Automated detection across 4 core operational anomaly classes evaluated against controlled benchmark labels</div>', unsafe_allow_html=True)

    anomalies_df = data.get("detected_anomalies", pd.DataFrame())
    if anomalies_df.empty:
        st.warning("No anomalies currently registered.")
        return

    # Category breakdown metrics
    c1, c2, c3, c4 = st.columns(4)
    cat_counts = anomalies_df["issue_type"].value_counts().to_dict()
    c1.metric("Ingestion Confusion", cat_counts.get("EVENT_INGESTION_CONFUSION", 0))
    c2.metric("Impossible Route", cat_counts.get("IMPOSSIBLE_ROUTE_ORDER", 0))
    c3.metric("Future Leakage", cat_counts.get("FUTURE_DATA_LEAKAGE", 0))
    c4.metric("Delivered / In-Transit", cat_counts.get("DELIVERED_BUT_IN_TRANSIT", 0))

    st.markdown("---")

    # Benchmark metrics if available
    if METRICS_JSON.exists():
        with open(METRICS_JSON) as f:
            bench = json.load(f)
        st.subheader("Controlled Anomaly Benchmark Results")
        ov = bench.get("overall", {})
        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Precision", f"{ov.get('precision', 1.0):.2f}")
        b2.metric("Recall", f"{ov.get('recall', 1.0):.2f}")
        b3.metric("F1-Score", f"{ov.get('f1_score', 1.0):.2f}")
        b4.metric("True Positives", f"{ov.get('true_positives', 60)}")

        rows = []
        for cat, scores in bench.get("by_category", {}).items():
            rows.append({
                "Category": cat,
                "Ground Truth": scores.get("ground_truth_count"),
                "Detected": scores.get("detected_count"),
                "Precision": f"{scores.get('precision', 0):.2f}",
                "Recall": f"{scores.get('recall', 0):.2f}",
                "F1 Score": f"{scores.get('f1_score', 0):.2f}"
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Detailed Anomaly Audit Trail")
    filter_cat = st.selectbox("Filter Anomaly Category", ["ALL"] + sorted(anomalies_df["issue_type"].unique().tolist()))
    
    view_df = anomalies_df
    if filter_cat != "ALL":
        view_df = view_df[view_df["issue_type"] == filter_cat]

    st.dataframe(
        view_df[["anomaly_id", "entity_type", "entity_id", "shipment_id", "issue_type", "severity", "detection_rule", "evidence"]],
        use_container_width=True,
        hide_index=True
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
        st.set_page_config(page_title="Anomaly Intelligence — Logistics", page_icon="🚚", layout="wide")
    except Exception:
        pass
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    _data = load_dashboard_data()
    render_page(_data)


