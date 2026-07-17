"""Build Dashboard 4 priority, tier, and program-request challenge artifacts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from cepe_fynsp.dashboards.dashboard_support import (
    AMOUNT_COLUMN,
    COMMON_LIMITATIONS,
    CROSSCUTS_SUBMISSION_TYPE,
    blank_mask,
    display_value,
    format_dollars,
    load_pit_production_layers,
    make_payload,
    source_row_lineage,
    write_dashboard_artifacts,
)

DASHBOARD_ID = "dashboard_04_priority_challenge"
DASHBOARD_TITLE = "Priority, Tier, and Program Request Challenge Board"
MATERIALITY_THRESHOLD = 100_000_000.0

QUESTION_TEXT = {
    "q1": "What are the largest Pit Production ROT and UFR requests?",
    "q2": "Which above-baseline requests are marked Tier 1, and why is that a review issue?",
    "q3": "Do program priorities form a clear 1-N ranking, or are priorities reused across requests?",
    "q4": "Which requests appear to be offsets, restorations, or delays?",
    "q5": "Which requests have strong traceability from title to scope, site, WBS, and acquisition?",
    "q6": "Which rows lack Account Integrator decision traceability?",
}

PAYLOAD_FILES = {
    "q1": "q1_largest_rot_ufr_requests.json",
    "q2": "q2_tier_by_funding_level.json",
    "q3": "q3_priority_uniqueness.json",
    "q4": "q4_offsets_restorations_delays.json",
    "q5": "q5_traceability_scorecard.json",
    "q6": "q6_account_integrator_traceability.json",
}


def _above_baseline(df: pd.DataFrame) -> pd.DataFrame:
    """Return only normalized ROT/UFR rows from an explicit Crosscuts input."""
    return df.loc[df["funding_level_normalized"].isin(["ROT", "UFR"])].copy()


def rank_rot_ufr_requests(crosscuts: pd.DataFrame) -> list[dict[str, Any]]:
    """Rank above-baseline program requests with Pareto shares."""
    if "program_request" not in crosscuts.columns:
        return [{"status": "not_evaluated", "reason": "Missing FORMEX program_request column."}]
    working = _above_baseline(crosscuts)
    working["program_request"] = working["program_request"].map(
        lambda value: display_value(value, "Unspecified program request")
    )
    grouped = (
        working.groupby(["program_request", "funding_level_normalized"], dropna=False)[
            AMOUNT_COLUMN
        ]
        .sum()
        .reset_index(name="amount")
        .sort_values("amount", ascending=False)
    )
    total = float(grouped["amount"].sum())
    cumulative = 0.0
    records = []
    for rank, row in enumerate(grouped.itertuples(index=False), start=1):
        amount = float(row.amount)
        cumulative += amount
        records.append(
            {
                "rank": rank,
                "program_request": str(row.program_request),
                "funding_level": str(row.funding_level_normalized),
                "amount": amount,
                "amount_display": format_dollars(amount),
                "share_of_above_baseline": amount / total if total else None,
                "cumulative_share": cumulative / total if total else None,
            }
        )
    return records


def aggregate_tier_by_funding_level(crosscuts: pd.DataFrame) -> list[dict[str, Any]]:
    """Summarize DOE Priority Tier by funding level and mark Tier 1 ROT/UFR review triggers."""
    if "doe_priority_tier" not in crosscuts.columns:
        return [{"status": "not_evaluated", "reason": "Missing FORMEX doe_priority_tier column."}]
    working = crosscuts.copy()
    working["doe_priority_tier"] = working["doe_priority_tier"].map(
        lambda value: display_value(value, "Unspecified")
    )
    grouped = (
        working.groupby(["funding_level_normalized", "doe_priority_tier"], dropna=False)
        .agg(row_count=(AMOUNT_COLUMN, "size"), amount=(AMOUNT_COLUMN, "sum"))
        .reset_index()
        .sort_values(["funding_level_normalized", "doe_priority_tier"])
    )
    records = []
    for row in grouped.itertuples(index=False):
        tier = pd.to_numeric(pd.Series([row.doe_priority_tier]), errors="coerce").iloc[0]
        is_trigger = row.funding_level_normalized in {"ROT", "UFR"} and pd.notna(tier) and tier == 1
        records.append(
            {
                "funding_level": str(row.funding_level_normalized),
                "doe_priority_tier": str(row.doe_priority_tier),
                "row_count": int(row.row_count),
                "amount": float(row.amount),
                "amount_display": format_dollars(float(row.amount)),
                "tier1_above_baseline_review_trigger": bool(is_trigger),
                "review_note": "Review consistency with guidance; this is not automatically an error."
                if is_trigger
                else "",
            }
        )
    return records


def priority_category(value: object) -> str:
    """Classify priority values so blank, zero, and text remain analytically distinct."""
    if pd.isna(value) or str(value).strip().casefold() in {"", "<na>", "na", "n/a", "none"}:
        return "Blank"
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return f"Non-numeric: {str(value).strip()}"
    if parsed == 0:
        return "Zero"
    if float(parsed).is_integer():
        return str(int(parsed))
    return str(float(parsed))


def calculate_priority_uniqueness(
    crosscuts: pd.DataFrame, materiality_threshold: float = MATERIALITY_THRESHOLD
) -> list[dict[str, Any]]:
    """Identify reused priorities among material above-baseline program requests."""
    required = {"program_priority", "program_request"}
    if missing := sorted(required - set(crosscuts.columns)):
        return [
            {"status": "not_evaluated", "reason": f"Missing FORMEX columns: {', '.join(missing)}."}
        ]
    working = _above_baseline(crosscuts)
    working["program_priority_category"] = working["program_priority"].map(priority_category)
    working["program_request"] = working["program_request"].map(
        lambda value: display_value(value, "Unspecified program request")
    )
    grouped = (
        working.groupby(["funding_level_normalized", "program_priority_category"], dropna=False)
        .agg(
            distinct_program_requests=("program_request", "nunique"),
            row_count=(AMOUNT_COLUMN, "size"),
            amount=(AMOUNT_COLUMN, "sum"),
        )
        .reset_index()
    )
    records = []
    for row in grouped.itertuples(index=False):
        amount = float(row.amount)
        duplicate = int(row.distinct_program_requests) > 1
        records.append(
            {
                "funding_level": str(row.funding_level_normalized),
                "program_priority": str(row.program_priority_category),
                "distinct_program_requests": int(row.distinct_program_requests),
                "row_count": int(row.row_count),
                "amount": amount,
                "amount_display": format_dollars(amount),
                "priority_reused": duplicate,
                "material_duplicate_review_trigger": duplicate
                and abs(amount) >= materiality_threshold,
            }
        )
    return sorted(
        records, key=lambda row: (not row["material_duplicate_review_trigger"], -abs(row["amount"]))
    )


def classify_request_intent(
    program_request: object, scope_description: object, amount: float | int | None = None
) -> str:
    """Classify request intent using transparent deterministic keyword rules."""
    text = " ".join(str(value or "") for value in [program_request, scope_description]).casefold()
    if re.search(r"\b(offset|decrement|reduce|reduction)\b", text) or (
        amount is not None and amount < 0
    ):
        return "offset"
    if re.search(r"\b(restor|restore|restoration)\b", text):
        return "restoration"
    if re.search(r"\b(delay\w*|defer\w*|slip\w*|postpone\w*)\b", text):
        return "delay"
    if re.search(r"\b(construction|capital|modernization|li tec|li opc)\b", text):
        return "construction"
    if re.search(r"\b(sustain|maintain|maintenance|operations?)\b", text):
        return "sustainment"
    if re.search(r"\b(support|staff|services?)\b", text):
        return "support"
    return "other"


def classify_offsets_restorations_delays(crosscuts: pd.DataFrame) -> list[dict[str, Any]]:
    """Classify Crosscuts request descriptions using deterministic labels only."""
    if "program_request" not in crosscuts.columns:
        return [{"status": "not_evaluated", "reason": "Missing FORMEX program_request column."}]
    working = crosscuts.copy()
    scope = (
        working["scope_description"]
        if "scope_description" in working.columns
        else pd.Series("", index=working.index)
    )
    working["classification"] = [
        classify_request_intent(request, description, amount)
        for request, description, amount in zip(
            working["program_request"], scope, working[AMOUNT_COLUMN], strict=True
        )
    ]
    working["program_request"] = working["program_request"].map(
        lambda value: display_value(value, "Unspecified program request")
    )
    grouped = (
        working.groupby(
            ["program_request", "funding_level_normalized", "classification"], dropna=False
        )[AMOUNT_COLUMN]
        .sum()
        .reset_index(name="amount")
        .sort_values("amount", ascending=False)
    )
    return [
        {
            "program_request": str(row.program_request),
            "funding_level": str(row.funding_level_normalized),
            "classification": str(row.classification),
            "amount": float(row.amount),
            "amount_display": format_dollars(float(row.amount)),
            "negative_dollar_review_trigger": float(row.amount) < 0,
            "classification_basis": "Deterministic program-request and scope-description keyword rules.",
        }
        for row in grouped.itertuples(index=False)
    ]


def _availability(df: pd.DataFrame, column: str) -> pd.Series:
    """Return populated-field availability or a false series for unavailable optional columns."""
    if column not in df.columns:
        return pd.Series(False, index=df.index)
    return ~blank_mask(df[column])


def calculate_traceability_scores(crosscuts: pd.DataFrame) -> list[dict[str, Any]]:
    """Score request traceability components and expose component coverage transparently."""
    working = crosscuts.copy()
    request = _availability(working, "program_request")
    components: dict[str, pd.Series] = {
        "program_request": request,
        "scope_description": _availability(working, "scope_description"),
        "wbs": _availability(working, "wbs"),
        "bnr": _availability(working, "bnr_code"),
        "site": _availability(working, "site_planex") | _availability(working, "site_name"),
        "fiscal_year": _availability(working, "fiscal_year"),
        "funding_level": _availability(working, "funding_levels"),
    }
    acquisition_related = _availability(working, "acquisition_id") | _availability(
        working, "acquisition_type"
    )
    acquisition_complete = (
        _availability(working, "acquisition_id")
        & _availability(working, "acquisition_name")
        & _availability(working, "acquisition_type")
    )
    components["acquisition"] = (~acquisition_related) | acquisition_complete
    component_frame = pd.DataFrame(components)
    working["program_request_label"] = (
        working["program_request"].map(
            lambda value: display_value(value, "Unspecified program request")
        )
        if "program_request" in working.columns
        else "Unspecified program request"
    )
    working["traceability_score"] = component_frame.mean(axis=1)
    for name in components:
        working[f"component_{name}"] = component_frame[name]
    rows = []
    component_columns = [f"component_{name}" for name in components]
    for program_request, group in working.groupby("program_request_label", dropna=False):
        amount = float(group[AMOUNT_COLUMN].sum())
        component_coverage = {name: float(group[f"component_{name}"].mean()) for name in components}
        rows.append(
            {
                "program_request": str(program_request),
                "row_count": int(len(group)),
                "amount": amount,
                "amount_display": format_dollars(amount),
                "traceability_score": float(group["traceability_score"].mean()),
                "traceability_score_display": f"{float(group['traceability_score'].mean()):.0%}",
                "component_coverage": component_coverage,
                "complete_component_count": int(
                    sum(value == 1.0 for value in component_coverage.values())
                ),
                "component_count": len(component_columns),
            }
        )
    return sorted(rows, key=lambda row: row["traceability_score"], reverse=True)


def account_integrator_traceability(crosscuts: pd.DataFrame) -> list[dict[str, Any]]:
    """Summarize blank Decision and zero/blank Priority fields without assuming a decision."""
    results = []
    for field, title, rule_id, zero_is_missing in [
        ("account_integrator_decision", "Missing Account Integrator Decision", "FQ007", False),
        ("account_integrator_priority", "Blank or zero Account Integrator Priority", "FQ008", True),
    ]:
        if field not in crosscuts.columns:
            results.append(
                {
                    "rule_id": rule_id,
                    "finding_id": rule_id,
                    "title": title,
                    "status": "not_evaluated",
                    "row_count": 0,
                    "affected_dollars": None,
                    "affected_dollars_display": "Not available",
                    "details": f"Not evaluated because FORMEX column '{field}' is unavailable.",
                }
            )
            continue
        mask = blank_mask(crosscuts[field])
        if zero_is_missing:
            numeric = pd.to_numeric(crosscuts[field], errors="coerce")
            mask = mask | (numeric == 0)
        amount = float(crosscuts.loc[mask, AMOUNT_COLUMN].sum())
        results.append(
            {
                "rule_id": rule_id,
                "finding_id": rule_id,
                "title": title,
                "status": "evaluated",
                "severity": "limitation",
                "row_count": int(mask.sum()),
                "affected_dollars": amount,
                "affected_dollars_display": format_dollars(amount),
                "details": "The field is structurally unavailable for review when all rows are blank or zero."
                if bool(mask.all())
                else "Rows require Account Integrator traceability review.",
                "source_row_id_sample": crosscuts.loc[mask, "source_row_id"]
                .astype(str)
                .head(100)
                .tolist()
                if "source_row_id" in crosscuts.columns
                else [],
            }
        )
    return results


def _summary(data: list[dict[str, Any]], empty: str) -> str:
    """Summarize the largest numeric amount without interpreting it as a conclusion."""
    usable = [row for row in data if isinstance(row.get("amount"), (int, float))]
    if not usable:
        return empty
    leader = max(usable, key=lambda row: float(row["amount"]))
    return f"The largest displayed request is {leader.get('program_request', 'unspecified')} at {format_dollars(float(leader['amount']))}."


def build_dashboard_04_payloads(project_root: Path | None = None) -> dict[str, Any]:
    """Build all Dashboard 4 JSON payloads, RAG context, and ontology graph."""
    root, crosscuts, _, metadata = load_pit_production_layers(project_root)
    row_filter = {**metadata["base_filter"], "submission_type": CROSSCUTS_SUBMISSION_TYPE}
    above_filter = {**row_filter, "funding_level": ["ROT", "UFR"]}
    q1_data = rank_rot_ufr_requests(crosscuts)
    q2_data = aggregate_tier_by_funding_level(crosscuts)
    q3_data = calculate_priority_uniqueness(crosscuts)
    q4_data = classify_offsets_restorations_delays(crosscuts)
    q5_data = calculate_traceability_scores(crosscuts)
    q6_data = account_integrator_traceability(crosscuts)
    limitations = COMMON_LIMITATIONS + [
        "Tier 1 ROT/UFR rows are review triggers for consistency with guidance, not automatic data errors.",
        "Request intent labels use deterministic keyword rules and should be confirmed by analysts.",
        f"Material duplicate-priority review uses a default {format_dollars(MATERIALITY_THRESHOLD)} threshold when no configured threshold is available.",
    ]
    payloads = {
        "q1": make_payload(
            dashboard_id=DASHBOARD_ID,
            dashboard_title=DASHBOARD_TITLE,
            question_id="q1",
            question_text=QUESTION_TEXT["q1"],
            chart_type="pareto_ranked_bar",
            chart_title="Largest ROT and UFR program requests",
            metric_definition="Sum of FORMEX Formulated Measure by Program Request and funding level for ROT and UFR Federal Crosscuts rows, with cumulative above-baseline share.",
            source_submission_type=CROSSCUTS_SUBMISSION_TYPE,
            row_filter=above_filter,
            grouping_columns=["program_request", "funding_level"],
            value_column=AMOUNT_COLUMN,
            record_count=len(_above_baseline(crosscuts)),
            data=q1_data,
            summary=_summary(q1_data, "No ROT/UFR requests were available."),
            limitations=limitations,
            lineage=source_row_lineage(_above_baseline(crosscuts)),
            metric_cards=[
                {
                    "label": "Above-baseline requests",
                    "value": len(q1_data),
                    "display": str(len(q1_data)),
                }
            ],
            metadata=metadata,
        ),
        "q2": make_payload(
            dashboard_id=DASHBOARD_ID,
            dashboard_title=DASHBOARD_TITLE,
            question_id="q2",
            question_text=QUESTION_TEXT["q2"],
            chart_type="tier_funding_matrix",
            chart_title="DOE Priority Tier by funding level",
            metric_definition="Row count and Formulated Measure by DOE Priority Tier and funding level in Federal Crosscuts; Tier 1 ROT/UFR is marked as a consistency review trigger.",
            source_submission_type=CROSSCUTS_SUBMISSION_TYPE,
            row_filter=row_filter,
            grouping_columns=["doe_priority_tier", "funding_level"],
            value_column=AMOUNT_COLUMN,
            record_count=len(crosscuts),
            data=q2_data,
            summary=f"{sum(row.get('tier1_above_baseline_review_trigger', False) for row in q2_data)} Tier 1 above-baseline cells are review triggers.",
            limitations=limitations,
            lineage=source_row_lineage(crosscuts),
            metric_cards=[
                {
                    "label": "Tier 1 above-baseline cells",
                    "value": sum(
                        row.get("tier1_above_baseline_review_trigger", False) for row in q2_data
                    ),
                    "display": str(
                        sum(
                            row.get("tier1_above_baseline_review_trigger", False) for row in q2_data
                        )
                    ),
                }
            ],
            metadata=metadata,
        ),
        "q3": make_payload(
            dashboard_id=DASHBOARD_ID,
            dashboard_title=DASHBOARD_TITLE,
            question_id="q3",
            question_text=QUESTION_TEXT["q3"],
            chart_type="priority_uniqueness_matrix",
            chart_title="Program-priority uniqueness among above-baseline requests",
            metric_definition="Distinct Program Request count and dollars by Program Priority and funding level for ROT/UFR Federal Crosscuts rows; blank, zero, and non-numeric priorities remain separate.",
            source_submission_type=CROSSCUTS_SUBMISSION_TYPE,
            row_filter=above_filter,
            grouping_columns=["program_priority", "funding_level"],
            value_column=AMOUNT_COLUMN,
            record_count=len(_above_baseline(crosscuts)),
            data=q3_data,
            summary=f"{sum(row.get('material_duplicate_review_trigger', False) for row in q3_data)} material reused-priority groups are review triggers.",
            limitations=limitations,
            lineage=source_row_lineage(_above_baseline(crosscuts)),
            metric_cards=[
                {
                    "label": "Reused-priority groups",
                    "value": sum(row.get("priority_reused", False) for row in q3_data),
                    "display": str(sum(row.get("priority_reused", False) for row in q3_data)),
                }
            ],
            metadata=metadata,
        ),
        "q4": make_payload(
            dashboard_id=DASHBOARD_ID,
            dashboard_title=DASHBOARD_TITLE,
            question_id="q4",
            question_text=QUESTION_TEXT["q4"],
            chart_type="classified_ranked_table",
            chart_title="Deterministically classified offsets, restorations, and delays",
            metric_definition="Sum of FORMEX Formulated Measure by Program Request, funding level, and deterministic intent label using request/scope keywords and negative-dollar flags.",
            source_submission_type=CROSSCUTS_SUBMISSION_TYPE,
            row_filter=row_filter,
            grouping_columns=["program_request", "funding_level", "classification"],
            value_column=AMOUNT_COLUMN,
            record_count=len(crosscuts),
            data=q4_data,
            summary=_summary(q4_data, "No program-request classifications were available."),
            limitations=limitations,
            lineage=source_row_lineage(crosscuts),
            metric_cards=[
                {
                    "label": "Negative-dollar groups",
                    "value": sum(
                        row.get("negative_dollar_review_trigger", False) for row in q4_data
                    ),
                    "display": str(
                        sum(row.get("negative_dollar_review_trigger", False) for row in q4_data)
                    ),
                }
            ],
            metadata=metadata,
        ),
        "q5": make_payload(
            dashboard_id=DASHBOARD_ID,
            dashboard_title=DASHBOARD_TITLE,
            question_id="q5",
            question_text=QUESTION_TEXT["q5"],
            chart_type="traceability_scorecard",
            chart_title="Program-request traceability completeness",
            metric_definition="Per-program-request component completeness score for title, scope, WBS, BNR, site where available, acquisition fields when acquisition-related, fiscal year, and funding level in Federal Crosscuts.",
            source_submission_type=CROSSCUTS_SUBMISSION_TYPE,
            row_filter=row_filter,
            grouping_columns=["program_request"],
            value_column="traceability completeness score",
            record_count=len(crosscuts),
            data=q5_data,
            summary=f"Average traceability score across displayed program requests is {sum(row['traceability_score'] for row in q5_data) / len(q5_data):.0%}."
            if q5_data
            else "No traceability rows were available.",
            limitations=limitations,
            lineage=source_row_lineage(crosscuts),
            metric_cards=[
                {
                    "label": "Program requests scored",
                    "value": len(q5_data),
                    "display": str(len(q5_data)),
                }
            ],
            metadata=metadata,
        ),
        "q6": make_payload(
            dashboard_id=DASHBOARD_ID,
            dashboard_title=DASHBOARD_TITLE,
            question_id="q6",
            question_text=QUESTION_TEXT["q6"],
            chart_type="account_integrator_completeness_table",
            chart_title="Account Integrator decision traceability",
            metric_definition="Missing/blank Account Integrator Decision and blank/zero Account Integrator Priority counts and affected dollars in Federal Crosscuts.",
            source_submission_type=CROSSCUTS_SUBMISSION_TYPE,
            row_filter=row_filter,
            grouping_columns=["rule_id"],
            value_column=f"{AMOUNT_COLUMN} affected dollars",
            record_count=len(crosscuts),
            data=q6_data,
            summary="Account Integrator fields are reported as a data limitation when they are structurally blank or zero in the extract.",
            limitations=limitations,
            lineage=source_row_lineage(crosscuts),
            metric_cards=[
                {
                    "label": "Traceability limitation rows",
                    "value": sum(row.get("row_count", 0) for row in q6_data),
                    "display": str(sum(row.get("row_count", 0) for row in q6_data)),
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
    print(build_dashboard_04_payloads())
