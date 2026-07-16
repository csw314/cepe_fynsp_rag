"""Dashboard payload builders."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class ChartPayload:
    """Serializable chart payload with traceability metadata."""

    dashboard_id: str
    question_id: str
    natural_language_question: str
    chart_type: str
    metric_definition: str
    filters: dict[str, Any]
    data: list[dict[str, Any]]
    source_dataset: str
    source_submission_type: str
    lineage: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def funding_by_year_and_level(df: pd.DataFrame, integration_area: str) -> ChartPayload:
    """Build Dashboard 1 question 1 payload."""
    filtered = df[
        (df["submission_type"] == "Federal Crosscuts")
        & (df["program_int_area"].astype("string").str.upper() == integration_area.upper())
    ].copy()
    grouped = (
        filtered.groupby(["fiscal_year", "funding_levels"], dropna=False)["formulated_measure"]
        .sum()
        .reset_index()
        .sort_values(["fiscal_year", "funding_levels"])
    )
    return ChartPayload(
        dashboard_id="01_overview",
        question_id="q1",
        natural_language_question="How much funding is programmed for Pit Production by fiscal year and funding level?",
        chart_type="stacked_bar",
        metric_definition="Sum of FORMEX Formulated Measure by fiscal year and funding level, filtered to Federal Crosscuts and Pit Production.",
        filters={"submission_type": "Federal Crosscuts", "program_int_area": integration_area},
        data=grouped.to_dict(orient="records"),
        source_dataset="FORMEX",
        source_submission_type="Federal Crosscuts",
        lineage={
            "source_row_ids": filtered["source_row_id"].head(1000).tolist()
            if "source_row_id" in filtered
            else [],
            "lineage_truncated": len(filtered) > 1000,
        },
    )
