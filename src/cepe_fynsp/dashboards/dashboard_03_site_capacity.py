"""Build Dashboard 3 site capacity and integration burden artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from cepe_fynsp.dashboards.dashboard_support import (
    AMOUNT_COLUMN,
    COMMON_LIMITATIONS,
    SITE_SPLITS_SUBMISSION_TYPE,
    blank_mask,
    display_value,
    format_dollars,
    load_pit_production_layers,
    make_payload,
    source_row_lineage,
    write_dashboard_artifacts,
)

DASHBOARD_ID = "dashboard_03_site_capacity"
DASHBOARD_TITLE = "Site Capacity and Integration Burden Dashboard"
YOY_SURGE_THRESHOLD = 0.25

QUESTION_TEXT = {
    "q1": "Which sites receive the most Pit Production funding over FY2028-FY2032?",
    "q2": "How does Pit Production funding change by site and year?",
    "q3": "Which sites depend most on above-baseline funding?",
    "q4": "Which organizations are funding the same site, creating integration dependencies?",
    "q5": "Are there site-level funding cliffs or surges that should trigger executability review?",
    "q6": "Which site rows lack enough descriptive detail to support a thorough review?",
}

PAYLOAD_FILES = {
    "q1": "q1_site_totals.json",
    "q2": "q2_site_year_heatmap.json",
    "q3": "q3_site_above_baseline_dependency.json",
    "q4": "q4_suboffice_site_dependencies.json",
    "q5": "q5_site_yoy_surges.json",
    "q6": "q6_site_scope_quality_findings.json",
}


def _site_column(df: pd.DataFrame) -> str | None:
    """Return the most specific available Site Splits site field."""
    if "site_planex" in df.columns:
        return "site_planex"
    if "site_name" in df.columns:
        return "site_name"
    return None


def _site_frame(site_splits: pd.DataFrame) -> pd.DataFrame:
    """Add one explicit site display field to a Site Splits frame."""
    column = _site_column(site_splits)
    if column is None:
        return pd.DataFrame()
    working = site_splits.copy()
    working["site"] = working[column].map(lambda value: display_value(value, "Unspecified site"))
    return working


def aggregate_site_totals(site_splits: pd.DataFrame) -> list[dict[str, Any]]:
    """Aggregate, rank, and calculate shares for Pit Production sites."""
    working = _site_frame(site_splits)
    if working.empty and _site_column(site_splits) is None:
        return [
            {"status": "not_evaluated", "reason": "Missing FORMEX site_planex/site_name column."}
        ]
    grouped = working.groupby("site", dropna=False)[AMOUNT_COLUMN].sum().reset_index(name="amount")
    grouped = grouped.sort_values("amount", ascending=False)
    total = float(grouped["amount"].sum())
    return [
        {
            "rank": rank,
            "site": str(row.site),
            "amount": float(row.amount),
            "amount_display": format_dollars(float(row.amount)),
            "share_of_total": float(row.amount) / total if total else None,
        }
        for rank, row in enumerate(grouped.itertuples(index=False), start=1)
    ]


def aggregate_site_year_heatmap(site_splits: pd.DataFrame) -> list[dict[str, Any]]:
    """Aggregate Site Splits dollars to site/fiscal-year heatmap cells."""
    working = _site_frame(site_splits)
    if working.empty and _site_column(site_splits) is None:
        return [
            {"status": "not_evaluated", "reason": "Missing FORMEX site_planex/site_name column."}
        ]
    grouped = (
        working.groupby(["site", "fiscal_year_normalized", "fiscal_year_number"], dropna=False)[
            AMOUNT_COLUMN
        ]
        .sum()
        .reset_index(name="amount")
        .sort_values(["site", "fiscal_year_number"])
    )
    return [
        {
            "site": str(row.site),
            "fiscal_year": str(row.fiscal_year_normalized),
            "fiscal_year_number": int(row.fiscal_year_number)
            if pd.notna(row.fiscal_year_number)
            else None,
            "amount": float(row.amount),
            "amount_display": format_dollars(float(row.amount)),
        }
        for row in grouped.itertuples(index=False)
    ]


def calculate_site_above_baseline_dependency(site_splits: pd.DataFrame) -> list[dict[str, Any]]:
    """Calculate Baseline, ROT, UFR, and above-baseline dependence by site."""
    working = _site_frame(site_splits)
    if working.empty and _site_column(site_splits) is None:
        return [
            {"status": "not_evaluated", "reason": "Missing FORMEX site_planex/site_name column."}
        ]
    grouped = (
        working.groupby(["site", "funding_level_normalized"], dropna=False)[AMOUNT_COLUMN]
        .sum()
        .reset_index(name="amount")
    )
    by_site: dict[str, dict[str, float]] = {}
    for row in grouped.itertuples(index=False):
        by_site.setdefault(str(row.site), {})[str(row.funding_level_normalized)] = float(row.amount)
    records = []
    for site, amounts in by_site.items():
        baseline = amounts.get("Baseline", 0.0)
        rot = amounts.get("ROT", 0.0)
        ufr = amounts.get("UFR", 0.0)
        total = sum(amounts.values())
        above = rot + ufr
        records.append(
            {
                "site": str(site),
                "baseline": baseline,
                "baseline_display": format_dollars(baseline),
                "rot": rot,
                "rot_display": format_dollars(rot),
                "ufr": ufr,
                "ufr_display": format_dollars(ufr),
                "above_baseline": above,
                "above_baseline_display": format_dollars(above),
                "total": total,
                "total_display": format_dollars(total),
                "above_baseline_share": above / total if total else None,
            }
        )
    return sorted(records, key=lambda row: row["above_baseline_share"] or 0.0, reverse=True)


def aggregate_suboffice_site_dependencies(site_splits: pd.DataFrame) -> list[dict[str, Any]]:
    """Show which sub-offices fund each site without constructing an artificial join."""
    working = _site_frame(site_splits)
    if working.empty and _site_column(site_splits) is None:
        return [
            {"status": "not_evaluated", "reason": "Missing FORMEX site_planex/site_name column."}
        ]
    if "sub_office_number" not in working.columns:
        return [{"status": "not_evaluated", "reason": "Missing FORMEX sub_office_number column."}]
    working["organization"] = working["sub_office_number"].map(
        lambda value: display_value(value, "Unspecified organization")
    )
    site_counts = working.groupby("site")["organization"].nunique()
    grouped = (
        working.groupby(["organization", "site", "funding_level_normalized"], dropna=False)[
            AMOUNT_COLUMN
        ]
        .sum()
        .reset_index(name="amount")
        .sort_values("amount", ascending=False)
    )
    return [
        {
            "organization": str(row.organization),
            "site": str(row.site),
            "funding_level": str(row.funding_level_normalized),
            "amount": float(row.amount),
            "amount_display": format_dollars(float(row.amount)),
            "distinct_suboffices_at_site": int(site_counts[row.site]),
        }
        for row in grouped.itertuples(index=False)
    ]


def calculate_site_yoy_surges(
    site_splits: pd.DataFrame, threshold: float = YOY_SURGE_THRESHOLD
) -> list[dict[str, Any]]:
    """Calculate site year-over-year changes and handle zero prior funding explicitly."""
    cells = aggregate_site_year_heatmap(site_splits)
    if cells and cells[0].get("status") == "not_evaluated":
        return cells
    working = pd.DataFrame(cells)
    records: list[dict[str, Any]] = []
    for site, group in working.groupby("site", dropna=False):
        group = group.sort_values("fiscal_year_number")
        prior: float | None = None
        for row in group.itertuples(index=False):
            amount = float(row.amount)
            if prior is None:
                percent = None
                status = "first_available_year"
                dollar_change = None
            elif prior == 0 and amount != 0:
                percent = None
                status = "new_funding"
                dollar_change = amount
            elif prior == 0:
                percent = None
                status = "no_change_from_zero"
                dollar_change = 0.0
            else:
                dollar_change = amount - prior
                percent = dollar_change / abs(prior)
                status = "surge_or_cliff" if abs(percent) >= threshold else "within_threshold"
            records.append(
                {
                    "site": str(site),
                    "fiscal_year": str(row.fiscal_year),
                    "amount": amount,
                    "amount_display": format_dollars(amount),
                    "prior_year_amount": prior,
                    "dollar_change": dollar_change,
                    "dollar_change_display": format_dollars(dollar_change)
                    if dollar_change is not None
                    else "Not available",
                    "percent_change": percent,
                    "change_status": status,
                    "review_flag": status in {"new_funding", "surge_or_cliff"},
                }
            )
            prior = amount
    return records


def _generic_scope_mask(series: pd.Series) -> pd.Series:
    """Flag blank and transparent generic scope descriptions deterministically."""
    text = series.astype("string").str.strip().str.casefold()
    generic_terms = {
        "support",
        "program support",
        "other",
        "tbd",
        "to be determined",
        "n/a",
        "none",
    }
    return blank_mask(series) | text.isin(generic_terms) | (text.str.len() < 12)


def site_scope_quality_findings(site_splits: pd.DataFrame) -> list[dict[str, Any]]:
    """Return deterministic site-review completeness findings with bounded lineage."""
    source = SITE_SPLITS_SUBMISSION_TYPE
    specifications = [
        ("SQ001", "Missing scope description", "scope_description", "missing"),
        ("SQ002", "Generic scope description", "scope_description", "generic"),
        ("SQ003", "Missing program request", "program_request", "missing"),
        ("SQ004", "Missing site", _site_column(site_splits), "missing"),
        ("SQ005", "Missing WBS traceability", "wbs", "missing"),
        ("SQ006", "Missing BNR traceability", "bnr_code", "missing"),
    ]
    findings = []
    for rule_id, title, column, check in specifications:
        if column is None or column not in site_splits.columns:
            findings.append(
                {
                    "rule_id": rule_id,
                    "finding_id": rule_id,
                    "title": title,
                    "status": "not_evaluated",
                    "severity": "not_evaluated",
                    "row_count": 0,
                    "affected_dollars": None,
                    "affected_dollars_display": "Not available",
                    "source_submission_type": source,
                    "details": f"Not evaluated because FORMEX column '{column or 'site_planex/site_name'}' is unavailable.",
                    "source_row_id_sample": [],
                }
            )
            continue
        if check == "generic":
            mask = _generic_scope_mask(site_splits[column]) & ~blank_mask(site_splits[column])
        else:
            mask = blank_mask(site_splits[column])
        amount = float(site_splits.loc[mask, AMOUNT_COLUMN].sum())
        findings.append(
            {
                "rule_id": rule_id,
                "finding_id": rule_id,
                "title": title,
                "status": "evaluated",
                "severity": "medium",
                "row_count": int(mask.sum()),
                "affected_dollars": amount,
                "affected_dollars_display": format_dollars(amount),
                "source_submission_type": source,
                "details": "Deterministic scope-quality review trigger; future RAG classification may refine generic-scope labels.",
                "source_row_id_sample": site_splits.loc[mask, "source_row_id"]
                .astype(str)
                .head(100)
                .tolist()
                if "source_row_id" in site_splits.columns
                else [],
            }
        )
    return findings


def _leader_summary(data: list[dict[str, Any]], label: str, value: str = "amount") -> str:
    """Create a plain-language summary without adding unsupported interpretation."""
    usable = [row for row in data if isinstance(row.get(value), (int, float))]
    if not usable:
        return "No rows were available for this site analysis."
    leader = max(usable, key=lambda row: float(row[value]))
    return f"The largest displayed {label} is {leader.get('site', 'unspecified')} at {format_dollars(float(leader[value]))}."


def build_dashboard_03_payloads(project_root: Path | None = None) -> dict[str, Any]:
    """Build all Dashboard 3 JSON payloads, RAG context, and ontology graph."""
    root, _, site_splits, metadata = load_pit_production_layers(project_root)
    row_filter = {**metadata["base_filter"], "submission_type": SITE_SPLITS_SUBMISSION_TYPE}
    q1_data = aggregate_site_totals(site_splits)
    q2_data = aggregate_site_year_heatmap(site_splits)
    q3_data = calculate_site_above_baseline_dependency(site_splits)
    q4_data = aggregate_suboffice_site_dependencies(site_splits)
    q5_data = calculate_site_yoy_surges(site_splits)
    q6_data = site_scope_quality_findings(site_splits)
    limitations = COMMON_LIMITATIONS + [
        "Site totals are Federal Site Splits for distribution analysis and should not replace Federal Crosscuts portfolio totals.",
        "Funding surges and cliffs are executability review triggers, not independent capacity conclusions.",
        f"The year-over-year review threshold is {YOY_SURGE_THRESHOLD:.0%} because no configured threshold is available.",
    ]
    payloads = {
        "q1": make_payload(
            dashboard_id=DASHBOARD_ID,
            dashboard_title=DASHBOARD_TITLE,
            question_id="q1",
            question_text=QUESTION_TEXT["q1"],
            chart_type="ranked_bar_table",
            chart_title="Pit Production funding by site",
            metric_definition="Sum of FORMEX Formulated Measure by Site in Federal Site Splits, with each site's share of the Site Splits total.",
            source_submission_type=SITE_SPLITS_SUBMISSION_TYPE,
            row_filter=row_filter,
            grouping_columns=["site"],
            value_column=AMOUNT_COLUMN,
            record_count=len(site_splits),
            data=q1_data,
            summary=_leader_summary(q1_data, "site"),
            limitations=limitations,
            lineage=source_row_lineage(site_splits),
            metric_cards=[
                {"label": "Sites represented", "value": len(q1_data), "display": str(len(q1_data))}
            ],
            metadata=metadata,
        ),
        "q2": make_payload(
            dashboard_id=DASHBOARD_ID,
            dashboard_title=DASHBOARD_TITLE,
            question_id="q2",
            question_text=QUESTION_TEXT["q2"],
            chart_type="site_year_heatmap_table",
            chart_title="Pit Production funding by site and fiscal year",
            metric_definition="Sum of FORMEX Formulated Measure by Site and fiscal year in Federal Site Splits.",
            source_submission_type=SITE_SPLITS_SUBMISSION_TYPE,
            row_filter=row_filter,
            grouping_columns=["site", "fiscal_year"],
            value_column=AMOUNT_COLUMN,
            record_count=len(site_splits),
            data=q2_data,
            summary=_leader_summary(q2_data, "site-year cell"),
            limitations=limitations,
            lineage=source_row_lineage(site_splits),
            metric_cards=[
                {"label": "Site-year cells", "value": len(q2_data), "display": str(len(q2_data))}
            ],
            metadata=metadata,
        ),
        "q3": make_payload(
            dashboard_id=DASHBOARD_ID,
            dashboard_title=DASHBOARD_TITLE,
            question_id="q3",
            question_text=QUESTION_TEXT["q3"],
            chart_type="above_baseline_dependency_table",
            chart_title="Site dependence on above-baseline funding",
            metric_definition="Baseline, ROT, UFR, total funding, and above-baseline share by Site from Federal Site Splits.",
            source_submission_type=SITE_SPLITS_SUBMISSION_TYPE,
            row_filter=row_filter,
            grouping_columns=["site", "funding_level"],
            value_column=AMOUNT_COLUMN,
            record_count=len(site_splits),
            data=q3_data,
            summary=_leader_summary(q3_data, "above-baseline total", "above_baseline"),
            limitations=limitations,
            lineage=source_row_lineage(site_splits),
            metric_cards=[
                {
                    "label": "Sites with above-baseline funding",
                    "value": sum((row.get("above_baseline") or 0) != 0 for row in q3_data),
                    "display": str(sum((row.get("above_baseline") or 0) != 0 for row in q3_data)),
                }
            ],
            metadata=metadata,
        ),
        "q4": make_payload(
            dashboard_id=DASHBOARD_ID,
            dashboard_title=DASHBOARD_TITLE,
            question_id="q4",
            question_text=QUESTION_TEXT["q4"],
            chart_type="suboffice_site_matrix",
            chart_title="Sub-office to site funding dependencies",
            metric_definition="Sum of FORMEX Formulated Measure by Sub Office Number, Site, and funding level in Federal Site Splits, with distinct sub-office counts per site.",
            source_submission_type=SITE_SPLITS_SUBMISSION_TYPE,
            row_filter=row_filter,
            grouping_columns=["organization", "site", "funding_level"],
            value_column=AMOUNT_COLUMN,
            record_count=len(site_splits),
            data=q4_data,
            summary=_leader_summary(q4_data, "organization-site dependency"),
            limitations=limitations,
            lineage=source_row_lineage(site_splits),
            metric_cards=[
                {
                    "label": "Organization-site relationships",
                    "value": len(q4_data),
                    "display": str(len(q4_data)),
                }
            ],
            metadata=metadata,
        ),
        "q5": make_payload(
            dashboard_id=DASHBOARD_ID,
            dashboard_title=DASHBOARD_TITLE,
            question_id="q5",
            question_text=QUESTION_TEXT["q5"],
            chart_type="yoy_change_table",
            chart_title="Site-level funding cliffs and surges",
            metric_definition="Year-over-year dollar and percent change by Site in Federal Site Splits; zero prior-year values use new funding/not meaningful percent states.",
            source_submission_type=SITE_SPLITS_SUBMISSION_TYPE,
            row_filter=row_filter,
            grouping_columns=["site", "fiscal_year"],
            value_column=AMOUNT_COLUMN,
            record_count=len(site_splits),
            data=q5_data,
            summary=f"{sum(row.get('review_flag', False) for row in q5_data)} site-year cells are surge, cliff, or new-funding review triggers.",
            limitations=limitations,
            lineage=source_row_lineage(site_splits),
            metric_cards=[
                {
                    "label": "Review-trigger cells",
                    "value": sum(row.get("review_flag", False) for row in q5_data),
                    "display": str(sum(row.get("review_flag", False) for row in q5_data)),
                }
            ],
            metadata=metadata,
        ),
        "q6": make_payload(
            dashboard_id=DASHBOARD_ID,
            dashboard_title=DASHBOARD_TITLE,
            question_id="q6",
            question_text=QUESTION_TEXT["q6"],
            chart_type="scope_quality_scorecard",
            chart_title="Site-level scope and traceability findings",
            metric_definition="Column-tolerant deterministic checks for missing/generic scope, program request, site, WBS, and BNR on Federal Site Splits.",
            source_submission_type=SITE_SPLITS_SUBMISSION_TYPE,
            row_filter=row_filter,
            grouping_columns=["rule_id"],
            value_column=f"{AMOUNT_COLUMN} affected dollars",
            record_count=len(site_splits),
            data=q6_data,
            summary=f"{sum(row.get('row_count', 0) for row in q6_data if row.get('status') == 'evaluated')} site rows are represented by deterministic completeness review triggers.",
            limitations=limitations,
            lineage=source_row_lineage(site_splits),
            metric_cards=[
                {
                    "label": "Evaluated finding categories",
                    "value": sum(row.get("status") == "evaluated" for row in q6_data),
                    "display": str(sum(row.get("status") == "evaluated" for row in q6_data)),
                }
            ],
            metadata=metadata,
        ),
    }
    return write_dashboard_artifacts(
        root=root,
        dashboard_id=DASHBOARD_ID,
        dashboard_title=DASHBOARD_TITLE,
        payloads=payloads,
        payload_files=PAYLOAD_FILES,
        metadata=metadata,
        limitations=limitations,
    )


if __name__ == "__main__":  # pragma: no cover
    print(build_dashboard_03_payloads())
