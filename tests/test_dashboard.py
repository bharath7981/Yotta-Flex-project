"""Automated Tests for 12-Page Streamlit Dashboard
Verifies that all pages render cleanly with zero exceptions.
"""

import pytest
from streamlit.testing.v1 import AppTest


@pytest.fixture(scope="module")
def app_test():
    at = AppTest.from_file("frontend/streamlit_app.py", default_timeout=60)
    at.run()
    return at


def test_app_initial_load(app_test):
    assert not app_test.exception, f"App initial load raised exception: {app_test.exception}"
    assert len(app_test.sidebar.radio) > 0


@pytest.mark.parametrize("page_index,page_name", [
    (0, "1. Executive Overview"),
    (1, "2. Shipment Control Tower"),
    (2, "3. Shipment Intelligence"),
    (3, "4. Delay Analytics & Root Cause"),
    (4, "5. Anomaly Intelligence"),
    (5, "6. Weather Disruption Monitoring"),
    (6, "7. Facility Congestion Monitoring"),
    (7, "8. Carrier Performance"),
    (8, "9. Facility Operations"),
    (9, "10. Model Performance & Calibration"),
    (10, "11. Shipment Replay (Point-in-Time)"),
    (11, "12. Data Quality & Lake Validation"),
])
def test_all_12_dashboard_pages(page_index, page_name):
    at = AppTest.from_file("frontend/streamlit_app.py", default_timeout=30)
    at.run()
    # Select target page
    at.sidebar.radio[0].set_value(page_name)
    at.run()
    assert not at.exception, f"Page '{page_name}' crashed with: {at.exception}"

