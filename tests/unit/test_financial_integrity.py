"""Regression tests for monetary parsing and completeness-preserving aggregates."""

from __future__ import annotations

import pandas as pd

from cepe_fynsp.dashboards.dashboard_01_pit_production import calculate_q6_reconciliation
from cepe_fynsp.etl.financial import aggregate_financial, parse_amount_series


def _aggregate(values: list[object]) -> pd.Series:
    parsed = parse_amount_series(pd.Series(values))
    return aggregate_financial(parsed).iloc[0]


def test_explicit_zero_is_valid_not_blank() -> None:
    row = _aggregate(["0"])
    assert row["amount"] == 0
    assert row["valid_amount_row_count"] == 1
    assert row["aggregate_status"] == "complete"


def test_blank_is_unavailable_not_zero() -> None:
    row = _aggregate([""])
    assert pd.isna(row["amount"])
    assert row["blank_amount_row_count"] == 1
    assert row["aggregate_status"] == "unavailable"


def test_invalid_amount_is_quarantined_and_reported() -> None:
    parsed = parse_amount_series(pd.Series(["not-money"]))
    assert parsed.loc[0, "amount_parse_status"] == "invalid"
    assert pd.isna(parsed.loc[0, "amount_normalized"])
    assert parsed.loc[0, "amount_parse_error"] == "unparseable_amount"


def test_null_only_aggregate_remains_null() -> None:
    row = _aggregate([None, "null"])
    assert pd.isna(row["amount"])
    assert row["blank_amount_row_count"] == 2
    assert row["completeness_percentage"] == 0


def test_partial_aggregate_preserves_value_and_counts() -> None:
    row = _aggregate(["100", "", "bad"])
    assert row["amount"] == 100
    assert row["valid_amount_row_count"] == 1
    assert row["blank_amount_row_count"] == 1
    assert row["invalid_amount_row_count"] == 1
    assert row["aggregate_status"] == "partial"


def test_negative_and_offset_heavy_portfolio_are_not_silently_removed() -> None:
    row = _aggregate(["100", "(250)", "-25"])
    assert row["amount"] == -175
    assert row["valid_amount_row_count"] == 3


def test_grouped_mixed_funding_levels_keep_unknown_category() -> None:
    parsed = parse_amount_series(pd.Series(["10", "20", "30"]))
    frame = parsed.assign(funding_level=["Baseline", "ROT", "Unknown source code"])
    grouped = aggregate_financial(frame, ["funding_level"])
    assert set(grouped["funding_level"]) == {"Baseline", "ROT", "Unknown source code"}
    assert grouped["amount"].sum() == 60


def test_reconciliation_missing_side_is_unavailable_not_zero() -> None:
    crosscuts = pd.DataFrame(
        {"funding_level_normalized": ["Baseline"], "formulated_measure": [100.0]}
    )
    site_splits = pd.DataFrame({"funding_level_normalized": ["ROT"], "formulated_measure": [20.0]})
    rows, _ = calculate_q6_reconciliation(crosscuts, site_splits)
    baseline = next(row for row in rows if row["funding_level"] == "Baseline")
    assert baseline["federal_site_splits_amount"] is None
    assert baseline["variance_amount"] is None
    assert baseline["aggregate_status"] == "partial"
