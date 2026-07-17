"""Executable contract, stable lineage, and ontology integrity regressions."""

from __future__ import annotations

import pandas as pd
import pytest

from cepe_fynsp.etl.contracts import (
    ContractError,
    DataContract,
    SourceFormat,
    validate_dataframe,
    validate_headers,
)
from cepe_fynsp.etl.normalize import add_source_lineage, normalize_columns
from cepe_fynsp.ontology.build_graph import stable_node_id, validate_graph_references


def _formex_contract() -> DataContract:
    return DataContract(
        dataset="formex",
        contract_version="test",
        raw_file="synthetic.csv",
        format=SourceFormat(encoding="utf-8", separator="comma"),
        required_columns_raw=("Scenario", "Submission Type", "Fiscal Year", "Funding Levels"),
        canonical_amount_column="amount",
        allowed_fiscal_years=("FY2028",),
        allowed_submission_types=("Federal Crosscuts",),
        allowed_funding_levels=("BASELINE", "ROT", "UFR"),
    )


def test_duplicate_normalized_columns_fail() -> None:
    frame = pd.DataFrame([[1, 2]], columns=["Site Name", "site-name"])
    with pytest.raises(ValueError, match="Duplicate normalized"):
        normalize_columns(frame)


def test_missing_required_column_fails_contract() -> None:
    with pytest.raises(ContractError, match="missing required columns"):
        validate_headers(["Scenario"], _formex_contract())


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("submission_type", "Federal Site Splits", "Invalid submission_type"),
        ("fiscal_year", "FY2099", "Invalid fiscal_year"),
        ("funding_levels", "MYSTERY", "Invalid funding_levels"),
    ],
)
def test_invalid_controlled_domains_fail(column: str, value: str, message: str) -> None:
    frame = pd.DataFrame(
        [
            {
                "scenario": "Synthetic",
                "submission_type": "Federal Crosscuts",
                "fiscal_year": "FY2028",
                "funding_levels": "BASELINE",
            }
        ]
    )
    frame.loc[0, column] = value
    with pytest.raises(ContractError, match=message):
        validate_dataframe(frame, _formex_contract())


def test_all_blank_scenario_fails_contract() -> None:
    frame = pd.DataFrame(
        [
            {
                "scenario": None,
                "submission_type": "Federal Crosscuts",
                "fiscal_year": "FY2028",
                "funding_levels": "BASELINE",
            }
        ]
    )
    with pytest.raises(ContractError, match="scenario is blank"):
        validate_dataframe(frame, _formex_contract())


def test_row_reordering_preserves_content_hash_and_record_id_sets() -> None:
    frame = pd.DataFrame({"business": ["A", "B"], "amount": [1, 2]})
    original = add_source_lineage(frame, "FORMEX", source_file_identity="synthetic.csv")
    reordered = add_source_lineage(
        frame.iloc[::-1].reset_index(drop=True), "FORMEX", source_file_identity="synthetic.csv"
    )
    assert set(original["source_content_hash"]) == set(reordered["source_content_hash"])
    assert set(original["source_record_id"]) == set(reordered["source_record_id"])


def test_duplicate_records_have_auditable_unique_occurrences() -> None:
    frame = pd.DataFrame({"business": ["A", "A"], "amount": [1, 1]})
    lineage = add_source_lineage(frame, "FORMEX", source_file_identity="synthetic.csv")
    assert set(lineage["source_duplicate_count"]) == {2}
    assert set(lineage["source_duplicate_occurrence"]) == {1, 2}
    assert lineage["source_record_id"].is_unique


def test_ontology_slug_collision_values_keep_distinct_ids() -> None:
    assert stable_node_id("Site", "A/B") != stable_node_id("Site", "A B")


def test_graph_validator_detects_dangling_edges() -> None:
    import networkx as nx

    graph = nx.MultiDiGraph()
    graph.add_node("present")
    graph.add_edge("present", "created-by-networkx")
    graph.remove_node("created-by-networkx")
    # NetworkX removes incident edges with a node, so inject a deliberately invalid edge view.
    graph._succ["present"]["missing"] = {0: {}}  # type: ignore[attr-defined]
    with pytest.raises(ValueError, match="dangling"):
        validate_graph_references(graph)
