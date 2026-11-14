"""Operational Recommendations Engine
Generates deterministic, actionable decision-support recommendations
linked directly to underlying exception types and supporting evidence.
"""

from typing import Dict, Any, List


RECOMMENDATION_MATRIX: Dict[str, Dict[str, Any]] = {
    "NO_SCAN_24H": {
        "title": "Carrier Inactivity Inquiry",
        "action": "Issue formal ping to dispatch carrier operations desk to request GPS last-known fix and trailer inspection.",
        "priority": "HIGH"
    },
    "ETA_SLIP": {
        "title": "Downstream Facility Notice",
        "action": "Alert receiving cross-dock of revised ETA window to reschedule labor staffing and inbound bay allocation.",
        "priority": "MEDIUM"
    },
    "MISSED_CONNECTION": {
        "title": "Expedited Connection Rebooking",
        "action": "Book next outbound linehaul slot or initiate cross-dock recovery to prevent prolonged terminal dwell.",
        "priority": "CRITICAL"
    },
    "SEVERE_WEATHER_ON_PATH": {
        "title": "Weather Route Optimization",
        "action": "Evaluate alternative bypass lane avoiding severe storm/snow corridor or notify consignee of weather force-majeure.",
        "priority": "HIGH"
    },
    "QUEUE_OVERLOAD": {
        "title": "Inbound Gate Metering",
        "action": "Meter upstream dispatch frequency and divert secondary freight to adjacent overflow sorting hub.",
        "priority": "HIGH"
    },
    "SLA_BREACH_RISK": {
        "title": "Priority Freight Upgrade",
        "action": "Tag shipment for expedited cross-dock handling and assign dedicated last-mile courier delivery.",
        "priority": "CRITICAL"
    },
    "ROUTE_INCONSISTENCY": {
        "title": "Topological Leg Re-verification",
        "action": "Audit manifest leg sequence with network planning to confirm route continuity and resolve facility mismatch.",
        "priority": "MEDIUM"
    },
    "DELIVERED_STATE_MISMATCH": {
        "title": "Status Reconciliation Audit",
        "action": "Verify signed electronic Proof of Delivery (ePOD) and manually transition master shipment state to DELIVERED.",
        "priority": "MEDIUM"
    }
}


def get_recommendation_for_exception(exception_type: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Retrieve structured operational recommendation for an exception."""
    rec = RECOMMENDATION_MATRIX.get(exception_type, {
        "title": "General Operational Review",
        "action": "Conduct standard operational triage and monitor shipment progression.",
        "priority": "LOW"
    })
    return {
        "recommendation_title": rec["title"],
        "recommended_action": rec["action"],
        "priority": rec["priority"],
        "governance": "HUMAN_IN_THE_LOOP_DECISION_SUPPORT"
    }

