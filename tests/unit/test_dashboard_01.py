"""Unit tests for deterministic Dashboard 1 payload generation."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from cepe_fynsp.dashboards.dashboard_01_pit_production import (
    CROSSCUTS_SUBMISSION_TYPE,
    SITE_SPLITS_SUBMISSION_TYPE,
    aggregate_q1_funding_by_year_level,
    build_dashboard_01_payloads,
    calculate_q6_reconciliation,
    filter_pit_production,
    find_formex_csv,
    normalize_funding_level,
    prepare_formex_dataframe,
)


def _synthetic_formex() -> pd.DataFrame:
    """Return a minimal FORMEX-shaped frame with both dashboard submission layers."""
    return pd.DataFrame(
        {
            "Submission Type": [
                " federal crosscuts ",
                "Federal Crosscuts",
                "Federal Site Splits",
                "Federal Site Splits",
                "Federal Crosscuts",
            ],
            "Program Int. Area": [
                " pit   production ",
                "Pit Production",
                "PIT PRODUCTION",
                "Pit Production",
                "Other Area",
            ],
            "Fiscal Year": ["FY2028", "FY2029", "FY2028", "FY2029", "FY2028"],
            "Funding Levels": ["baseline", "ROT", "Baseline", "rot", "UFR"],
            "Formulated Measure": ["100", "25", "100", "25", "999"],
            "Scenario": ["Scenario A"] * 5,
            "Sub Office Number": ["NA-19", "NA-90", "NA-19", "NA-90", "NA-00"],
            "Site - PlanEX": ["LANL", "SRS-SRNS", "LANL", "SRS-SRNS", "Other"],
            "Program Request": ["Baseline work", "Growth request", "Baseline work", "Growth request", "Other"],
            "Scope Description": ["Scope"] * 5,
            "WBS": ["1.1"] * 5,
            "BNR Code": ["BNR"] * 5,
            "DOE Priority Tier": [0, 2, 0, 2, 1],
            "Account Integrator Priority": [0] * 5,
            "Account Integrator Decision": [None] * 5,
            "Acquisition Type": [None] * 5,
            "Acquisition ID": [None] * 5,
            "Acquisition Name": [None] * 5,
            "Acquisition Start Date": [None] * 5,
            "Acquisition End Date": [None] * 5,
        }
    )


def _prepared_layers() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return prepared synthetic Crosscuts and Site Splits frames."""
    prepared = prepare_formex_dataframe(_synthetic_formex())
    crosscuts = filter_pit_production(
        prepared, CROSSCUTS_SUBMISSION_TYPE, scenario="Scenario A"
    )
    site_splits = filter_pit_production(
        prepared, SITE_SPLITS_SUBMISSION_TYPE, scenario="Scenario A"
    )
    return crosscuts, site_splits


def test_normalize_funding_level() -> None:
    """Funding-level aliases normalize into dashboard categories."""
    assert normalize_funding_level(" baseline ") == "Baseline"
    assert normalize_funding_level("Request Over Target") == "ROT"
    assert normalize_funding_level("unfunded requirement") == "UFR"
    assert normalize_funding_level("  ") == "Unspecified"


def test_filter_pit_production_normalizes_text_and_submission_layer() -> None:
    """Pit filtering ignores capitalization/whitespace but respects the source layer."""
    crosscuts, site_splits = _prepared_layers()
    assert len(crosscuts) == 2
    assert len(site_splits) == 2
    assert set(crosscuts["submission_type"]) == {CROSSCUTS_SUBMISSION_TYPE}
    assert set(site_splits["submission_type"]) == {SITE_SPLITS_SUBMISSION_TYPE}


def test_q1_aggregation_uses_fiscal_year_and_funding_level() -> None:
    """Q1 aggregation produces raw and display-ready values from a small frame."""
    crosscuts, _ = _prepared_layers()
    data = aggregate_q1_funding_by_year_level(crosscuts)
    assert data == [
        {
            "fiscal_year": "FY2028",
            "fiscal_year_number": 2028,
            "funding_level": "Baseline",
            "amount": 100.0,
            "amount_display": "$100",
        },
        {
            "fiscal_year": "FY2029",
            "fiscal_year_number": 2029,
            "funding_level": "ROT",
            "amount": 25.0,
            "amount_display": "$25",
        },
    ]


def test_q6_reconciliation_calculates_site_splits_minus_crosscuts() -> None:
    """Q6 reconciliation keeps funding levels separate and reports the signed variance."""
    crosscuts = pd.DataFrame(
        {
            "funding_level_normalized": ["Baseline", "ROT"],
            "formulated_measure": [100.0, 20.0],
        }
    )
    site_splits = pd.DataFrame(
        {
            "funding_level_normalized": ["Baseline", "ROT"],
            "formulated_measure": [90.0, 35.0],
        }
    )
    data, summary = calculate_q6_reconciliation(crosscuts, site_splits)
    assert data[0]["variance_amount"] == -10.0
    assert data[1]["variance_amount"] == 15.0
    assert summary["variance_amount"] == 5.0


def test_build_dashboard_payloads_writes_static_artifacts(tmp_path) -> None:
    """The complete build writes payloads, compact RAG context, and the graph export."""
    raw_dir = tmp_path / "data" / "raw" / "formex"
    raw_dir.mkdir(parents=True)
    _synthetic_formex().to_csv(raw_dir / "formex.csv", sep="\t", encoding="utf-16", index=False)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "settings.yaml").write_text(
        """project:
  name: test-dashboard
  default_integration_area: Pit Production
  default_scenario: Scenario A
paths: {}
formex: {}
asksage: {}
""",
        encoding="utf-8",
    )

    manifest = build_dashboard_01_payloads(tmp_path)

    payload_dir = tmp_path / "data" / "curated" / "dashboard_payloads" / "dashboard_01_pit_production"
    q1_payload = json.loads((payload_dir / "q1_funding_by_year_level.json").read_text(encoding="utf-8"))
    assert manifest["dashboard_id"] == "dashboard_01_pit_production"
    assert (payload_dir / "manifest.json").exists()
    assert q1_payload["traceability"]["chart_id"] == "dashboard_01_pit_production_q1"
    assert q1_payload["traceability"]["source_submission_type"] == "Federal Crosscuts"
    assert (tmp_path / "data" / "curated" / "rag_chunks" / "dashboard_01_pit_production" / "dashboard_01_context.jsonl").exists()
    graph = json.loads(
        (tmp_path / "data" / "ontology" / "dashboard_01_pit_production_graph.json").read_text(
            encoding="utf-8"
        )
    )
    assert {node["node_type"] for node in graph["nodes"]} >= {
        "Dashboard",
        "Question",
        "Chart",
        "Metric",
        "SourceFile",
        "SubmissionType",
        "IntegrationArea",
        "FundingLevel",
        "FiscalYear",
        "Organization",
        "Site",
        "ProgramRequest",
        "Finding",
    }


def test_build_dashboard_payloads_fails_clearly_without_formex(tmp_path) -> None:
    """A missing FORMEX input is reported before attempting any artifact write."""
    (tmp_path / "data" / "raw" / "formex").mkdir(parents=True)
    with pytest.raises(FileNotFoundError, match="No FORMEX CSV"):
        build_dashboard_01_payloads(tmp_path)


def test_find_formex_csv_fails_clearly_when_multiple_inputs_exist(tmp_path) -> None:
    """Ambiguous FORMEX input must be resolved rather than selecting an arbitrary file."""
    formex_dir = tmp_path / "data" / "raw" / "formex"
    formex_dir.mkdir(parents=True)
    (formex_dir / "first.csv").touch()
    (formex_dir / "second.csv").touch()
    with pytest.raises(ValueError, match="Multiple FORMEX CSV candidates"):
        find_formex_csv(tmp_path)
