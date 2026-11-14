"""Data Validator Module — Comprehensive Validation Framework (Part 11)
Validates all relational, temporal, business-rule, and anomaly constraints:
- Primary key uniqueness across all 16 core & supporting entities
- Foreign key referential integrity across all relationships
- Route and leg sequence continuity (contiguous sequences, node handoffs)
- State machine lifecycle transitions
- Timestamp ordering and ingestion latency
- SLA delay calculation verification
- Dual modes: strict clean mode vs anomaly-aware mode
- Report generation: validation_summary.json, validation_summary.md, validation_errors.csv
"""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
import pandas as pd
from src.data.loader import load_all_data


@dataclass
class ValidationIssue:
    severity: str  # ERROR, WARNING, INFO
    table: str
    rule: str
    description: str
    affected_count: int
    sample_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "table": self.table,
            "rule": self.rule,
            "description": self.description,
            "affected_count": self.affected_count,
            "sample_ids": self.sample_ids,
        }


@dataclass
class ValidationReport:
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    warning_checks: int = 0
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not any(issue.severity == "ERROR" for issue in self.issues)

    def summary(self) -> str:
        lines = [
            "=== Validation Summary ===",
            f"Total Checks: {self.total_checks}",
            f"Passed: {self.passed_checks}",
            f"Failed: {self.failed_checks}",
            f"Warnings: {self.warning_checks}",
            f"Status: {'PASSED' if self.is_valid else 'FAILED WITH ERRORS'}",
            "",
            "=== Issues Detected ==="
        ]
        for issue in self.issues:
            lines.append(f"[{issue.severity}] Table '{issue.table}' | Rule: {issue.rule}")
            lines.append(f"  Description: {issue.description}")
            lines.append(f"  Affected records: {issue.affected_count}")
            if issue.sample_ids:
                lines.append(f"  Sample IDs: {issue.sample_ids[:5]}")
        return "\n".join(lines)


class DataValidator:
    def __init__(self, data: Dict[str, pd.DataFrame], allow_expected_anomalies: bool = True):
        self.data = data
        self.allow_expected_anomalies = allow_expected_anomalies
        self.report = ValidationReport()
        self._load_ground_truth_ids()

    def _load_ground_truth_ids(self):
        """Identify IDs marked as known intentional anomalies."""
        self.known_anomaly_ids: Set[str] = set()
        gt = self.data.get("ground_truth_anomalies")
        if gt is None:
            gt = self.data.get("ground_truth")
        if gt is not None and not gt.empty:
            if "entity_id" in gt.columns:
                self.known_anomaly_ids.update(gt["entity_id"].dropna().astype(str).tolist())
            if "anomaly_id" in gt.columns:
                self.known_anomaly_ids.update(gt["anomaly_id"].dropna().astype(str).tolist())
            if "shipment_id" in gt.columns:
                self.known_anomaly_ids.update(gt["shipment_id"].dropna().astype(str).tolist())

    def _check(
        self,
        passed: bool,
        severity: str,
        table: str,
        rule: str,
        desc: str,
        count: int = 0,
        sample_ids: Optional[List[Any]] = None
    ):
        self.report.total_checks += 1
        if passed:
            self.report.passed_checks += 1
        else:
            if severity == "WARNING":
                self.report.warning_checks += 1
            else:
                self.report.failed_checks += 1
            self.report.issues.append(
                ValidationIssue(
                    severity=severity,
                    table=table,
                    rule=rule,
                    description=desc,
                    affected_count=count,
                    sample_ids=[str(s) for s in (sample_ids or [])]
                )
            )

    def validate_primary_keys(self):
        """Verify strict uniqueness of primary keys across all tables."""
        pk_map = {
            "carriers": ["carrier_id"],
            "facilities": ["facility_id"],
            "routes": ["route_id"],
            "service_levels": ["service_level_id"],
            "delay_reasons": ["reason_id", "delay_reason_id"],
            "carrier_calendars": ["calendar_id"],
            "facility_calendars": ["calendar_id"],
            "shipments": ["shipment_id"],
            "shipment_legs": ["leg_id"],
            "shipment_status_history": ["history_id", "status_history_id"],
            "route_change_history": ["history_id", "change_id"],
            "shipment_delay_reasons": ["association_id", "mapping_id"],
            "tracking_events": ["event_id"],
            "eta_snapshots": ["eta_id"],
            "eta_estimates": ["eta_id"],
            "facility_queues": ["queue_id"],
            "weather_events": ["weather_id", "event_id"],
            "weather_forecasts": ["forecast_id", "weather_id"],
            "weather_observations": ["observation_id", "weather_id"],
            "route_changes": ["history_id", "change_id"],
            "disruptions": ["disruption_id", "weather_id"],
            "ground_truth_anomalies": ["anomaly_id"],
            "ground_truth": ["anomaly_id"],
        }
        for table, pks in pk_map.items():
            if table not in self.data:
                continue
            df = self.data[table]
            pk = next((col for col in pks if col in df.columns), None)
            if not pk:
                continue
            dups = df[df.duplicated(subset=[pk], keep=False)]
            passed = len(dups) == 0
            self._check(
                passed=passed,
                severity="ERROR",
                table=table,
                rule="PRIMARY_KEY_UNIQUE",
                desc=f"Primary key '{pk}' must be strictly unique in '{table}'.",
                count=len(dups),
                sample_ids=dups[pk].tolist() if not passed else []
            )

    def validate_foreign_keys(self):
        """Verify foreign key integrity across all relational entities."""
        ship_ids = set(self.data["shipments"]["shipment_id"]) if "shipments" in self.data else set()
        fac_ids = set(self.data["facilities"]["facility_id"]) if "facilities" in self.data else set()
        car_ids = set(self.data["carriers"]["carrier_id"]) if "carriers" in self.data else set()
        route_ids = set(self.data["routes"]["route_id"]) if "routes" in self.data else set()

        # 1. shipment_legs -> shipments.shipment_id
        if "shipment_legs" in self.data:
            legs = self.data["shipment_legs"]
            inv = legs[~legs["shipment_id"].isin(ship_ids)]
            self._check(
                passed=len(inv) == 0,
                severity="ERROR",
                table="shipment_legs",
                rule="FK_SHIPMENT_ID",
                desc="All shipment_legs must reference a valid shipment_id",
                count=len(inv),
                sample_ids=inv["leg_id"].tolist()
            )

            # Leg facilities
            inv_fac = legs[~legs["origin_facility_id"].isin(fac_ids) | ~legs["destination_facility_id"].isin(fac_ids)]
            self._check(
                passed=len(inv_fac) == 0,
                severity="ERROR",
                table="shipment_legs",
                rule="FK_FACILITY_ID",
                desc="Leg origin and destination facilities must exist in facilities table",
                count=len(inv_fac),
                sample_ids=inv_fac["leg_id"].tolist()
            )

        # 2. tracking_events -> shipments.shipment_id, legs.leg_id, facilities.facility_id
        if "tracking_events" in self.data:
            events = self.data["tracking_events"]
            inv_evt_ships = events[~events["shipment_id"].isin(ship_ids)]
            self._check(
                passed=len(inv_evt_ships) == 0,
                severity="ERROR",
                table="tracking_events",
                rule="FK_SHIPMENT_ID",
                desc="All tracking_events must reference a valid shipment_id",
                count=len(inv_evt_ships),
                sample_ids=inv_evt_ships["event_id"].tolist()
            )

            if "shipment_legs" in self.data:
                leg_ids = set(self.data["shipment_legs"]["leg_id"])
                has_leg = events[events["leg_id"].notna() & (events["leg_id"] != "")]
                inv_evt_legs = has_leg[~has_leg["leg_id"].isin(leg_ids)]
                self._check(
                    passed=len(inv_evt_legs) == 0,
                    severity="ERROR",
                    table="tracking_events",
                    rule="FK_LEG_ID",
                    desc="Tracking events with leg_id must reference a valid leg_id in shipment_legs",
                    count=len(inv_evt_legs),
                    sample_ids=inv_evt_legs["event_id"].tolist()
                )

            has_fac = events[events["facility_id"].notna() & (events["facility_id"] != "")]
            inv_evt_facs = has_fac[~has_fac["facility_id"].isin(fac_ids)]
            self._check(
                passed=len(inv_evt_facs) == 0,
                severity="ERROR",
                table="tracking_events",
                rule="FK_FACILITY_ID",
                desc="Tracking events with facility_id must reference a valid facility",
                count=len(inv_evt_facs),
                sample_ids=inv_evt_facs["event_id"].tolist()
            )

        # 3. eta_snapshots / eta_estimates -> shipments.shipment_id
        for eta_tbl in ["eta_snapshots", "eta_estimates"]:
            if eta_tbl in self.data:
                etas = self.data[eta_tbl]
                inv_eta_ships = etas[~etas["shipment_id"].isin(ship_ids)]
                self._check(
                    passed=len(inv_eta_ships) == 0,
                    severity="ERROR",
                    table=eta_tbl,
                    rule="FK_SHIPMENT_ID",
                    desc=f"All {eta_tbl} must reference a valid shipment_id",
                    count=len(inv_eta_ships),
                    sample_ids=inv_eta_ships["eta_id"].tolist()
                )

        # 4. shipments -> carriers.carrier_id, facilities
        if "shipments" in self.data:
            ships = self.data["shipments"]
            inv_ship_cars = ships[~ships["carrier_id"].isin(car_ids)]
            self._check(
                passed=len(inv_ship_cars) == 0,
                severity="ERROR",
                table="shipments",
                rule="FK_CARRIER_ID",
                desc="All shipments must reference a valid carrier_id",
                count=len(inv_ship_cars),
                sample_ids=inv_ship_cars["shipment_id"].tolist()
            )

            inv_orig = ships[~ships["origin_facility_id"].isin(fac_ids)]
            self._check(
                passed=len(inv_orig) == 0,
                severity="ERROR",
                table="shipments",
                rule="FK_ORIGIN_FACILITY_ID",
                desc="Shipment origin_facility_id must reference a valid facility",
                count=len(inv_orig),
                sample_ids=inv_orig["shipment_id"].tolist()
            )

            inv_dest = ships[~ships["destination_facility_id"].isin(fac_ids)]
            self._check(
                passed=len(inv_dest) == 0,
                severity="ERROR",
                table="shipments",
                rule="FK_DEST_FACILITY_ID",
                desc="Shipment destination_facility_id must reference a valid facility",
                count=len(inv_dest),
                sample_ids=inv_dest["shipment_id"].tolist()
            )

            if "route_id" in ships.columns and route_ids:
                has_route = ships[ships["route_id"].notna() & (ships["route_id"] != "")]
                inv_routes = has_route[~has_route["route_id"].isin(route_ids)]
                self._check(
                    passed=len(inv_routes) == 0,
                    severity="ERROR",
                    table="shipments",
                    rule="FK_ROUTE_ID",
                    desc="Shipments with route_id must reference a valid route",
                    count=len(inv_routes),
                    sample_ids=inv_routes["shipment_id"].tolist()
                )

        # 5. Supporting tables FKs
        if "shipment_status_history" in self.data:
            ssh = self.data["shipment_status_history"]
            inv_ssh = ssh[~ssh["shipment_id"].isin(ship_ids)]
            self._check(
                passed=len(inv_ssh) == 0,
                severity="ERROR",
                table="shipment_status_history",
                rule="FK_SHIPMENT_ID",
                desc="Status history must reference a valid shipment",
                count=len(inv_ssh),
                sample_ids=inv_ssh["history_id"].tolist()
            )

        if "route_change_history" in self.data:
            rch = self.data["route_change_history"]
            pk_col = "history_id" if "history_id" in rch.columns else "change_id"
            inv_rch = rch[~rch["shipment_id"].isin(ship_ids)]
            self._check(
                passed=len(inv_rch) == 0,
                severity="ERROR",
                table="route_change_history",
                rule="FK_SHIPMENT_ID",
                desc="Route change history must reference a valid shipment",
                count=len(inv_rch),
                sample_ids=inv_rch[pk_col].tolist() if pk_col in inv_rch.columns else []
            )

        if "shipment_delay_reasons" in self.data:
            sdr = self.data["shipment_delay_reasons"]
            pk_col = "association_id" if "association_id" in sdr.columns else ("mapping_id" if "mapping_id" in sdr.columns else sdr.columns[0])
            inv_sdr_ship = sdr[~sdr["shipment_id"].isin(ship_ids)]
            self._check(
                passed=len(inv_sdr_ship) == 0,
                severity="ERROR",
                table="shipment_delay_reasons",
                rule="FK_SHIPMENT_ID",
                desc="Shipment delay reasons must reference a valid shipment",
                count=len(inv_sdr_ship),
                sample_ids=inv_sdr_ship[pk_col].tolist() if pk_col in inv_sdr_ship.columns else []
            )

            if "delay_reasons" in self.data:
                dr = self.data["delay_reasons"]
                r_col = "reason_id" if "reason_id" in dr.columns else "delay_reason_id"
                sdr_r_col = "reason_id" if "reason_id" in sdr.columns else "delay_reason_id"
                if r_col in dr.columns and sdr_r_col in sdr.columns:
                    reason_ids = set(dr[r_col])
                    inv_sdr_reason = sdr[~sdr[sdr_r_col].isin(reason_ids)]
                    self._check(
                        passed=len(inv_sdr_reason) == 0,
                        severity="ERROR",
                        table="shipment_delay_reasons",
                        rule="FK_DELAY_REASON_ID",
                        desc="Shipment delay reasons must reference a valid delay_reason_id",
                        count=len(inv_sdr_reason),
                        sample_ids=inv_sdr_reason[pk_col].tolist() if pk_col in inv_sdr_reason.columns else []
                    )

        if "carrier_calendars" in self.data:
            cc = self.data["carrier_calendars"]
            inv_cc = cc[~cc["carrier_id"].isin(car_ids)]
            self._check(
                passed=len(inv_cc) == 0,
                severity="ERROR",
                table="carrier_calendars",
                rule="FK_CARRIER_ID",
                desc="Carrier calendars must reference an existing carrier_id",
                count=len(inv_cc),
                sample_ids=inv_cc["calendar_id"].tolist()
            )

        if "facility_calendars" in self.data:
            fc = self.data["facility_calendars"]
            inv_fc = fc[~fc["facility_id"].isin(fac_ids)]
            self._check(
                passed=len(inv_fc) == 0,
                severity="ERROR",
                table="facility_calendars",
                rule="FK_FACILITY_ID",
                desc="Facility calendars must reference an existing facility_id",
                count=len(inv_fc),
                sample_ids=inv_fc["calendar_id"].tolist()
            )

        if "facility_queues" in self.data:
            fq = self.data["facility_queues"]
            inv_fq = fq[~fq["facility_id"].isin(fac_ids)]
            self._check(
                passed=len(inv_fq) == 0,
                severity="ERROR",
                table="facility_queues",
                rule="FK_FACILITY_ID",
                desc="Facility queues must reference a valid facility_id",
                count=len(inv_fq),
                sample_ids=inv_fq["queue_id"].tolist()
            )

    def validate_enums(self):
        """Validate categorical enum domains."""
        # 1. service_level
        valid_sl = {"STANDARD", "EXPRESS", "PRIORITY", "ECONOMY", "SAME_DAY", "NEXT_DAY"}
        if "shipments" in self.data:
            ships = self.data["shipments"]
            inv_sl = ships[~ships["service_level"].astype(str).str.upper().isin(valid_sl)]
            self._check(
                passed=len(inv_sl) == 0,
                severity="ERROR",
                table="shipments",
                rule="ENUM_SERVICE_LEVEL",
                desc=f"service_level must be one of {valid_sl}",
                count=len(inv_sl),
                sample_ids=inv_sl["shipment_id"].tolist()
            )

        # 2. current_status
        valid_status = {"IN_TRANSIT", "DELIVERED", "DELAYED", "AT_FACILITY", "CANCELLED", "CREATED"}
        if "shipments" in self.data:
            inv_status = ships[~ships["current_status"].astype(str).str.upper().isin(valid_status)]
            self._check(
                passed=len(inv_status) == 0,
                severity="ERROR",
                table="shipments",
                rule="ENUM_SHIPMENT_STATUS",
                desc=f"current_status must be one of {valid_status}",
                count=len(inv_status),
                sample_ids=inv_status["shipment_id"].tolist()
            )

        # 3. transport_mode
        valid_modes = {"TRUCK", "AIR", "RAIL", "OCEAN"}
        if "shipment_legs" in self.data:
            legs = self.data["shipment_legs"]
            inv_modes = legs[~legs["transport_mode"].astype(str).str.upper().isin(valid_modes)]
            self._check(
                passed=len(inv_modes) == 0,
                severity="ERROR",
                table="shipment_legs",
                rule="ENUM_TRANSPORT_MODE",
                desc=f"transport_mode must be one of {valid_modes}",
                count=len(inv_modes),
                sample_ids=inv_modes["leg_id"].tolist()
            )

        # 4. event_type
        valid_events = {"PICKUP", "DEPARTURE", "ARRIVAL", "FACILITY_PROCESSING", "OUT_FOR_DELIVERY", "DELIVERED", "EXCEPTION", "DELAY"}
        if "tracking_events" in self.data:
            events = self.data["tracking_events"]
            inv_evts = events[~events["event_type"].astype(str).str.upper().isin(valid_events)]
            self._check(
                passed=len(inv_evts) == 0,
                severity="ERROR",
                table="tracking_events",
                rule="ENUM_EVENT_TYPE",
                desc=f"event_type must be one of {valid_events}",
                count=len(inv_evts),
                sample_ids=inv_evts["event_id"].tolist()
            )

        # 5. facility_type
        valid_fac_types = {"ORIGIN_HUB", "DISTRIBUTION_CENTER", "SORTING_FACILITY", "CROSS_DOCK", "DESTINATION_HUB"}
        if "facilities" in self.data:
            facs = self.data["facilities"]
            inv_fac_types = facs[~facs["facility_type"].astype(str).str.upper().isin(valid_fac_types)]
            self._check(
                passed=len(inv_fac_types) == 0,
                severity="ERROR",
                table="facilities",
                rule="ENUM_FACILITY_TYPE",
                desc=f"facility_type must be one of {valid_fac_types}",
                count=len(inv_fac_types),
                sample_ids=inv_fac_types["facility_id"].tolist()
            )

    def validate_leg_ordering(self):
        """Verify leg_sequence starts at 1 and increases contiguously by 1; verify physical facility handoff."""
        if "shipment_legs" not in self.data:
            return
        legs = self.data["shipment_legs"]
        disordered_ships = []
        broken_handoffs = []

        for ship_id, ship_legs in legs.groupby("shipment_id"):
            sorted_legs = ship_legs.sort_values("leg_sequence")
            seqs = sorted_legs["leg_sequence"].tolist()
            expected = list(range(1, len(seqs) + 1))
            if seqs != expected:
                disordered_ships.append(ship_id)

            # Node continuity: destination of leg i == origin of leg i+1
            leg_list = sorted_legs.to_dict(orient="records")
            for i in range(len(leg_list) - 1):
                if leg_list[i]["destination_facility_id"] != leg_list[i + 1]["origin_facility_id"]:
                    broken_handoffs.append(ship_id)
                    break

        self._check(
            passed=len(disordered_ships) == 0,
            severity="ERROR",
            table="shipment_legs",
            rule="LEG_SEQUENCE_CONTIGUOUS",
            desc="leg_sequence values must start at 1 and be strictly contiguous",
            count=len(disordered_ships),
            sample_ids=disordered_ships
        )

        unexpected_broken = [s for s in broken_handoffs if s not in self.known_anomaly_ids]
        severity = "WARNING" if self.allow_expected_anomalies else "ERROR"
        count = len(unexpected_broken) if self.allow_expected_anomalies else len(broken_handoffs)
        sample_ids = unexpected_broken if self.allow_expected_anomalies else broken_handoffs

        self._check(
            passed=count == 0,
            severity=severity,
            table="shipment_legs",
            rule="LEG_FACILITY_HANDOFF_CONTINUITY",
            desc="Destination facility of leg i must match origin facility of leg i+1 (controlled operational anomaly when expected)",
            count=count,
            sample_ids=sample_ids
        )

    def validate_lifecycle_transitions(self):
        """Verify business lifecycle rules."""
        if "shipments" not in self.data or "shipment_legs" not in self.data:
            return
        ships = self.data["shipments"]
        legs = self.data["shipment_legs"]

        # Rule 1: CANCELLED shipments cannot have IN_TRANSIT legs
        cancelled_ships = set(ships[ships["current_status"] == "CANCELLED"]["shipment_id"])
        inv_cancelled_legs = legs[legs["shipment_id"].isin(cancelled_ships) & (legs["leg_status"] == "IN_TRANSIT")]
        self._check(
            passed=len(inv_cancelled_legs) == 0,
            severity="ERROR",
            table="shipment_legs",
            rule="LIFECYCLE_CANCELLED_NO_IN_TRANSIT",
            desc="CANCELLED shipments must not have legs in IN_TRANSIT state",
            count=len(inv_cancelled_legs),
            sample_ids=inv_cancelled_legs["leg_id"].tolist()
        )

        # Rule 2: DELIVERED shipments must have actual_delivery_at populated
        delivered = ships[ships["current_status"] == "DELIVERED"]
        missing_delivery_dt = delivered[delivered["actual_delivery_at"].isna()]
        self._check(
            passed=len(missing_delivery_dt) == 0,
            severity="ERROR",
            table="shipments",
            rule="LIFECYCLE_DELIVERED_HAS_ACTUAL_TIME",
            desc="DELIVERED shipments must have actual_delivery_at populated",
            count=len(missing_delivery_dt),
            sample_ids=missing_delivery_dt["shipment_id"].tolist()
        )

    def validate_timestamps(self):
        """Verify timestamp ordering, ingestion lag, and anomaly isolation."""
        if "tracking_events" in self.data:
            events = self.data["tracking_events"]
            confused = events[events["ingested_at"] < events["event_time"]]
            is_anomaly = confused["event_id"].isin(self.known_anomaly_ids) | confused["shipment_id"].isin(self.known_anomaly_ids)
            unexpected_confused = confused[~is_anomaly]

            severity = "WARNING" if self.allow_expected_anomalies else "ERROR"
            count = len(unexpected_confused) if self.allow_expected_anomalies else len(confused)
            sample_ids = unexpected_confused["event_id"].tolist() if self.allow_expected_anomalies else confused["event_id"].tolist()

            self._check(
                passed=count == 0,
                severity=severity,
                table="tracking_events",
                rule="INGESTION_TIME_CONSISTENCY",
                desc="ingested_at should be >= event_time (known controlled operational anomaly when expected)",
                count=count,
                sample_ids=sample_ids
            )

        if "shipments" in self.data:
            shipments = self.data["shipments"]
            invalid_plans = shipments[shipments["planned_delivery_at"] <= shipments["created_at"]]
            self._check(
                passed=len(invalid_plans) == 0,
                severity="ERROR",
                table="shipments",
                rule="PLAN_TIME_ORDERING",
                desc="planned_delivery_at must be strictly after created_at",
                count=len(invalid_plans),
                sample_ids=invalid_plans["shipment_id"].tolist()
            )

            # Delivered shipments: actual_delivery_at >= created_at
            deliv = shipments[shipments["actual_delivery_at"].notna()]
            invalid_deliv = deliv[deliv["actual_delivery_at"] < deliv["created_at"]]
            self._check(
                passed=len(invalid_deliv) == 0,
                severity="ERROR",
                table="shipments",
                rule="DELIVERY_AFTER_CREATION",
                desc="actual_delivery_at must be after created_at",
                count=len(invalid_deliv),
                sample_ids=invalid_deliv["shipment_id"].tolist()
            )

    def validate_sla_calculations(self):
        """Verify SLA delay calculations match delay_hours = max(0, actual - promised - grace)."""
        if "shipments" not in self.data:
            return
        ships = self.data["shipments"]
        if "actual_delivery_at" not in ships.columns or "promised_delivery_at" not in ships.columns:
            return

        deliv = ships[ships["actual_delivery_at"].notna() & ships["promised_delivery_at"].notna()].copy()
        if "delay_hours" in deliv.columns and "grace_period_hours" in deliv.columns:
            actual_dt = pd.to_datetime(deliv["actual_delivery_at"], utc=True)
            promised_dt = pd.to_datetime(deliv["promised_delivery_at"], utc=True)
            diff_hours = (actual_dt - promised_dt).dt.total_seconds() / 3600.0
            expected_delays = (diff_hours - deliv["grace_period_hours"].fillna(0)).clip(lower=0.0)

            # Tolerant up to 0.05h for float precision
            mismatches = deliv[abs(deliv["delay_hours"].fillna(0) - expected_delays) > 0.05]
            self._check(
                passed=len(mismatches) == 0,
                severity="ERROR",
                table="shipments",
                rule="SLA_DELAY_CALCULATION_CORRECT",
                desc="delay_hours must strictly match max(0, actual_delivery - promised_delivery - grace_period)",
                count=len(mismatches),
                sample_ids=mismatches["shipment_id"].tolist()
            )

    def run_all(self) -> ValidationReport:
        self.validate_primary_keys()
        self.validate_foreign_keys()
        self.validate_enums()
        self.validate_leg_ordering()
        self.validate_lifecycle_transitions()
        self.validate_timestamps()
        self.validate_sla_calculations()
        return self.report


def validate_clean_data(data: Optional[Dict[str, pd.DataFrame]] = None) -> ValidationReport:
    """Validate data assuming zero tolerance for anomalies."""
    d = data or load_all_data()
    return DataValidator(d, allow_expected_anomalies=False).run_all()


def validate_with_expected_anomalies(data: Optional[Dict[str, pd.DataFrame]] = None) -> ValidationReport:
    """Validate data treating controlled anomalies as warnings."""
    d = data or load_all_data()
    return DataValidator(d, allow_expected_anomalies=True).run_all()


def validate_dataset() -> ValidationReport:
    return validate_with_expected_anomalies()


def generate_validation_reports(output_dir: str = "reports", data: Optional[Dict[str, pd.DataFrame]] = None) -> Dict[str, str]:
    """Execute complete validation suite and generate summary JSON, Markdown, and error CSV reports."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    d = data or load_all_data()
    validator = DataValidator(d, allow_expected_anomalies=True)
    report = validator.run_all()

    # 1. Generate JSON report
    json_path = out_path / "validation_summary.json"
    json_data = {
        "status": "PASSED" if report.is_valid else "FAILED",
        "total_checks": report.total_checks,
        "passed_checks": report.passed_checks,
        "failed_checks": report.failed_checks,
        "warning_checks": report.warning_checks,
        "issues": [issue.to_dict() for issue in report.issues],
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2)

    # 2. Generate CSV error / warning report
    csv_path = out_path / "validation_errors.csv"
    error_rows = []
    for issue in report.issues:
        error_rows.append({
            "severity": issue.severity,
            "table": issue.table,
            "rule": issue.rule,
            "affected_count": issue.affected_count,
            "sample_ids": ";".join(issue.sample_ids[:10]),
            "description": issue.description,
        })
    errors_df = pd.DataFrame(error_rows, columns=["severity", "table", "rule", "affected_count", "sample_ids", "description"])
    errors_df.to_csv(csv_path, index=False)

    # 3. Generate Markdown report
    md_path = out_path / "validation_summary.md"
    md_lines = [
        "# Data Lake Validation Summary Report",
        "",
        f"- **Validation Status:** `{'PASSED' if report.is_valid else 'FAILED'}`",
        f"- **Total Rules Evaluated:** {report.total_checks}",
        f"- **Passed Checks:** {report.passed_checks}",
        f"- **Failed (Blocking Errors):** {report.failed_checks}",
        f"- **Warnings (Controlled Anomalies):** {report.warning_checks}",
        "",
        "## Summary of Evaluated Rules",
        "",
        "| Table | Rule | Severity | Status | Affected Records | Description |",
        "|---|---|---|---|---|---|",
    ]
    if not report.issues:
        md_lines.append("| All | All Rules | INFO | PASSED | 0 | All referential and business rules strictly satisfied. |")
    else:
        for issue in report.issues:
            status_badge = "❌ FAILED" if issue.severity == "ERROR" else "⚠️ WARNING"
            md_lines.append(f"| `{issue.table}` | `{issue.rule}` | `{issue.severity}` | {status_badge} | {issue.affected_count} | {issue.description} |")

    md_lines.extend([
        "",
        "## Controlled Anomaly Isolation",
        "Controlled operational anomalies injected for model benchmarking (e.g., GPS drift, inverted timestamps, facility congestion) are quarantined and flagged for downstream ML feature pipelines without breaking foundational referential integrity.",
        "",
        "## Recommended Actions",
        "- For any `ERROR` severity items, inspect source ingestion adapters.",
        "- For `WARNING` severity items, ensure point-in-time feature builders respect the `ingested_at` cutoff.",
        ""
    ])

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    return {
        "json": str(json_path),
        "csv": str(csv_path),
        "markdown": str(md_path),
    }


if __name__ == "__main__":
    report_files = generate_validation_reports()
    print("Validation reports generated successfully:")
    for k, v in report_files.items():
        print(f"  {k}: {v}")
