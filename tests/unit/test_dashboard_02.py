"""Unit tests for deterministic Dashboard 2 acquisition logic."""

from __future__ import annotations

import json

import pandas as pd

from cepe_fynsp.dashboards.dashboard_02_acquisition_schedule import (
    aggregate_acquisition_type_by_funding_level,
    aggregate_li_tec_li_opc_site_year,
    build_dashboard_02_payloads,
    detect_acquisition_schedule_exceptions,
)


def _crosscuts() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "acquisition_type": ["LI TEC", None, "LI OPC"],
            "acquisition_id": ["A", None, "B"],
            "acquisition_name": ["Alpha", None, "Bravo"],
            "acquisition_start_date": ["2028-01-01", None, "2031-01-01"],
            "acquisition_end_date": ["2030-01-01", None, "2030-01-01"],
            "fiscal_year_number": [2029, 2028, 2028],
            "funding_level_normalized": ["Baseline", "ROT", "UFR"],
            "formulated_measure": [100.0, 200.0, 300.0],
            "source_row_id": ["a", "b", "c"],
            "program_request": ["A", "B", "C"],
            "program_priority": [1, 2, 3],
            "doe_priority_tier": [1, 2, 1],
        }
    )


def test_acquisition_type_aggregation_uses_no_tag_bucket() -> None:
    data = aggregate_acquisition_type_by_funding_level(_crosscuts())
    assert {row["acquisition_type"] for row in data} == {"LI TEC", "LI OPC", "No acquisition tag"}
    assert sum(row["amount"] for row in data) == 600.0


def test_schedule_exception_detection_flags_bad_and_missing_dates() -> None:
    crosscuts = _crosscuts().copy()
    crosscuts.loc[1, "acquisition_type"] = "LI TEC"
    data = detect_acquisition_schedule_exceptions(crosscuts, materiality_threshold=150.0)
    by_rule = {row["rule_id"]: row for row in data}
    assert by_rule["AQ003"]["row_count"] == 1
    assert by_rule["AQ005"]["row_count"] == 1
    assert by_rule["AQ006"]["row_count"] == 1
    assert by_rule["AQ007"]["row_count"] == 1


def test_li_tec_li_opc_filter_uses_only_matching_types() -> None:
    sites = _crosscuts().assign(
        site_planex=["LANL", "SRS-SRNS", "LANL"],
        fiscal_year_normalized=["FY2029", "FY2028", "FY2028"],
    )
    data = aggregate_li_tec_li_opc_site_year(sites)
    assert {row["acquisition_type"] for row in data} == {"LI TEC", "LI OPC"}
    assert sum(row["amount"] for row in data) == 400.0


def test_dashboard_02_build_writes_payloads(tmp_path) -> None:
    raw = tmp_path / "data" / "raw" / "formex"
    raw.mkdir(parents=True)
    frame = (
        _crosscuts()
        .rename(
            columns={
                "acquisition_type": "Acquisition Type",
                "acquisition_id": "Acquisition ID",
                "acquisition_name": "Acquisition Name",
                "acquisition_start_date": "Acquisition Start Date",
                "acquisition_end_date": "Acquisition End Date",
                "program_request": "Program Request",
                "program_priority": "Program Priority",
                "doe_priority_tier": "DOE Priority Tier",
                "formulated_measure": "Formulated Measure",
            }
        )
        .drop(columns=["fiscal_year_number", "funding_level_normalized", "source_row_id"])
        .assign(
            **{
                "Submission Type": ["Federal Crosscuts"] * 3,
                "Program Int. Area": ["Pit Production"] * 3,
                "Fiscal Year": ["FY2029", "FY2028", "FY2028"],
                "Funding Levels": ["Baseline", "ROT", "UFR"],
                "Scenario": ["Scenario A"] * 3,
                "Site - PlanEX": ["LANL", "SRS-SRNS", "LANL"],
                "NNSA Appropriation": ["Weapons Activities"] * 3,
                "STAT L3 (Programming)": ["L3"] * 3,
                "STAT L4 (Programming)": ["L4"] * 3,
                "STAT L5 (Programming)": ["L5"] * 3,
                "Construction or Operating": ["Operating"] * 3,
                "Sub Office Number": ["NA-19"] * 3,
                "Site Grouping": ["Federal"] * 3,
                "Site Name": ["Site"] * 3,
                "BNR Code": ["BNR"] * 3,
                "Program Value": ["Program"] * 3,
                "Scope Description": ["Scope"] * 3,
                "Process Imp. Area": ["None"] * 3,
                "Account Integrator Priority": [0] * 3,
                "Account Integrator Decision": [None] * 3,
                "WBS": ["1.1"] * 3,
                "WBS Name": ["Work"] * 3,
                "WBS Level": [1] * 3,
            }
        )
    )
    site_rows = frame.copy().assign(**{"Submission Type": ["Federal Site Splits"] * 3})
    pd.concat([frame, site_rows], ignore_index=True).to_csv(
        raw / "formex.csv", sep="\t", encoding="utf-16", index=False
    )
    config = tmp_path / "config"
    config.mkdir()
    (config / "settings.yaml").write_text(
        "project:\n  name: test\n  default_integration_area: Pit Production\n  default_scenario: Scenario A\npaths: {}\nformex: {}\nasksage: {}\n",
        encoding="utf-8",
    )
    manifest = build_dashboard_02_payloads(tmp_path)
    output = (
        tmp_path / "data" / "curated" / "dashboard_payloads" / "dashboard_02_acquisition_schedule"
    )
    assert manifest["dashboard_id"] == "dashboard_02_acquisition_schedule"
    assert (
        json.loads((output / "q1_acquisition_type_by_funding_level.json").read_text())[
            "question_id"
        ]
        == "q1"
    )
    assert (output / "manifest.json").exists()
