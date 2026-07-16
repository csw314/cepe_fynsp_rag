"""Build Dashboard 2 acquisition and schedule executability artifacts."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd

from cepe_fynsp.dashboards.dashboard_support import (
    AMOUNT_COLUMN,
    COMMON_LIMITATIONS,
    CROSSCUTS_SUBMISSION_TYPE,
    SITE_SPLITS_SUBMISSION_TYPE,
    blank_mask,
    display_value,
    format_dollars,
    load_pit_production_layers,
    make_payload,
    source_row_lineage,
    write_dashboard_artifacts,
)

DASHBOARD_ID = "dashboard_02_acquisition_schedule"
DASHBOARD_TITLE = "Acquisition and Schedule Executability Monitor"
MATERIALITY_THRESHOLD = 100_000_000.0

QUESTION_TEXT = {
    "q1": "How much Pit Production funding is tied to construction, MIEs, major modernization, or no acquisition tag?",
    "q2": "Which acquisition lines have the largest programmed values?",
    "q3": "Do acquisition start and end dates support the funding profile?",
    "q4": "Which acquisition rows have missing, classified, or suspicious dates?",
    "q5": "Where are LI TEC and LI OPC dollars concentrated by year and site?",
    "q6": "Which above-baseline acquisition requests are high-dollar and high-priority?",
}

PAYLOAD_FILES = {
    "q1": "q1_acquisition_type_by_funding_level.json",
    "q2": "q2_largest_acquisition_lines.json",
    "q3": "q3_acquisition_timeline_funding.json",
    "q4": "q4_acquisition_schedule_exceptions.json",
    "q5": "q5_li_tec_li_opc_site_year.json",
    "q6": "q6_above_baseline_acquisition_priority.json",
}


def _required_columns_available(df: pd.DataFrame, columns: Iterable[str]) -> list[str]:
    """Return the requested columns that are unavailable in a source frame."""
    return [column for column in columns if column not in df.columns]


def _acquisition_type_series(df: pd.DataFrame) -> pd.Series:
    """Return acquisition types with an explicit untagged category."""
    if "acquisition_type" not in df.columns:
        return pd.Series("Not evaluated", index=df.index, dtype="string")
    return df["acquisition_type"].map(lambda value: display_value(value, "No acquisition tag"))


def aggregate_acquisition_type_by_funding_level(crosscuts: pd.DataFrame) -> list[dict[str, Any]]:
    """Aggregate Crosscuts dollars by acquisition type and normalized funding level."""
    working = crosscuts.copy()
    working["acquisition_type_label"] = _acquisition_type_series(working)
    grouped = (
        working.groupby(["acquisition_type_label", "funding_level_normalized"], dropna=False)[AMOUNT_COLUMN]
        .sum()
        .reset_index(name="amount")
        .sort_values("amount", ascending=False)
    )
    return [
        {
            "acquisition_type": str(row.acquisition_type_label),
            "funding_level": str(row.funding_level_normalized),
            "amount": float(row.amount),
            "amount_display": format_dollars(float(row.amount)),
        }
        for row in grouped.itertuples(index=False)
    ]


def aggregate_largest_acquisition_lines(crosscuts: pd.DataFrame) -> list[dict[str, Any]]:
    """Aggregate and rank acquisition lines while retaining blank-ID rows visibly."""
    working = crosscuts.copy()
    for column, fallback in [
        ("acquisition_id", "No acquisition ID"),
        ("acquisition_name", "No acquisition name"),
        ("acquisition_type", "No acquisition tag"),
    ]:
        working[column] = (
            working[column].map(lambda value: display_value(value, fallback))
            if column in working.columns
            else fallback
        )
    grouped = (
        working.groupby(["acquisition_id", "acquisition_name", "acquisition_type", "funding_level_normalized"], dropna=False)[
            AMOUNT_COLUMN
        ]
        .sum()
        .reset_index(name="amount")
    )
    totals = grouped.groupby(["acquisition_id", "acquisition_name", "acquisition_type"], dropna=False)["amount"].sum()
    grouped["line_total"] = grouped.set_index(
        ["acquisition_id", "acquisition_name", "acquisition_type"]
    ).index.map(totals)
    grouped = grouped.sort_values(["line_total", "amount"], ascending=False)
    records = []
    for rank, row in enumerate(grouped.itertuples(index=False), start=1):
        records.append(
            {
                "rank": rank,
                "acquisition_id": str(row.acquisition_id),
                "acquisition_name": str(row.acquisition_name),
                "acquisition_type": str(row.acquisition_type),
                "funding_level": str(row.funding_level_normalized),
                "amount": float(row.amount),
                "amount_display": format_dollars(float(row.amount)),
                "acquisition_total": float(row.line_total),
                "acquisition_total_display": format_dollars(float(row.line_total)),
            }
        )
    return records


def _schedule_frame(crosscuts: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Prepare acquisition rows and parse dates without treating bad dates as valid."""
    required = ["acquisition_id", "acquisition_type", "acquisition_start_date", "acquisition_end_date"]
    missing = _required_columns_available(crosscuts, required)
    if missing:
        return pd.DataFrame(), missing
    working = crosscuts.copy()
    related = ~blank_mask(working["acquisition_id"]) | ~blank_mask(working["acquisition_type"])
    working = working.loc[related].copy()
    working["acquisition_id"] = working["acquisition_id"].map(
        lambda value: display_value(value, "No acquisition ID")
    )
    working["acquisition_name"] = (
        working["acquisition_name"].map(lambda value: display_value(value, "No acquisition name"))
        if "acquisition_name" in working.columns
        else "No acquisition name"
    )
    working["acquisition_type"] = working["acquisition_type"].map(
        lambda value: display_value(value, "No acquisition tag")
    )
    working["start_date_parsed"] = pd.to_datetime(working["acquisition_start_date"], errors="coerce")
    working["end_date_parsed"] = pd.to_datetime(working["acquisition_end_date"], errors="coerce")
    return working, []


def aggregate_acquisition_timeline_funding(crosscuts: pd.DataFrame) -> list[dict[str, Any]]:
    """Return a Gantt-ready schedule table with the scheduled funding-year flags."""
    working, missing = _schedule_frame(crosscuts)
    if missing:
        return [
            {
                "status": "not_evaluated",
                "reason": f"Missing FORMEX columns: {', '.join(missing)}.",
            }
        ]
    records: list[dict[str, Any]] = []
    group_columns = ["acquisition_id", "acquisition_name", "acquisition_type"]
    for values, group in working.groupby(group_columns, dropna=False):
        starts = group["start_date_parsed"].dropna()
        ends = group["end_date_parsed"].dropna()
        start = starts.min() if not starts.empty else pd.NaT
        end = ends.max() if not ends.empty else pd.NaT
        funding_years = sorted(
            int(value)
            for value in group["fiscal_year_number"].dropna().unique().tolist()
        )
        outside = 0
        if pd.notna(start) and pd.notna(end):
            outside = sum(year < start.year or year > end.year for year in funding_years)
        amount = float(group[AMOUNT_COLUMN].sum())
        records.append(
            {
                "acquisition_id": values[0],
                "acquisition_name": values[1],
                "acquisition_type": values[2],
                "start_date": start.date().isoformat() if pd.notna(start) else None,
                "end_date": end.date().isoformat() if pd.notna(end) else None,
                "funding_years": [f"FY{year}" for year in funding_years],
                "funding_amount": amount,
                "funding_amount_display": format_dollars(amount),
                "funding_years_outside_schedule": outside,
                "schedule_status": "review" if outside or pd.isna(start) or pd.isna(end) else "within_schedule",
            }
        )
    return sorted(records, key=lambda row: row["funding_amount"], reverse=True)


def detect_acquisition_schedule_exceptions(
    crosscuts: pd.DataFrame, materiality_threshold: float = MATERIALITY_THRESHOLD
) -> list[dict[str, Any]]:
    """Evaluate deterministic, column-tolerant schedule metadata exceptions."""
    specifications = [
        ("AQ001", "Acquisition type populated but acquisition ID blank", ["acquisition_type", "acquisition_id"]),
        ("AQ002", "Acquisition ID populated but acquisition name blank", ["acquisition_id", "acquisition_name"]),
        ("AQ003", "Acquisition-related row missing start date", ["acquisition_id", "acquisition_type", "acquisition_start_date"]),
        ("AQ004", "Acquisition-related row missing end date", ["acquisition_id", "acquisition_type", "acquisition_end_date"]),
        ("AQ005", "Acquisition start date is after end date", ["acquisition_start_date", "acquisition_end_date"]),
        ("AQ006", "Funding fiscal year falls outside acquisition schedule", ["acquisition_start_date", "acquisition_end_date", "fiscal_year_number"]),
        ("AQ007", "High-dollar acquisition row lacks schedule metadata", ["acquisition_id", "acquisition_type", "acquisition_start_date", "acquisition_end_date"]),
    ]
    results: list[dict[str, Any]] = []
    for rule_id, title, required in specifications:
        missing = _required_columns_available(crosscuts, required)
        if missing:
            results.append(
                {
                    "rule_id": rule_id,
                    "title": title,
                    "status": "not_evaluated",
                    "severity": "not_evaluated",
                    "row_count": 0,
                    "affected_dollars": None,
                    "affected_dollars_display": "Not available",
                    "details": f"Not evaluated because FORMEX columns are unavailable: {', '.join(missing)}.",
                    "source_row_id_sample": [],
                }
            )
            continue
        acquisition_related = ~blank_mask(crosscuts["acquisition_id"]) | ~blank_mask(crosscuts["acquisition_type"])
        if rule_id == "AQ001":
            mask = ~blank_mask(crosscuts["acquisition_type"]) & blank_mask(crosscuts["acquisition_id"])
        elif rule_id == "AQ002":
            mask = ~blank_mask(crosscuts["acquisition_id"]) & blank_mask(crosscuts["acquisition_name"])
        else:
            starts = pd.to_datetime(crosscuts["acquisition_start_date"], errors="coerce")
            ends = pd.to_datetime(crosscuts["acquisition_end_date"], errors="coerce")
            if rule_id == "AQ003":
                mask = acquisition_related & starts.isna()
            elif rule_id == "AQ004":
                mask = acquisition_related & ends.isna()
            elif rule_id == "AQ005":
                mask = starts.notna() & ends.notna() & (starts > ends)
            elif rule_id == "AQ006":
                years = pd.to_numeric(crosscuts["fiscal_year_number"], errors="coerce")
                mask = starts.notna() & ends.notna() & ((years < starts.dt.year) | (years > ends.dt.year))
            else:
                mask = acquisition_related & (starts.isna() | ends.isna()) & (
                    crosscuts[AMOUNT_COLUMN].abs() >= materiality_threshold
                )
        affected = float(crosscuts.loc[mask, AMOUNT_COLUMN].sum())
        results.append(
            {
                "rule_id": rule_id,
                "title": title,
                "status": "evaluated",
                "severity": "high" if rule_id in {"AQ005", "AQ006", "AQ007"} else "medium",
                "row_count": int(mask.sum()),
                "affected_dollars": affected,
                "affected_dollars_display": format_dollars(affected),
                "details": "Deterministic review trigger; it is not a confirmed schedule error.",
                "source_row_id_sample": crosscuts.loc[mask, "source_row_id"].astype(str).head(100).tolist()
                if "source_row_id" in crosscuts.columns
                else [],
            }
        )
    return results


def aggregate_li_tec_li_opc_site_year(site_splits: pd.DataFrame) -> list[dict[str, Any]]:
    """Aggregate LI TEC and LI OPC Site Splits dollars by site and fiscal year."""
    required = ["acquisition_type", "fiscal_year_normalized"]
    missing = _required_columns_available(site_splits, required)
    site_column = "site_planex" if "site_planex" in site_splits.columns else "site_name"
    if site_column not in site_splits.columns:
        missing.append("site_planex/site_name")
    if missing:
        return [{"status": "not_evaluated", "reason": f"Missing FORMEX columns: {', '.join(missing)}."}]
    working = site_splits.copy()
    acquisition_types = working["acquisition_type"].astype("string").str.strip().str.upper()
    working = working.loc[acquisition_types.isin(["LI TEC", "LI OPC"])].copy()
    working["acquisition_type"] = working["acquisition_type"].astype("string").str.strip().str.upper()
    working["site"] = working[site_column].map(lambda value: display_value(value, "Unspecified site"))
    grouped = (
        working.groupby(["site", "fiscal_year_normalized", "acquisition_type"], dropna=False)[AMOUNT_COLUMN]
        .sum()
        .reset_index(name="amount")
        .sort_values("amount", ascending=False)
    )
    return [
        {
            "site": str(row.site),
            "fiscal_year": str(row.fiscal_year_normalized),
            "acquisition_type": str(row.acquisition_type),
            "amount": float(row.amount),
            "amount_display": format_dollars(float(row.amount)),
        }
        for row in grouped.itertuples(index=False)
    ]


def aggregate_above_baseline_acquisition_priority(
    crosscuts: pd.DataFrame, materiality_threshold: float = MATERIALITY_THRESHOLD
) -> list[dict[str, Any]]:
    """Rank ROT/UFR acquisition-related requests with transparent priority signals."""
    if "program_request" not in crosscuts.columns:
        return [{"status": "not_evaluated", "reason": "Missing FORMEX column: program_request."}]
    working = crosscuts.loc[crosscuts["funding_level_normalized"].isin(["ROT", "UFR"])].copy()
    working["program_request"] = working["program_request"].map(
        lambda value: display_value(value, "Unspecified program request")
    )
    for column, fallback in [
        ("acquisition_type", "No acquisition tag"),
        ("program_priority", "Unspecified"),
        ("doe_priority_tier", "Unspecified"),
    ]:
        working[column] = (
            working[column].map(lambda value: display_value(value, fallback))
            if column in working.columns
            else fallback
        )
    grouped = (
        working.groupby(
            [
                "program_request",
                "funding_level_normalized",
                "acquisition_type",
                "program_priority",
                "doe_priority_tier",
            ],
            dropna=False,
        )[AMOUNT_COLUMN]
        .sum()
        .reset_index(name="amount")
        .sort_values("amount", ascending=False)
    )
    records = []
    for rank, row in enumerate(grouped.itertuples(index=False), start=1):
        amount = float(row.amount)
        program_priority = pd.to_numeric(pd.Series([row.program_priority]), errors="coerce").iloc[0]
        tier = pd.to_numeric(pd.Series([row.doe_priority_tier]), errors="coerce").iloc[0]
        records.append(
            {
                "rank": rank,
                "program_request": str(row.program_request),
                "funding_level": str(row.funding_level_normalized),
                "acquisition_type": str(row.acquisition_type),
                "program_priority": str(row.program_priority),
                "doe_priority_tier": str(row.doe_priority_tier),
                "amount": amount,
                "amount_display": format_dollars(amount),
                "is_material": abs(amount) >= materiality_threshold,
                "priority_review_signal": bool(
                    (pd.notna(program_priority) and program_priority <= 3)
                    or (pd.notna(tier) and tier == 1)
                ),
            }
        )
    return records


def _summary(data: list[dict[str, Any]], empty: str, key: str = "amount") -> str:
    """Return a bounded deterministic narrative for a chart payload."""
    usable = [row for row in data if isinstance(row.get(key), (int, float))]
    if not usable:
        return empty
    leader = max(usable, key=lambda row: float(row[key]))
    label = leader.get("acquisition_id") or leader.get("site") or leader.get("program_request") or leader.get("acquisition_type")
    return f"The largest displayed grouping is {label} at {format_dollars(float(leader[key]))}."


def build_dashboard_02_payloads(project_root: Path | None = None) -> dict[str, Any]:
    """Build all Dashboard 2 JSON payloads, RAG context, and ontology graph."""
    root, crosscuts, site_splits, metadata = load_pit_production_layers(project_root)
    crosscuts_filter = {**metadata["base_filter"], "submission_type": CROSSCUTS_SUBMISSION_TYPE}
    sites_filter = {**metadata["base_filter"], "submission_type": SITE_SPLITS_SUBMISSION_TYPE}
    q1_data = aggregate_acquisition_type_by_funding_level(crosscuts)
    q2_data = aggregate_largest_acquisition_lines(crosscuts)
    q3_data = aggregate_acquisition_timeline_funding(crosscuts)
    q4_data = detect_acquisition_schedule_exceptions(crosscuts)
    q5_data = aggregate_li_tec_li_opc_site_year(site_splits)
    q6_data = aggregate_above_baseline_acquisition_priority(crosscuts)
    limitations = COMMON_LIMITATIONS + [
        "Schedule fields are FORMEX metadata and do not independently demonstrate acquisition executability.",
        f"The high-dollar review threshold is {format_dollars(MATERIALITY_THRESHOLD)} when no configured threshold is available.",
    ]
    payloads = {
        "q1": make_payload(
            dashboard_id=DASHBOARD_ID, dashboard_title=DASHBOARD_TITLE, question_id="q1", question_text=QUESTION_TEXT["q1"],
            chart_type="stacked_bar", chart_title="Pit Production funding by acquisition type and funding level",
            metric_definition="Sum of FORMEX Formulated Measure by acquisition type and funding level in Federal Crosscuts; blank types are No acquisition tag.",
            source_submission_type=CROSSCUTS_SUBMISSION_TYPE, row_filter=crosscuts_filter,
            grouping_columns=["acquisition_type", "funding_level"], value_column=AMOUNT_COLUMN, record_count=len(crosscuts), data=q1_data,
            summary=_summary(q1_data, "No acquisition-type funding rows were available."), limitations=limitations,
            lineage=source_row_lineage(crosscuts), metric_cards=[{"label": "Crosscuts acquisition funding", "value": sum(row["amount"] for row in q1_data), "display": format_dollars(sum(row["amount"] for row in q1_data))}], metadata=metadata,
        ),
        "q2": make_payload(
            dashboard_id=DASHBOARD_ID, dashboard_title=DASHBOARD_TITLE, question_id="q2", question_text=QUESTION_TEXT["q2"],
            chart_type="ranked_table", chart_title="Largest Pit Production acquisition lines",
            metric_definition="Sum of FORMEX Formulated Measure by acquisition ID, name, type, and funding level in Federal Crosscuts; blank IDs remain in the No acquisition ID bucket.",
            source_submission_type=CROSSCUTS_SUBMISSION_TYPE, row_filter=crosscuts_filter,
            grouping_columns=["acquisition_id", "acquisition_name", "acquisition_type", "funding_level"], value_column=AMOUNT_COLUMN, record_count=len(crosscuts), data=q2_data,
            summary=_summary(q2_data, "No acquisition lines were available."), limitations=limitations,
            lineage=source_row_lineage(crosscuts), metric_cards=[{"label": "Acquisition line rows", "value": len(q2_data), "display": str(len(q2_data))}], metadata=metadata,
        ),
        "q3": make_payload(
            dashboard_id=DASHBOARD_ID, dashboard_title=DASHBOARD_TITLE, question_id="q3", question_text=QUESTION_TEXT["q3"],
            chart_type="schedule_table", chart_title="Acquisition dates and funding-year alignment",
            metric_definition="Acquisition start and end dates paired with Federal Crosscuts funding years; funding years outside parseable schedule dates are flagged for review.",
            source_submission_type=CROSSCUTS_SUBMISSION_TYPE, row_filter=crosscuts_filter,
            grouping_columns=["acquisition_id", "acquisition_start_date", "acquisition_end_date", "fiscal_year"], value_column=AMOUNT_COLUMN, record_count=len(crosscuts), data=q3_data,
            summary=_summary(q3_data, "No acquisition schedule rows were available.", "funding_amount"), limitations=limitations,
            lineage=source_row_lineage(crosscuts), metric_cards=[{"label": "Scheduled acquisition lines", "value": len(q3_data), "display": str(len(q3_data))}], metadata=metadata,
        ),
        "q4": make_payload(
            dashboard_id=DASHBOARD_ID, dashboard_title=DASHBOARD_TITLE, question_id="q4", question_text=QUESTION_TEXT["q4"],
            chart_type="exception_table", chart_title="Acquisition schedule metadata exceptions",
            metric_definition="Column-tolerant deterministic checks for missing IDs, names, dates, invalid date order, funding outside dates, and high-dollar missing schedule metadata.",
            source_submission_type=CROSSCUTS_SUBMISSION_TYPE, row_filter=crosscuts_filter,
            grouping_columns=["rule_id"], value_column=f"{AMOUNT_COLUMN} affected dollars", record_count=len(crosscuts), data=q4_data,
            summary=f"{sum(row.get('row_count', 0) for row in q4_data if row.get('status') == 'evaluated')} acquisition-row exceptions were flagged for analyst review.", limitations=limitations,
            lineage=source_row_lineage(crosscuts), metric_cards=[{"label": "High-severity checks", "value": sum(row.get("severity") == "high" and row.get("row_count", 0) > 0 for row in q4_data), "display": str(sum(row.get("severity") == "high" and row.get("row_count", 0) > 0 for row in q4_data))}], metadata=metadata,
        ),
        "q5": make_payload(
            dashboard_id=DASHBOARD_ID, dashboard_title=DASHBOARD_TITLE, question_id="q5", question_text=QUESTION_TEXT["q5"],
            chart_type="site_year_heatmap_table", chart_title="LI TEC and LI OPC funding by site and year",
            metric_definition="Sum of FORMEX Formulated Measure by Site, fiscal year, and acquisition type restricted to LI TEC and LI OPC in Federal Site Splits.",
            source_submission_type=SITE_SPLITS_SUBMISSION_TYPE, row_filter={**sites_filter, "acquisition_type": ["LI TEC", "LI OPC"]},
            grouping_columns=["site", "fiscal_year", "acquisition_type"], value_column=AMOUNT_COLUMN, record_count=len(site_splits), data=q5_data,
            summary=_summary(q5_data, "LI TEC and LI OPC could not be evaluated from Site Splits."), limitations=limitations + ["No Crosscuts-to-Site-Splits join is invented when Site Splits acquisition fields are weak or absent."],
            lineage=source_row_lineage(site_splits), metric_cards=[{"label": "LI TEC / LI OPC cells", "value": len(q5_data), "display": str(len(q5_data))}], metadata=metadata,
        ),
        "q6": make_payload(
            dashboard_id=DASHBOARD_ID, dashboard_title=DASHBOARD_TITLE, question_id="q6", question_text=QUESTION_TEXT["q6"],
            chart_type="ranked_priority_table", chart_title="Above-baseline acquisition requests with priority signals",
            metric_definition="Sum of FORMEX Formulated Measure by program request, funding level, acquisition type, program priority, and DOE priority tier for ROT and UFR Federal Crosscuts rows.",
            source_submission_type=CROSSCUTS_SUBMISSION_TYPE, row_filter={**crosscuts_filter, "funding_level": ["ROT", "UFR"]},
            grouping_columns=["program_request", "funding_level", "acquisition_type", "program_priority", "doe_priority_tier"], value_column=AMOUNT_COLUMN, record_count=int(crosscuts["funding_level_normalized"].isin(["ROT", "UFR"]).sum()), data=q6_data,
            summary=_summary(q6_data, "No above-baseline acquisition requests were available."), limitations=limitations + ["Priority signals identify review targets; they do not establish request merit."],
            lineage=source_row_lineage(crosscuts.loc[crosscuts["funding_level_normalized"].isin(["ROT", "UFR"])]), metric_cards=[{"label": "Material requests", "value": sum(row.get("is_material", False) for row in q6_data), "display": str(sum(row.get("is_material", False) for row in q6_data))}], metadata=metadata,
        ),
    }
    return write_dashboard_artifacts(
        root=root, dashboard_id=DASHBOARD_ID, dashboard_title=DASHBOARD_TITLE, payloads=payloads,
        payload_files=PAYLOAD_FILES, metadata=metadata, limitations=limitations,
    )


if __name__ == "__main__":  # pragma: no cover
    print(build_dashboard_02_payloads())
