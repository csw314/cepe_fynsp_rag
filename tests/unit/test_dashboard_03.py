"""Unit tests for Dashboard 3 site calculations."""

from __future__ import annotations

import pandas as pd

from cepe_fynsp.dashboards.dashboard_03_site_capacity import (
    aggregate_site_totals,
    aggregate_suboffice_site_dependencies,
    calculate_site_above_baseline_dependency,
    calculate_site_yoy_surges,
)


def _sites() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "site_planex": ["LANL", "LANL", "SRS", "SRS", "LANL"],
            "fiscal_year_normalized": ["FY2028", "FY2029", "FY2028", "FY2029", "FY2030"],
            "fiscal_year_number": [2028, 2029, 2028, 2029, 2030],
            "funding_level_normalized": ["Baseline", "ROT", "UFR", "Baseline", "Baseline"],
            "sub_office_number": ["NA-19", "NA-90", "NA-19", "NA-90", "NA-19"],
            "formulated_measure": [100.0, 50.0, 40.0, 40.0, 0.0],
        }
    )


def test_site_total_aggregation_and_share() -> None:
    data = aggregate_site_totals(_sites())
    assert data[0]["site"] == "LANL"
    assert data[0]["amount"] == 150.0
    assert (
        round(sum(row["share_of_total"] for row in data if row["share_of_total"] is not None), 8)
        == 1.0
    )


def test_above_baseline_dependency_calculation() -> None:
    data = {row["site"]: row for row in calculate_site_above_baseline_dependency(_sites())}
    assert data["LANL"]["above_baseline"] == 50.0
    assert data["LANL"]["above_baseline_share"] == 50.0 / 150.0


def test_yoy_surge_handles_zero_prior_as_new_funding() -> None:
    sites = pd.DataFrame(
        {
            "site_planex": ["LANL", "LANL"],
            "fiscal_year_normalized": ["FY2028", "FY2029"],
            "fiscal_year_number": [2028, 2029],
            "formulated_measure": [0.0, 75.0],
        }
    )
    data = calculate_site_yoy_surges(sites)
    assert data[1]["change_status"] == "new_funding"
    assert data[1]["percent_change"] is None


def test_suboffice_site_dependency_grouping() -> None:
    data = aggregate_suboffice_site_dependencies(_sites())
    lanl = [row for row in data if row["site"] == "LANL"]
    assert {row["organization"] for row in lanl} == {"NA-19", "NA-90"}
    assert {row["distinct_suboffices_at_site"] for row in lanl} == {2}
