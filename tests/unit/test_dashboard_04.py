"""Unit tests for Dashboard 4 challenge-board calculations."""

from __future__ import annotations

import pandas as pd

from cepe_fynsp.dashboards.dashboard_04_priority_challenge import (
    calculate_priority_uniqueness,
    calculate_traceability_scores,
    classify_request_intent,
    rank_rot_ufr_requests,
)


def _crosscuts() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "funding_level_normalized": ["ROT", "UFR", "Baseline", "ROT"],
            "program_request": ["Request A", "Request B", "Base", "Request C"],
            "program_priority": [1, 1, 0, 1],
            "doe_priority_tier": [1, 2, 0, 1],
            "formulated_measure": [100.0, 50.0, 10.0, 25.0],
            "scope_description": [
                "Build construction",
                "Restore operations",
                "Baseline scope",
                "Delay modernization",
            ],
            "wbs": ["W", "W", "W", ""],
            "bnr_code": ["B", "B", "B", ""],
            "site_planex": ["LANL", "LANL", "LANL", ""],
            "fiscal_year": ["FY2028"] * 4,
            "funding_levels": ["ROT", "UFR", "Baseline", "ROT"],
            "acquisition_id": ["A", "", "", "C"],
            "acquisition_name": ["Alpha", "", "", "Charlie"],
            "acquisition_type": ["LI TEC", "", "", "LI OPC"],
        }
    )


def test_rot_ufr_request_ranking_and_tier1_source_rows() -> None:
    data = rank_rot_ufr_requests(_crosscuts())
    assert [row["program_request"] for row in data] == ["Request A", "Request B", "Request C"]
    assert data[0]["cumulative_share"] > 0


def test_priority_uniqueness_detects_reused_priorities() -> None:
    data = calculate_priority_uniqueness(_crosscuts(), materiality_threshold=100.0)
    one = next(row for row in data if row["program_priority"] == "1")
    assert one["priority_reused"] is True
    assert one["material_duplicate_review_trigger"] is True


def test_deterministic_request_intent_classification() -> None:
    assert classify_request_intent("Offset program", "", 5) == "offset"
    assert classify_request_intent("", "Restoration of work", 5) == "restoration"
    assert classify_request_intent("", "Delayed construction", 5) == "delay"
    assert classify_request_intent("", "Sustain operations", 5) == "sustainment"
    assert classify_request_intent("Unspecified", "", -1) == "offset"


def test_traceability_score_calculation_exposes_components() -> None:
    data = {row["program_request"]: row for row in calculate_traceability_scores(_crosscuts())}
    assert data["Request A"]["traceability_score"] > data["Request C"]["traceability_score"]
    assert "scope_description" in data["Request A"]["component_coverage"]
