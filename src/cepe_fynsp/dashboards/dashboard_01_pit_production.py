"""Build Dashboard 1 artifacts for the Pit Production program review.

The module keeps data transformations deterministic and produces only aggregate
dashboard data plus source-row identifiers for lineage. It deliberately does not
make a live AskSage call; callers may pass the generated chart payload to the
existing AskSage client through :func:`request_asksage_chart_summary` when an
approved backend and credentials are available.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from numbers import Integral, Real
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from cepe_fynsp.asksage.client import AskSageClient
from cepe_fynsp.config import load_settings
from cepe_fynsp.etl.loaders import load_formex
from cepe_fynsp.etl.normalize import add_source_row_id, normalize_columns, parse_dollar_amounts, require_columns
from cepe_fynsp.quality.rules import (
    QualityFinding,
    evaluate_dashboard_01_quality_rules,
    reconciliation_finding,
)

LOGGER = logging.getLogger(__name__)

DASHBOARD_ID = "dashboard_01_pit_production"
DASHBOARD_TITLE = "Pit Production Accuracy and Thoroughness Overview"
INTEGRATION_AREA = "Pit Production"
CROSSCUTS_SUBMISSION_TYPE = "Federal Crosscuts"
SITE_SPLITS_SUBMISSION_TYPE = "Federal Site Splits"
AMOUNT_COLUMN = "formulated_measure"
PIPELINE_VERSION = "dashboard_01_v1"
LINEAGE_SAMPLE_LIMIT = 250
FUNDING_LEVEL_ORDER = {"Baseline": 0, "ROT": 1, "UFR": 2}
BLANK_LIKE_VALUES = {"", "<na>", "n/a", "na", "nan", "none", "null"}

QUESTION_TEXT = {
    "q1": "How much funding is programmed for Pit Production by fiscal year and funding level?",
    "q2": "Which organizations own the largest Pit Production funding shares?",
    "q3": "Which sites receive Pit Production funding, and how concentrated is the portfolio?",
    "q4": "Which program requests drive above-baseline Pit Production growth?",
    "q5": "Are there rows that appear incomplete, contradictory, or hard to trace?",
    "q6": "Do Federal Crosscuts and Federal Site Splits reconcile for Pit Production?",
}


@dataclass(frozen=True)
class BuildMetadata:
    """Stable metadata shared by each Dashboard 1 chart payload."""

    generated_at: str
    source_file: str
    source_file_sha256: str
    scenario: str | None
    git_commit: str | None


def project_root_from_module() -> Path:
    """Return the repository root when no explicit project root is supplied."""
    return Path(__file__).resolve().parents[3]


def find_formex_csv(project_root: Path) -> Path:
    """Find the only FORMEX CSV below ``data/raw/formex``.

    A clear error is raised for missing or ambiguous input rather than quietly
    selecting an arbitrary submission export.
    """
    formex_dir = project_root / "data" / "raw" / "formex"
    candidates = sorted(
        path for path in formex_dir.glob("*") if path.is_file() and path.suffix.casefold() == ".csv"
    )
    if not candidates:
        raise FileNotFoundError(
            f"No FORMEX CSV was found under '{formex_dir}'. Add one UTF-16 tab-delimited CSV."
        )
    if len(candidates) > 1:
        listed = ", ".join(path.name for path in candidates)
        raise ValueError(
            "Multiple FORMEX CSV candidates were found under "
            f"'{formex_dir}': {listed}. Keep one CSV there or disambiguate the input first."
        )
    return candidates[0]


def normalize_text_value(value: object) -> str | None:
    """Normalize FORMEX text defensively while retaining meaningful values."""
    if pd.isna(value):
        return None
    text = re.sub(r"\s+", " ", str(value).strip())
    return None if text.casefold() in BLANK_LIKE_VALUES else text


def normalize_funding_level(value: object) -> str:
    """Map spelling and capitalization variations to dashboard funding levels."""
    text = normalize_text_value(value)
    if text is None:
        return "Unspecified"
    compact = re.sub(r"[^a-z0-9]", "", text.casefold())
    aliases = {
        "baseline": "Baseline",
        "base": "Baseline",
        "rot": "ROT",
        "requestovertarget": "ROT",
        "requestoverthreshold": "ROT",
        "ufr": "UFR",
        "unfundedrequirement": "UFR",
    }
    return aliases.get(compact, text.upper())


def normalize_submission_type(value: object) -> str | None:
    """Canonicalize known FORMEX submission-type labels."""
    text = normalize_text_value(value)
    if text is None:
        return None
    compact = re.sub(r"[^a-z0-9]", "", text.casefold())
    aliases = {
        "federalcrosscuts": CROSSCUTS_SUBMISSION_TYPE,
        "federalsitesplits": SITE_SPLITS_SUBMISSION_TYPE,
        "gpraconstraints": "GPRA Constraints",
        "federalstattable": "Federal STAT Table",
    }
    return aliases.get(compact, text)


def normalize_fiscal_year(value: object) -> tuple[str, int | None]:
    """Return a display label and sortable fiscal-year number."""
    text = normalize_text_value(value)
    if text is None:
        return "Unspecified", None
    match = re.search(r"(20\d{2})", text)
    if not match:
        return text, None
    year = int(match.group(1))
    return f"FY{year}", year


def prepare_formex_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize a loaded FORMEX frame and add deterministic dashboard fields."""
    prepared = normalize_columns(df)
    required = [
        "submission_type",
        "program_int_area",
        "fiscal_year",
        "funding_levels",
        AMOUNT_COLUMN,
    ]
    require_columns(prepared, required)

    for column in prepared.columns:
        if pd.api.types.is_object_dtype(prepared[column]) or pd.api.types.is_string_dtype(
            prepared[column]
        ):
            prepared[column] = prepared[column].map(normalize_text_value)

    if "source_row_id" not in prepared.columns:
        prepared = add_source_row_id(prepared, "formex")
    prepared[AMOUNT_COLUMN] = parse_dollar_amounts(prepared[AMOUNT_COLUMN])
    prepared["submission_type"] = prepared["submission_type"].map(normalize_submission_type)
    prepared["program_int_area_normalized"] = prepared["program_int_area"].map(normalize_text_value)
    prepared["funding_level_normalized"] = prepared["funding_levels"].map(normalize_funding_level)
    fiscal_values = prepared["fiscal_year"].map(normalize_fiscal_year)
    prepared["fiscal_year_normalized"] = fiscal_values.map(lambda value: value[0])
    prepared["fiscal_year_number"] = fiscal_values.map(lambda value: value[1])
    return prepared


def select_scenario(df: pd.DataFrame, configured_scenario: str | None) -> str | None:
    """Select the explicit scenario required for FORMEX aggregation.

    A one-scenario source is still reported as explicitly selected. For a source
    with multiple scenarios, the configured default must be present to prevent an
    accidental cross-scenario sum.
    """
    if "scenario" not in df.columns:
        return None
    scenarios = sorted({value for value in df["scenario"].dropna().tolist() if value})
    if not scenarios:
        return None
    if len(scenarios) == 1:
        return scenarios[0]
    normalized_default = normalize_text_value(configured_scenario)
    if normalized_default:
        for scenario in scenarios:
            if scenario.casefold() == normalized_default.casefold():
                return scenario
    options = ", ".join(scenarios)
    raise ValueError(
        "FORMEX contains multiple scenarios, but the configured default scenario "
        f"was not found. Available scenarios: {options}."
    )


def filter_pit_production(
    df: pd.DataFrame,
    submission_type: str,
    *,
    integration_area: str = INTEGRATION_AREA,
    scenario: str | None = None,
) -> pd.DataFrame:
    """Filter a prepared FORMEX frame to one submission layer and Pit Production."""
    required = {"submission_type", "program_int_area_normalized"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Cannot filter Pit Production rows; missing columns: {missing}")
    area = normalize_text_value(integration_area)
    if area is None:
        raise ValueError("integration_area must contain a non-blank value.")
    mask = (
        (df["submission_type"] == submission_type)
        & (df["program_int_area_normalized"].astype("string").str.casefold() == area.casefold())
    )
    if scenario is not None:
        if "scenario" not in df.columns:
            raise ValueError("FORMEX scenario filtering was requested but the 'scenario' column is absent.")
        mask &= df["scenario"].astype("string").str.casefold() == scenario.casefold()
    return df.loc[mask].copy()


def format_dollars(value: float | int | None) -> str:
    """Format a raw dollar value for a compact dashboard display label."""
    if value is None or pd.isna(value):
        return "Not available"
    amount = float(value)
    sign = "-" if amount < 0 else ""
    absolute = abs(amount)
    if absolute >= 1_000_000_000:
        return f"{sign}${absolute / 1_000_000_000:.1f}B"
    if absolute >= 1_000_000:
        return f"{sign}${absolute / 1_000_000:.1f}M"
    if absolute >= 1_000:
        return f"{sign}${absolute / 1_000:.1f}K"
    return f"{sign}${absolute:,.0f}"


def aggregate_q1_funding_by_year_level(crosscuts: pd.DataFrame) -> list[dict[str, Any]]:
    """Aggregate Federal Crosscuts funding by fiscal year and funding level."""
    grouped = (
        crosscuts.groupby(["fiscal_year_normalized", "fiscal_year_number", "funding_level_normalized"], dropna=False)[
            AMOUNT_COLUMN
        ]
        .sum()
        .reset_index(name="amount")
    )
    grouped["level_order"] = grouped["funding_level_normalized"].map(FUNDING_LEVEL_ORDER).fillna(99)
    grouped = grouped.sort_values(
        ["fiscal_year_number", "fiscal_year_normalized", "level_order", "funding_level_normalized"],
        na_position="last",
    )
    records: list[dict[str, Any]] = []
    for row in grouped.itertuples(index=False):
        amount = float(row.amount)
        records.append(
            {
                "fiscal_year": row.fiscal_year_normalized,
                "fiscal_year_number": int(row.fiscal_year_number)
                if pd.notna(row.fiscal_year_number)
                else None,
                "funding_level": row.funding_level_normalized,
                "amount": amount,
                "amount_display": format_dollars(amount),
            }
        )
    return records


def aggregate_q2_funding_by_organization(crosscuts: pd.DataFrame) -> list[dict[str, Any]]:
    """Aggregate and rank Federal Crosscuts funding by Sub Office Number."""
    organization_column = "sub_office_number"
    if organization_column not in crosscuts.columns:
        return []
    working = crosscuts.copy()
    working[organization_column] = working[organization_column].fillna("Unspecified organization")
    grouped = working.groupby(organization_column, dropna=False)[AMOUNT_COLUMN].sum().reset_index(name="amount")
    grouped = grouped.sort_values("amount", ascending=False)
    total = float(grouped["amount"].sum())
    records = []
    for rank, row in enumerate(grouped.itertuples(index=False), start=1):
        amount = float(row.amount)
        records.append(
            {
                "organization": str(getattr(row, organization_column)),
                "amount": amount,
                "amount_display": format_dollars(amount),
                "share_of_total": amount / total if total else None,
                "rank": rank,
            }
        )
    return records


def aggregate_q3_site_distribution(site_splits: pd.DataFrame) -> list[dict[str, Any]]:
    """Aggregate and rank Federal Site Splits funding by site."""
    site_column = "site_planex" if "site_planex" in site_splits.columns else "site_name"
    if site_column not in site_splits.columns:
        return []
    working = site_splits.copy()
    working[site_column] = working[site_column].fillna("Unspecified site")
    grouped = working.groupby(site_column, dropna=False)[AMOUNT_COLUMN].sum().reset_index(name="amount")
    grouped = grouped.sort_values("amount", ascending=False)
    total = float(grouped["amount"].sum())
    records = []
    for rank, row in enumerate(grouped.itertuples(index=False), start=1):
        amount = float(row.amount)
        records.append(
            {
                "site": str(getattr(row, site_column)),
                "amount": amount,
                "amount_display": format_dollars(amount),
                "share_of_total": amount / total if total else None,
                "rank": rank,
            }
        )
    return records


def aggregate_q4_above_baseline_requests(crosscuts: pd.DataFrame) -> list[dict[str, Any]]:
    """Aggregate, rank, and calculate Pareto shares for ROT/UFR program requests."""
    if "program_request" not in crosscuts.columns:
        return []
    working = crosscuts.loc[crosscuts["funding_level_normalized"].isin(["ROT", "UFR"])].copy()
    working["program_request"] = working["program_request"].fillna("Unspecified program request")
    grouped = working.groupby("program_request", dropna=False)[AMOUNT_COLUMN].sum().reset_index(name="amount")
    grouped = grouped.sort_values("amount", ascending=False)
    total = float(grouped["amount"].sum())
    cumulative = 0.0
    records = []
    for rank, row in enumerate(grouped.itertuples(index=False), start=1):
        amount = float(row.amount)
        cumulative += amount
        records.append(
            {
                "program_request": str(row.program_request),
                "amount": amount,
                "amount_display": format_dollars(amount),
                "share_of_above_baseline": amount / total if total else None,
                "cumulative_share": cumulative / total if total else None,
                "rank": rank,
            }
        )
    return records


def calculate_q6_reconciliation(
    crosscuts: pd.DataFrame, site_splits: pd.DataFrame
) -> tuple[list[dict[str, Any]], dict[str, float | None]]:
    """Compare Pit Production totals by funding level across the two required layers."""
    crosscuts_grouped = crosscuts.groupby("funding_level_normalized")[AMOUNT_COLUMN].sum()
    sites_grouped = site_splits.groupby("funding_level_normalized")[AMOUNT_COLUMN].sum()
    levels = sorted(
        set(crosscuts_grouped.index).union(sites_grouped.index),
        key=lambda level: (FUNDING_LEVEL_ORDER.get(level, 99), level),
    )
    records = []
    for level in levels:
        crosscuts_amount = float(crosscuts_grouped.get(level, 0.0))
        site_splits_amount = float(sites_grouped.get(level, 0.0))
        variance = site_splits_amount - crosscuts_amount
        records.append(
            {
                "funding_level": level,
                "federal_crosscuts_amount": crosscuts_amount,
                "federal_crosscuts_display": format_dollars(crosscuts_amount),
                "federal_site_splits_amount": site_splits_amount,
                "federal_site_splits_display": format_dollars(site_splits_amount),
                "variance_amount": variance,
                "variance_display": format_dollars(variance),
                "variance_percent": variance / crosscuts_amount if crosscuts_amount else None,
            }
        )
    crosscuts_total = float(crosscuts[AMOUNT_COLUMN].sum())
    site_splits_total = float(site_splits[AMOUNT_COLUMN].sum())
    return records, {
        "federal_crosscuts_total": crosscuts_total,
        "federal_site_splits_total": site_splits_total,
        "variance_amount": site_splits_total - crosscuts_total,
        "variance_percent": (site_splits_total - crosscuts_total) / crosscuts_total
        if crosscuts_total
        else None,
    }


def _source_row_lineage(df: pd.DataFrame) -> dict[str, Any]:
    """Return a bounded list of lineage identifiers without publishing source rows."""
    identifiers = df.get("source_row_id", pd.Series(dtype="string")).dropna().astype(str).tolist()
    return {
        "source_row_id_sample": identifiers[:LINEAGE_SAMPLE_LIMIT],
        "lineage_truncated": len(identifiers) > LINEAGE_SAMPLE_LIMIT,
        "source_row_id_count": len(identifiers),
    }


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 of the source file for payload auditability."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_commit(project_root: Path) -> str | None:
    """Return the short git commit when the project is in a git checkout."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _summary_for_q1(data: list[dict[str, Any]]) -> str:
    total = sum(row["amount"] for row in data)
    level_totals: dict[str, float] = {}
    for row in data:
        level_totals[row["funding_level"]] = level_totals.get(row["funding_level"], 0.0) + row["amount"]
    parts = ", ".join(
        f"{level} {format_dollars(amount)}" for level, amount in sorted(level_totals.items())
    )
    return (
        f"Federal Crosscuts programs {format_dollars(total)} for Pit Production across the selected years "
        f"({parts})."
        if data
        else "No Federal Crosscuts Pit Production rows matched the selected scenario."
    )


def _summary_for_ranked_data(
    data: list[dict[str, Any]], label_key: str, total_label: str, source_name: str
) -> str:
    if not data:
        return f"No {source_name} Pit Production rows were available for this ranking."
    leader = data[0]
    share = leader["share_of_total"]
    share_display = f"{share:.1%}" if share is not None else "an unavailable share"
    return (
        f"{leader[label_key]} is the largest {total_label}, with {leader['amount_display']} "
        f"({share_display} of the {source_name} total)."
    )


def _summary_for_q4(data: list[dict[str, Any]]) -> str:
    if not data:
        return "No ROT or UFR Pit Production program requests matched the selected scenario."
    leader = data[0]
    total = sum(row["amount"] for row in data)
    return (
        f"The leading above-baseline program request is {leader['program_request']} at "
        f"{leader['amount_display']}; all ROT and UFR requests total {format_dollars(total)}."
    )


def _summary_for_q5(data: list[dict[str, Any]]) -> str:
    evaluated = [row for row in data if row["status"] == "evaluated" and row["row_count"] > 0]
    high = [row for row in evaluated if row["severity"] in {"high", "critical"}]
    if not evaluated:
        return "No populated deterministic quality findings were produced for the selected rows."
    return (
        f"{len(evaluated)} deterministic finding categories have affected rows; "
        f"{len(high)} are high-severity review triggers. Findings identify review targets, not confirmed errors."
    )


def _summary_for_q6(summary: Mapping[str, float | None]) -> str:
    variance = summary["variance_amount"]
    if variance is None:
        return "Reconciliation could not be calculated because source totals were unavailable."
    direction = "higher" if variance > 0 else "lower" if variance < 0 else "equal"
    return (
        "Federal Site Splits are "
        f"{direction} than Federal Crosscuts by {format_dollars(abs(variance))} for Pit Production. "
        "The variance is a reconciliation review trigger; the two layers have different analytic grain."
    )


def _make_payload(
    *,
    metadata: BuildMetadata,
    question_id: str,
    chart_type: str,
    chart_title: str,
    metric_definition: str,
    source_submission_type: str,
    row_filter: Mapping[str, Any],
    grouping_columns: list[str],
    value_column: str,
    record_count: int,
    data: list[dict[str, Any]],
    summary: str,
    limitations: list[str],
    lineage: Mapping[str, Any],
    metric_cards: list[dict[str, Any]],
    ontology_node_ids: list[str],
) -> dict[str, Any]:
    """Build one chart-ready payload with required citation and lineage metadata."""
    chart_id = f"{DASHBOARD_ID}_{question_id}"
    traceability = {
        "chart_id": chart_id,
        "dashboard_id": DASHBOARD_ID,
        "question_text": QUESTION_TEXT[question_id],
        "source_file": metadata.source_file,
        "source_file_sha256": metadata.source_file_sha256,
        "source_submission_type": source_submission_type,
        "row_filter": dict(row_filter),
        "metric_definition": metric_definition,
        "grouping_columns": grouping_columns,
        "value_column": value_column,
        "generated_at": metadata.generated_at,
        "record_count": record_count,
        "limitations": limitations,
        "lineage": dict(lineage),
        "ontology_node_ids": ontology_node_ids,
    }
    return {
        "schema_version": "1.0",
        "chart_id": chart_id,
        "dashboard_id": DASHBOARD_ID,
        "question_id": question_id,
        "question_text": QUESTION_TEXT[question_id],
        "chart_type": chart_type,
        "chart_title": chart_title,
        "metric_definition": metric_definition,
        "plain_language_summary": summary,
        "metric_cards": metric_cards,
        "data": data,
        "traceability": traceability,
        "build": {
            "pipeline_version": PIPELINE_VERSION,
            "git_commit": metadata.git_commit,
        },
    }


def _quality_records(findings: list[QualityFinding]) -> list[dict[str, Any]]:
    """Serialize quality findings for a table while keeping only lineage identifiers."""
    return [
        {
            "rule_id": finding.rule_id,
            "severity": finding.severity,
            "status": finding.status,
            "title": finding.title,
            "source_submission_type": finding.source_submission_type,
            "row_count": finding.row_count,
            "affected_dollars": finding.affected_dollars,
            "affected_dollars_display": format_dollars(finding.affected_dollars),
            "details": finding.details,
            "source_row_id_sample": list(finding.source_row_ids),
        }
        for finding in findings
    ]


def _node_id(node_type: str, value: str) -> str:
    """Create a stable, readable identifier for a dashboard ontology node."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return f"{node_type.casefold()}:{slug or 'unspecified'}"


def build_dashboard_01_graph(payloads: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Build a lightweight, aggregate-focused ontology graph for Dashboard 1 RAG grounding."""
    nodes: dict[str, dict[str, str]] = {}
    edges: list[dict[str, str]] = []

    def add_node(node_id: str, node_type: str, label: str) -> None:
        nodes.setdefault(node_id, {"id": node_id, "node_type": node_type, "label": label})

    def add_edge(source: str, target: str, edge_type: str) -> None:
        edge = {"source": source, "target": target, "edge_type": edge_type}
        if edge not in edges:
            edges.append(edge)

    dashboard_node = _node_id("Dashboard", DASHBOARD_ID)
    integration_area_node = _node_id("IntegrationArea", INTEGRATION_AREA)
    source_file = str(payloads["q1"]["traceability"]["source_file"])
    source_node = _node_id("SourceFile", source_file)
    add_node(dashboard_node, "Dashboard", DASHBOARD_TITLE)
    add_node(integration_area_node, "IntegrationArea", INTEGRATION_AREA)
    add_node(source_node, "SourceFile", source_file)

    dimension_edges = {
        "q1": [("funding_level", "FundingLevel", "funding_line_grouped_by_funding_level"), ("fiscal_year", "FiscalYear", "funding_line_grouped_by_fiscal_year")],
        "q2": [("organization", "Organization", "funding_line_grouped_by_organization")],
        "q3": [("site", "Site", "funding_line_grouped_by_site")],
        "q4": [("program_request", "ProgramRequest", "funding_line_grouped_by_program_request")],
    }
    for question_id, payload in payloads.items():
        chart_id = str(payload["chart_id"])
        question_node = _node_id("Question", chart_id)
        chart_node = _node_id("Chart", chart_id)
        metric_node = _node_id("Metric", chart_id)
        add_node(question_node, "Question", str(payload["question_text"]))
        add_node(chart_node, "Chart", str(payload["chart_title"]))
        add_node(metric_node, "Metric", str(payload["metric_definition"]))
        add_edge(dashboard_node, question_node, "dashboard_has_question")
        add_edge(question_node, chart_node, "question_answered_by_chart")
        add_edge(chart_node, metric_node, "chart_uses_metric")
        add_edge(metric_node, source_node, "metric_derived_from_source_file")
        add_edge(chart_node, integration_area_node, "chart_filtered_to_integration_area")
        for submission_type in str(payload["traceability"]["source_submission_type"]).split(" and "):
            submission_node = _node_id("SubmissionType", submission_type)
            add_node(submission_node, "SubmissionType", submission_type)
            add_edge(metric_node, submission_node, "metric_uses_submission_type")
        for field, node_type, edge_type in dimension_edges.get(question_id, []):
            for row in payload["data"]:
                value = row.get(field)
                if value is None:
                    continue
                node_id = _node_id(node_type, str(value))
                add_node(node_id, node_type, str(value))
                add_edge(metric_node, node_id, edge_type)
        if question_id == "q5":
            for finding in payload["data"]:
                finding_id = _node_id("Finding", str(finding["rule_id"]))
                add_node(finding_id, "Finding", str(finding["title"]))
                add_edge(finding_id, chart_node, "finding_supported_by_chart")

    return {
        "schema_version": "1.0",
        "graph_id": f"{DASHBOARD_ID}_graph",
        "dashboard_id": DASHBOARD_ID,
        "nodes": sorted(nodes.values(), key=lambda node: node["id"]),
        "edges": sorted(edges, key=lambda edge: (edge["source"], edge["edge_type"], edge["target"])),
    }


def _json_default(value: object) -> object:
    """Convert common dataframe/path values to JSON-compatible primitives."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        return float(value)
    if pd.isna(value):
        return None
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write formatted JSON with parent directories created as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, default=_json_default)
        handle.write("\n")


def _write_rag_context(path: Path, payloads: Mapping[str, Mapping[str, Any]]) -> None:
    """Write compact, aggregate-only JSONL retrieval packets for each dashboard question."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for question_id in sorted(payloads):
            payload = payloads[question_id]
            traceability = payload["traceability"]
            record = {
                "dashboard_id": DASHBOARD_ID,
                "question_id": question_id,
                "chart_id": payload["chart_id"],
                "question_text": payload["question_text"],
                "metric_definition": payload["metric_definition"],
                "plain_language_summary": payload["plain_language_summary"],
                "source_filter": traceability["row_filter"],
                "source_submission_type": traceability["source_submission_type"],
                "chart_payload_id": payload["chart_id"],
                "ontology_node_ids": traceability["ontology_node_ids"],
                "limitations": traceability["limitations"],
            }
            json.dump(record, handle, ensure_ascii=False, default=_json_default)
            handle.write("\n")


def prepare_asksage_chart_summary_request(chart_payload: Mapping[str, Any]) -> dict[str, Any]:
    """Prepare a safe, evidence-bounded AskSage chart-summary request.

    This returns request arguments only; it does not read credentials or make a
    network call. The payload includes aggregate values and lineage identifiers,
    never raw FORMEX rows.
    """
    traceability = chart_payload["traceability"]
    evidence = {
        "chart_id": chart_payload["chart_id"],
        "question_text": chart_payload["question_text"],
        "metric_definition": chart_payload["metric_definition"],
        "plain_language_summary": chart_payload["plain_language_summary"],
        "source_filter": traceability["row_filter"],
        "source_submission_type": traceability["source_submission_type"],
        "limitations": traceability["limitations"],
        "ontology_node_ids": traceability["ontology_node_ids"],
    }
    return {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a CEPE program-review analyst assistant. Answer only from the supplied "
                    "Dashboard 1 evidence. Distinguish observed data from interpretation, state "
                    "limitations, and cite the chart ID. Return JSON with answer, key_observations, "
                    "review_triggers, limitations, and citations."
                ),
            },
            {"role": "user", "content": json.dumps(evidence, ensure_ascii=False)},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }


def request_asksage_chart_summary(
    client: AskSageClient, chart_payload: Mapping[str, Any]
) -> dict[str, Any]:
    """Submit a prepared chart-summary request through the approved client abstraction."""
    request = prepare_asksage_chart_summary_request(chart_payload)
    messages = request.pop("messages")
    return client.chat_completion(messages, **request)


def build_dashboard_01_payloads(project_root: Path | None = None) -> dict[str, Any]:
    """Build all static Dashboard 1 payload, RAG-context, and ontology artifacts.

    The function locates one FORMEX input, normalizes it, applies explicit scenario
    and submission-layer filters, and exports aggregate data beneath ``data/``.
    """
    root = (project_root or project_root_from_module()).resolve()
    formex_path = find_formex_csv(root)
    settings = load_settings(root / "config" / "settings.yaml")
    prepared = prepare_formex_dataframe(load_formex(formex_path))
    selected_scenario = select_scenario(prepared, settings.project.default_scenario)
    crosscuts = filter_pit_production(
        prepared,
        CROSSCUTS_SUBMISSION_TYPE,
        scenario=selected_scenario,
    )
    site_splits = filter_pit_production(
        prepared,
        SITE_SPLITS_SUBMISSION_TYPE,
        scenario=selected_scenario,
    )
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    metadata = BuildMetadata(
        generated_at=generated_at,
        source_file=str(formex_path.relative_to(root)).replace("\\", "/"),
        source_file_sha256=_sha256_file(formex_path),
        scenario=selected_scenario,
        git_commit=_git_commit(root),
    )
    base_filter = {
        "program_int_area": INTEGRATION_AREA,
        "scenario": selected_scenario,
    }
    crosscuts_filter = {**base_filter, "submission_type": CROSSCUTS_SUBMISSION_TYPE}
    site_splits_filter = {**base_filter, "submission_type": SITE_SPLITS_SUBMISSION_TYPE}
    both_filter = {
        **base_filter,
        "submission_type": [CROSSCUTS_SUBMISSION_TYPE, SITE_SPLITS_SUBMISSION_TYPE],
    }

    q1_data = aggregate_q1_funding_by_year_level(crosscuts)
    q2_data = aggregate_q2_funding_by_organization(crosscuts)
    q3_data = aggregate_q3_site_distribution(site_splits)
    q4_data = aggregate_q4_above_baseline_requests(crosscuts)
    q6_data, q6_summary = calculate_q6_reconciliation(crosscuts, site_splits)
    quality_findings = evaluate_dashboard_01_quality_rules(crosscuts, site_splits)
    quality_findings.append(
        reconciliation_finding(
            float(q6_summary["federal_crosscuts_total"] or 0.0),
            float(q6_summary["federal_site_splits_total"] or 0.0),
        )
    )
    q5_data = _quality_records(quality_findings)

    common_limitations = [
        "FORMEX submission types are overlapping views and are not additive.",
        "PLANEX and COSTEX are FY2026 context and are not reconciled to this FY2028-FY2032 dashboard.",
    ]
    q3_total = sum(row["amount"] for row in q3_data)
    q3_top_two_share = sum(row["share_of_total"] or 0.0 for row in q3_data[:2])
    q5_evaluated = [row for row in q5_data if row["status"] == "evaluated"]
    q5_high_count = sum(row["severity"] in {"high", "critical"} for row in q5_evaluated)

    payloads: dict[str, dict[str, Any]] = {
        "q1": _make_payload(
            metadata=metadata,
            question_id="q1",
            chart_type="stacked_bar",
            chart_title="Pit Production funding by fiscal year and funding level",
            metric_definition=(
                "Sum of FORMEX Formulated Measure by fiscal year and normalized funding level, "
                "filtered to Pit Production Federal Crosscuts."
            ),
            source_submission_type=CROSSCUTS_SUBMISSION_TYPE,
            row_filter=crosscuts_filter,
            grouping_columns=["fiscal_year", "funding_level"],
            value_column=AMOUNT_COLUMN,
            record_count=len(crosscuts),
            data=q1_data,
            summary=_summary_for_q1(q1_data),
            limitations=common_limitations,
            lineage=_source_row_lineage(crosscuts),
            metric_cards=[
                {
                    "label": "Five-year programmed funding",
                    "value": sum(row["amount"] for row in q1_data),
                    "display": format_dollars(sum(row["amount"] for row in q1_data)),
                }
            ],
            ontology_node_ids=[_node_id("Chart", f"{DASHBOARD_ID}_q1")],
        ),
        "q2": _make_payload(
            metadata=metadata,
            question_id="q2",
            chart_type="ranked_horizontal_bar",
            chart_title="Pit Production funding by organization",
            metric_definition=(
                "Sum of FORMEX Formulated Measure by Sub Office Number, filtered to Pit Production "
                "Federal Crosscuts."
            ),
            source_submission_type=CROSSCUTS_SUBMISSION_TYPE,
            row_filter=crosscuts_filter,
            grouping_columns=["sub_office_number"],
            value_column=AMOUNT_COLUMN,
            record_count=len(crosscuts),
            data=q2_data,
            summary=_summary_for_ranked_data(q2_data, "organization", "owner", "Federal Crosscuts"),
            limitations=common_limitations
            + ["Organization ownership is represented by FORMEX Sub Office Number."],
            lineage=_source_row_lineage(crosscuts),
            metric_cards=[
                {
                    "label": "Organizations with Pit Production funding",
                    "value": len(q2_data),
                    "display": str(len(q2_data)),
                }
            ],
            ontology_node_ids=[_node_id("Chart", f"{DASHBOARD_ID}_q2")],
        ),
        "q3": _make_payload(
            metadata=metadata,
            question_id="q3",
            chart_type="ranked_horizontal_bar",
            chart_title="Pit Production funding by site",
            metric_definition=(
                "Sum of FORMEX Formulated Measure by Site - PlanEX, filtered to Pit Production "
                "Federal Site Splits."
            ),
            source_submission_type=SITE_SPLITS_SUBMISSION_TYPE,
            row_filter=site_splits_filter,
            grouping_columns=["site_planex"],
            value_column=AMOUNT_COLUMN,
            record_count=len(site_splits),
            data=q3_data,
            summary=_summary_for_ranked_data(q3_data, "site", "site", "Federal Site Splits"),
            limitations=common_limitations
            + ["Site totals use Federal Site Splits and should not replace Federal Crosscuts portfolio totals."],
            lineage=_source_row_lineage(site_splits),
            metric_cards=[
                {
                    "label": "Site Split funding",
                    "value": q3_total,
                    "display": format_dollars(q3_total),
                },
                {
                    "label": "Top two site share",
                    "value": q3_top_two_share,
                    "display": f"{q3_top_two_share:.1%}",
                },
            ],
            ontology_node_ids=[_node_id("Chart", f"{DASHBOARD_ID}_q3")],
        ),
        "q4": _make_payload(
            metadata=metadata,
            question_id="q4",
            chart_type="pareto_ranked_bar",
            chart_title="Above-baseline Pit Production program requests",
            metric_definition=(
                "Sum of FORMEX Formulated Measure by Program Request for normalized ROT and UFR rows, "
                "filtered to Pit Production Federal Crosscuts."
            ),
            source_submission_type=CROSSCUTS_SUBMISSION_TYPE,
            row_filter={**crosscuts_filter, "funding_level": ["ROT", "UFR"]},
            grouping_columns=["program_request"],
            value_column=AMOUNT_COLUMN,
            record_count=int(crosscuts["funding_level_normalized"].isin(["ROT", "UFR"]).sum()),
            data=q4_data,
            summary=_summary_for_q4(q4_data),
            limitations=common_limitations
            + ["Rows without Program Request are grouped as 'Unspecified program request' and separately flagged in Q5."],
            lineage=_source_row_lineage(
                crosscuts.loc[crosscuts["funding_level_normalized"].isin(["ROT", "UFR"])]
            ),
            metric_cards=[
                {
                    "label": "ROT and UFR funding",
                    "value": sum(row["amount"] for row in q4_data),
                    "display": format_dollars(sum(row["amount"] for row in q4_data)),
                }
            ],
            ontology_node_ids=[_node_id("Chart", f"{DASHBOARD_ID}_q4")],
        ),
        "q5": _make_payload(
            metadata=metadata,
            question_id="q5",
            chart_type="quality_scorecard_and_table",
            chart_title="Pit Production deterministic data-quality findings",
            metric_definition=(
                "Column-tolerant deterministic completeness, priority, acquisition, negative-dollar, and "
                "traceability checks on Pit Production Federal Crosscuts and Federal Site Splits."
            ),
            source_submission_type=f"{CROSSCUTS_SUBMISSION_TYPE} and {SITE_SPLITS_SUBMISSION_TYPE}",
            row_filter=both_filter,
            grouping_columns=["rule_id", "source_submission_type"],
            value_column=f"{AMOUNT_COLUMN} affected dollars",
            record_count=len(crosscuts) + len(site_splits),
            data=q5_data,
            summary=_summary_for_q5(q5_data),
            limitations=common_limitations
            + ["Missing optional FORMEX fields are reported as not evaluated; findings are review triggers, not confirmed errors."],
            lineage={
                "federal_crosscuts": _source_row_lineage(crosscuts),
                "federal_site_splits": _source_row_lineage(site_splits),
            },
            metric_cards=[
                {
                    "label": "Rules evaluated",
                    "value": len(q5_evaluated),
                    "display": str(len(q5_evaluated)),
                },
                {
                    "label": "High-severity review triggers",
                    "value": q5_high_count,
                    "display": str(q5_high_count),
                },
            ],
            ontology_node_ids=[_node_id("Chart", f"{DASHBOARD_ID}_q5")],
        ),
        "q6": _make_payload(
            metadata=metadata,
            question_id="q6",
            chart_type="reconciliation_variance_table",
            chart_title="Pit Production Crosscuts-to-Site-Splits reconciliation",
            metric_definition=(
                "Federal Site Splits Formulated Measure minus Federal Crosscuts Formulated Measure by "
                "normalized funding level, filtered to Pit Production."
            ),
            source_submission_type=f"{CROSSCUTS_SUBMISSION_TYPE} and {SITE_SPLITS_SUBMISSION_TYPE}",
            row_filter=both_filter,
            grouping_columns=["funding_level"],
            value_column=AMOUNT_COLUMN,
            record_count=len(crosscuts) + len(site_splits),
            data=q6_data,
            summary=_summary_for_q6(q6_summary),
            limitations=common_limitations
            + ["Reconciliation compares two overlapping submission layers with different intended analytic grain; a variance requires analyst review."],
            lineage={
                "federal_crosscuts": _source_row_lineage(crosscuts),
                "federal_site_splits": _source_row_lineage(site_splits),
            },
            metric_cards=[
                {
                    "label": "Federal Crosscuts total",
                    "value": q6_summary["federal_crosscuts_total"],
                    "display": format_dollars(q6_summary["federal_crosscuts_total"]),
                },
                {
                    "label": "Site Splits variance",
                    "value": q6_summary["variance_amount"],
                    "display": format_dollars(q6_summary["variance_amount"]),
                },
            ],
            ontology_node_ids=[_node_id("Chart", f"{DASHBOARD_ID}_q6")],
        ),
    }

    output_dir = root / "data" / "curated" / "dashboard_payloads" / DASHBOARD_ID
    payload_files = {
        "q1": "q1_funding_by_year_level.json",
        "q2": "q2_funding_by_organization.json",
        "q3": "q3_site_distribution.json",
        "q4": "q4_above_baseline_program_requests.json",
        "q5": "q5_data_quality_findings.json",
        "q6": "q6_crosscuts_site_splits_reconciliation.json",
    }
    for question_id, filename in payload_files.items():
        _write_json(output_dir / filename, payloads[question_id])

    graph = build_dashboard_01_graph(payloads)
    _write_json(root / "data" / "ontology" / f"{DASHBOARD_ID}_graph.json", graph)
    _write_rag_context(
        root / "data" / "curated" / "rag_chunks" / DASHBOARD_ID / "dashboard_01_context.jsonl",
        payloads,
    )
    manifest = {
        "schema_version": "1.0",
        "dashboard_id": DASHBOARD_ID,
        "title": DASHBOARD_TITLE,
        "generated_at": generated_at,
        "pipeline_version": PIPELINE_VERSION,
        "git_commit": metadata.git_commit,
        "source_file": metadata.source_file,
        "source_file_sha256": metadata.source_file_sha256,
        "filters": base_filter,
        "payloads": [
            {
                "question_id": question_id,
                "chart_id": payloads[question_id]["chart_id"],
                "question_text": QUESTION_TEXT[question_id],
                "file": payload_files[question_id],
                "record_count": payloads[question_id]["traceability"]["record_count"],
            }
            for question_id in payload_files
        ],
        "limitations": common_limitations,
        "rag_context_file": "data/curated/rag_chunks/dashboard_01_pit_production/dashboard_01_context.jsonl",
        "ontology_graph_file": "data/ontology/dashboard_01_pit_production_graph.json",
    }
    _write_json(output_dir / "manifest.json", manifest)
    LOGGER.info("Generated Dashboard 1 payloads in %s", output_dir)
    return manifest


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI entry point.
    generated_manifest = build_dashboard_01_payloads()
    print(
        "Generated Dashboard 1 payloads at "
        "data/curated/dashboard_payloads/dashboard_01_pit_production "
        f"({generated_manifest['generated_at']})."
    )
