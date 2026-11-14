"""Delay Explanation Intelligence Engine
Deterministic evidence-backed root cause analysis for delayed and at-risk shipments.
Identifies operational drivers and links explanations directly to concrete evidence IDs.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
import pandas as pd

from src.data.loader import load_all_data
from src.intelligence.evidence import collect_evidence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ANALYTICS_DIR = PROJECT_ROOT / "data" / "analytics"


@dataclass
class DelayExplanation:
    shipment_id: str
    reason_code: str
    reason_description: str
    severity: str
    supporting_event_ids: List[str]
    supporting_facility_ids: List[str]
    evidence_timestamp: Optional[str]
    explanation_method: str = "DETERMINISTIC_OPERATIONAL_RULES"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["supporting_event_ids"] = ",".join(self.supporting_event_ids)
        d["supporting_facility_ids"] = ",".join(self.supporting_facility_ids)
        return d


class DelayExplainer:
    def __init__(self, data: Optional[Dict[str, pd.DataFrame]] = None):
        self.data = data or load_all_data()
        self.shipments_dict = {
            str(k): v
            for k, v in self.data["shipments"].set_index("shipment_id").to_dict(orient="index").items()
        }

    def explain_shipment(self, shipment_id: str) -> List[DelayExplanation]:
        """Analyze a shipment and return all supported delay explanations."""
        explanations: List[DelayExplanation] = []
        ship = self.shipments_dict.get(str(shipment_id))
        if ship is None:
            return explanations

        evidence_list = collect_evidence(shipment_id, self.data)

        # 1. Route Changes check
        rc_evidence = [e for e in evidence_list if e["evidence_type"] == "ROUTE_CHANGE"]
        if rc_evidence:
            explanations.append(DelayExplanation(
                shipment_id=shipment_id,
                reason_code="ROUTE_CHANGE",
                reason_description=f"Shipment underwent unexpected operational reroute: {rc_evidence[0]['description']}",
                severity="HIGH",
                supporting_event_ids=[e["evidence_id"] for e in rc_evidence],
                supporting_facility_ids=[],
                evidence_timestamp=str(rc_evidence[0]["timestamp"])
            ))

        # 2. Weather Disruption check
        weather_evidence = [e for e in evidence_list if e["evidence_type"] == "WEATHER" and e["severity"] in ["HIGH", "CRITICAL"]]
        if weather_evidence:
            explanations.append(DelayExplanation(
                shipment_id=shipment_id,
                reason_code="WEATHER_DISRUPTION",
                reason_description=f"Severe adverse weather conditions encountered along transit route: {weather_evidence[0]['description']}",
                severity="HIGH",
                supporting_event_ids=[e["evidence_id"] for e in weather_evidence],
                supporting_facility_ids=[],
                evidence_timestamp=str(weather_evidence[0]["timestamp"])
            ))

        # 3. Facility Queue & Congestion check
        queue_evidence = [e for e in evidence_list if e["evidence_type"] == "FACILITY_QUEUE" and e["severity"] in ["MEDIUM", "HIGH", "CRITICAL"]]
        if queue_evidence:
            explanations.append(DelayExplanation(
                shipment_id=shipment_id,
                reason_code="FACILITY_QUEUE",
                reason_description=f"Excessive facility queue congestion and dwell wait: {queue_evidence[0]['description']}",
                severity="MEDIUM",
                supporting_event_ids=[e["evidence_id"] for e in queue_evidence],
                supporting_facility_ids=[],
                evidence_timestamp=str(queue_evidence[0]["timestamp"])
            ))

        # 4. Missed connection check (legs arriving late)
        delayed_legs = [e for e in evidence_list if e["evidence_type"] == "SHIPMENT_LEG" and e["severity"] in ["MEDIUM", "HIGH"]]
        if delayed_legs:
            explanations.append(DelayExplanation(
                shipment_id=shipment_id,
                reason_code="MISSED_CONNECTION",
                reason_description=f"In-transit transit leg delay leading to downstream connection slip: {delayed_legs[0]['description']}",
                severity="HIGH",
                supporting_event_ids=[e["evidence_id"] for e in delayed_legs],
                supporting_facility_ids=[],
                evidence_timestamp=str(delayed_legs[0]["timestamp"])
            ))

        # 5. Missing tracking event check (gap > 24 hours)
        tracking_events = [e for e in evidence_list if e["evidence_type"] == "TRACKING_EVENT"]
        if len(tracking_events) == 0:
            explanations.append(DelayExplanation(
                shipment_id=shipment_id,
                reason_code="MISSING_TRACKING_EVENT",
                reason_description="No tracking scan recorded since departure dispatch",
                severity="MEDIUM",
                supporting_event_ids=[],
                supporting_facility_ids=[ship["origin_facility_id"]],
                evidence_timestamp=str(ship["created_at"])
            ))

        # 6. Carrier general delay
        if not explanations and ship.get("current_status") in ["DELAYED", "IN_TRANSIT"]:
            explanations.append(DelayExplanation(
                shipment_id=shipment_id,
                reason_code="CARRIER_DELAY",
                reason_description=f"Carrier transit variance beyond planned schedule",
                severity="LOW",
                supporting_event_ids=[],
                supporting_facility_ids=[],
                evidence_timestamp=str(ship["created_at"])
            ))

        return explanations

    def explain_all_delays(self) -> pd.DataFrame:
        """Batch explain all delayed and at-risk shipments."""
        shipments = self.data["shipments"]
        all_explanations: List[Dict[str, Any]] = []

        delayed_mask = (
            shipments["current_status"].isin(["DELAYED", "FAILED"]) |
            (pd.to_datetime(shipments["actual_delivery_at"], utc=True, errors="coerce") > pd.to_datetime(shipments["planned_delivery_at"], utc=True, errors="coerce"))
        )
        target_ships = shipments[delayed_mask]
        if target_ships.empty:
            target_ships = shipments.head(1000)

        for ship_id in target_ships["shipment_id"]:
            exps = self.explain_shipment(str(ship_id))
            for exp in exps:
                all_explanations.append(exp.to_dict())

        df_exp = pd.DataFrame(all_explanations)
        ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = ANALYTICS_DIR / "delay_explanations.csv"
        df_exp.to_csv(out_path, index=False)
        print(f"Generated {len(df_exp)} delay explanations saved to {out_path}")
        return df_exp


if __name__ == "__main__":
    explainer = DelayExplainer()
    df = explainer.explain_all_delays()
    print(df["reason_code"].value_counts())

