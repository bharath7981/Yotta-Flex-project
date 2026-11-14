"""Page 12: Data Quality & Lake Validation
Monitors relational integrity, primary key uniqueness, foreign key consistency, and schema rules.
"""

import json
from pathlib import Path
import streamlit as st
import pandas as pd
from src.data.validator import DataValidator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = PROJECT_ROOT / "reports"
VAL_JSON = REPORTS_DIR / "validation_summary.json"
VAL_CSV = REPORTS_DIR / "validation_errors.csv"


def render_page(data):
    st.markdown('<div class="main-header">Data Quality & Lake Validation</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Continuous verification of relational integrity, primary/foreign keys, lifecycle transitions, and temporal logic</div>', unsafe_allow_html=True)

    # Re-run button or load from saved reports
    col_a, col_b = st.columns([3, 1])
    with col_b:
        rerun_val = st.button("🔄 Execute Live Integrity Audit", use_container_width=True)

    if rerun_val or not VAL_JSON.exists():
        with st.spinner("Executing 53 validation rules across all 16 lake entities..."):
            validator = DataValidator(data, allow_expected_anomalies=True)
            report = validator.run_all()
            report_dict = {
                "status": "PASSED" if report.is_valid else "FAILED",
                "total_checks": report.total_checks,
                "passed_checks": report.passed_checks,
                "failed_checks": report.failed_checks,
                "warning_checks": report.warning_checks,
                "issues": [issue.to_dict() for issue in report.issues]
            }
    else:
        with open(VAL_JSON, "r", encoding="utf-8") as f:
            report_dict = json.load(f)

    # Top KPI cards
    status = report_dict.get("status", "PASSED")
    total = report_dict.get("total_checks", 0)
    passed = report_dict.get("passed_checks", 0)
    failed = report_dict.get("failed_checks", 0)
    warnings = report_dict.get("warning_checks", 0)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Validation Status", status)
    c2.metric("Rules Evaluated", f"{total}")
    c3.metric("Passed Checks", f"{passed}")
    c4.metric("Blocking Errors", f"{failed}")
    c5.metric("Controlled Warnings", f"{warnings}")

    st.markdown("---")

    if status == "PASSED" and failed == 0 and warnings == 0:
        st.success("✅ All 53 relational, temporal, and lifecycle integrity constraints are strictly satisfied across all lake tables.")
    elif failed > 0:
        st.error(f"❌ Found {failed} critical integrity violations! Inspect the violation report below.")
    else:
        st.warning(f"⚠️ Found {warnings} controlled operational anomalies flagged for downstream ML isolation.")

    st.subheader("Validation Rules & Findings Matrix")
    issues = report_dict.get("issues", [])
    if not issues:
        st.info("Zero validation issues detected. Lake state is clean and referentially sound.")
    else:
        rows = []
        for issue in issues:
            rows.append({
                "Severity": issue["severity"],
                "Entity Table": issue["table"],
                "Rule Code": issue["rule"],
                "Affected Records": issue["affected_count"],
                "Sample IDs": ", ".join(issue.get("sample_ids", [])[:5]),
                "Description": issue["description"]
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

    st.markdown("---")
    st.subheader("Core Evaluated Rule Categories")
    r1, r2 = st.columns(2)
    with r1:
        st.markdown("""
        - **Primary Key Uniqueness**: Verified across all 16 tables.
        - **Foreign Key Referential Integrity**:
          - `shipments` -> `carriers`, `facilities`, `routes`, `service_levels`
          - `shipment_legs` -> `shipments`, `facilities`
          - `tracking_events` -> `shipments`, `legs`, `facilities`
          - `eta_snapshots` / `eta_estimates` -> `shipments`
          - `facility_queues` -> `facilities`
          - `carrier_calendars` -> `carriers`
          - `facility_calendars` -> `facilities`
        """)
    with r2:
        st.markdown("""
        - **Sequence & Continuity**: Contiguous 1..N leg sequence, physical handoff verification.
        - **Lifecycle Rules**: Cancelled shipments have no in-transit legs; delivered have actual times.
        - **Temporal Sanity**: `planned_delivery > created_at`, `actual_delivery > created_at`.
        - **SLA Delay Consistency**: Verified `delay_hours = max(0, actual - promised - grace)`.
        - **Controlled Anomaly Isolation**: Quarantines known anomalies into `ground_truth.csv`.
        """)

