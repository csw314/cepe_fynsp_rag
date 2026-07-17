"""Shared validated, aggregate-only artifact infrastructure for all dashboards."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import UTC, datetime
from numbers import Integral, Real
from pathlib import Path
from typing import Any, Literal, Mapping

import pandas as pd

from cepe_fynsp.config import load_settings
from cepe_fynsp.dashboards.dashboard_01_pit_production import (
    AMOUNT_COLUMN,
    CROSSCUTS_SUBMISSION_TYPE,
    INTEGRATION_AREA,
    SITE_SPLITS_SUBMISSION_TYPE,
    filter_pit_production,
    find_formex_csv,
    format_dollars,
    prepare_formex_dataframe,
    project_root_from_module,
    select_scenario,
)
from cepe_fynsp.etl.contracts import load_contract, validate_dataframe
from cepe_fynsp.etl.financial import financial_completeness
from cepe_fynsp.etl.loaders import load_formex
from cepe_fynsp.schemas import (
    SCHEMA_VERSION,
    ColumnSchema,
    DashboardManifest,
    DashboardQuestionPayload,
    ManifestEntry,
    MetricCard,
    NarrativeRecord,
    QualitySummary,
    RagRecord,
    VisualizationSpec,
)

LINEAGE_SAMPLE_LIMIT = 250
COMMON_LIMITATIONS = [
    "FORMEX submission types are overlapping views and are not additive.",
    "PLANEX and COSTEX are execution context and are not directly reconciled to FY2028-FY2032 FORMEX without an approved crosswalk.",
]


def blank_mask(series: pd.Series) -> pd.Series:
    """Return a mask for null, blank, and common blank-like text values."""
    values = series.astype("string").str.strip().str.casefold()
    return values.isna() | values.isin(["", "<na>", "n/a", "na", "nan", "none", "null"])


def display_value(value: object, fallback: str) -> str:
    """Return a readable value without allowing null-like bucket labels."""
    if pd.isna(value) or str(value).strip().casefold() in {"", "<na>", "nan", "none"}:
        return fallback
    return str(value).strip()


def source_row_lineage(df: pd.DataFrame) -> dict[str, Any]:
    """Return bounded identifiers/hashes without exporting source record content."""
    record_ids = (
        df.get("source_record_id", df.get("source_row_id", pd.Series(dtype="string")))
        .dropna()
        .astype(str)
        .tolist()
    )
    content_hashes = (
        df.get("source_content_hash", df.get("source_row_hash", pd.Series(dtype="string")))
        .dropna()
        .astype(str)
        .tolist()
    )
    location_ids = (
        df.get("source_location_id", pd.Series(dtype="string")).dropna().astype(str).tolist()
    )
    return {
        "source_record_id_sample": record_ids[:LINEAGE_SAMPLE_LIMIT],
        "source_content_hash_sample": content_hashes[:LINEAGE_SAMPLE_LIMIT],
        "source_location_id_sample": location_ids[:LINEAGE_SAMPLE_LIMIT],
        "source_row_id_sample": record_ids[:LINEAGE_SAMPLE_LIMIT],
        "lineage_truncated": len(record_ids) > LINEAGE_SAMPLE_LIMIT,
        "source_row_id_count": len(record_ids),
    }


def node_id(node_type: str, value: str) -> str:
    """Create a readable, collision-resistant ontology identifier."""
    normalized = re.sub(r"\s+", " ", value.strip())
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.casefold()).strip("-") or "unspecified"
    suffix = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:10]
    return f"{node_type.casefold()}:{slug}:{suffix}"


def sha256_file(path: Path) -> str:
    """Return the SHA-256 for a source file used by a payload build."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit(project_root: Path) -> str | None:
    """Return the git commit when available without making it a build requirement."""
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


def _health_status(completeness: Mapping[str, Any]) -> Literal["GREEN", "AMBER", "RED"]:
    """Assign deterministic traffic-light status from financial parse outcomes."""
    if int(completeness.get("invalid_amount_row_count", 0)):
        return "RED"
    if int(completeness.get("blank_amount_row_count", 0)) or int(
        completeness.get("excluded_amount_row_count", 0)
    ):
        return "AMBER"
    return "GREEN"


def load_pit_production_layers(
    project_root: Path | None = None,
) -> tuple[Path, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Load/validate FORMEX and return explicit Crosscuts and Site Splits slices."""
    root = (project_root or project_root_from_module()).resolve()
    formex_path = find_formex_csv(root)
    settings = load_settings(project_root=root)
    prepared = prepare_formex_dataframe(load_formex(formex_path))
    contract = load_contract("formex", root)
    validation = validate_dataframe(prepared, contract)
    scenario = select_scenario(prepared, settings.project.default_scenario)
    crosscuts = filter_pit_production(prepared, CROSSCUTS_SUBMISSION_TYPE, scenario=scenario)
    site_splits = filter_pit_production(prepared, SITE_SPLITS_SUBMISSION_TYPE, scenario=scenario)
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    crosscuts_health = financial_completeness(crosscuts)
    site_splits_health = financial_completeness(site_splits)
    combined_health = financial_completeness(pd.concat([crosscuts, site_splits], ignore_index=True))
    fiscal_years = sorted(
        int(value) for value in prepared["fiscal_year_number"].dropna().unique().tolist()
    )
    data_health = {
        "source_dataset_identity": "FORMEX",
        "source_file": str(formex_path.relative_to(root)).replace("\\", "/"),
        "source_file_date": datetime.fromtimestamp(formex_path.stat().st_mtime, tz=UTC)
        .date()
        .isoformat(),
        "dashboard_generation_date": generated_at,
        "scenario": scenario,
        "submission_layer": [CROSSCUTS_SUBMISSION_TYPE, SITE_SPLITS_SUBMISSION_TYPE],
        "fiscal_year_scope": fiscal_years,
        "source_rows_considered": len(prepared),
        "rows_included": len(crosscuts) + len(site_splits),
        "rows_excluded": len(prepared) - len(crosscuts) - len(site_splits),
        "blank_monetary_values": int(str(combined_health["blank_amount_row_count"])),
        "invalid_monetary_values": int(str(combined_health["invalid_amount_row_count"])),
        "quality_check_summary": "Executable FORMEX contract and amount parsing passed before aggregation.",
        "reconciliation_status": "evaluated by Dashboard 1 Q6",
        "overall_status": _health_status(combined_health),
        "status_rule": (
            "RED for invalid monetary values; AMBER for blank/excluded monetary values; GREEN when all included canonical amounts are valid."
        ),
    }
    metadata = {
        "project_root": root,
        "generated_at": generated_at,
        "source_file": data_health["source_file"],
        "source_file_sha256": sha256_file(formex_path),
        "scenario": scenario,
        "git_commit": git_commit(root),
        "base_filter": {"program_int_area": INTEGRATION_AREA, "scenario": scenario},
        "contract_version": contract.contract_version,
        "contract_validation_status": validation.status,
        "data_health": data_health,
        "layer_health": {
            CROSSCUTS_SUBMISSION_TYPE: crosscuts_health,
            SITE_SPLITS_SUBMISSION_TYPE: site_splits_health,
            f"{CROSSCUTS_SUBMISSION_TYPE} and {SITE_SPLITS_SUBMISSION_TYPE}": combined_health,
        },
    }
    return root, crosscuts, site_splits, metadata


def _column_format(
    key: str,
) -> Literal["text", "integer", "number", "currency", "percentage", "date", "status"]:
    """Choose a transparent display format from a generated field's semantic name."""
    lowered = key.casefold()
    if "date" in lowered:
        return "date"
    if any(token in lowered for token in ("amount", "dollars", "exposure", "materiality")):
        return "currency"
    if any(token in lowered for token in ("percentage", "percent", "share", "rate", "score")):
        return "percentage"
    if lowered.endswith("count") or lowered in {"rank", "row_count", "section_number"}:
        return "integer"
    if any(token in lowered for token in ("status", "severity", "flag", "trigger")):
        return "status"
    return "text"


def _label(key: str) -> str:
    """Return a consistent human-readable field label."""
    acronyms = {"wbs": "WBS", "bnr": "BNR", "rot": "ROT", "ufr": "UFR", "id": "ID"}
    return " ".join(acronyms.get(part, part.capitalize()) for part in key.split("_"))


def _column_schemas(data: list[dict[str, Any]]) -> tuple[ColumnSchema, ...]:
    """Build an explicit all-column schema without arbitrary truncation."""
    keys: list[str] = []
    excluded = {
        "source_row_id_sample",
        "source_record_id_sample",
        "source_content_hash_sample",
        "source_location_id_sample",
    }
    for row in data:
        for key in row:
            if key not in keys and key not in excluded and not key.endswith("_display"):
                keys.append(key)
    return tuple(
        ColumnSchema(key=key, label=_label(key), format=_column_format(key)) for key in keys
    )


def _first_key(data: list[dict[str, Any]], candidates: tuple[str, ...]) -> str | None:
    """Return the first declared semantic field available in aggregate rows."""
    available = {key for row in data for key in row}
    return next((key for key in candidates if key in available), None)


def _visualization(chart_type: str, data: list[dict[str, Any]], title: str) -> VisualizationSpec:
    """Map analytical chart intent to a declarative renderer contract."""
    x = _first_key(
        data,
        (
            "fiscal_year",
            "program_request",
            "acquisition_type",
            "organization",
            "site",
            "funding_level",
            "coverage_category",
            "theme",
            "rule_id",
            "section",
        ),
    )
    y = _first_key(
        data,
        (
            "amount",
            "funding_amount",
            "above_baseline",
            "percent_change",
            "traceability_score",
            "coverage_rate",
            "row_count",
            "affected_dollars",
            "materiality",
        ),
    )
    series = _first_key(
        data,
        ("funding_level", "acquisition_type", "site", "severity", "classification"),
    )
    field_overrides: dict[str, tuple[str | None, str | None, str | None]] = {
        "site_year_heatmap_table": ("fiscal_year", "amount", "site"),
        "suboffice_site_matrix": ("organization", "amount", "site"),
        "yoy_change_table": ("fiscal_year", "dollar_change", "site"),
        "tier_funding_matrix": ("doe_priority_tier", "amount", "funding_level"),
        "priority_uniqueness_matrix": ("program_priority", "amount", "funding_level"),
        "classified_ranked_table": ("program_request", "amount", "classification"),
        "coverage_matrix": ("coverage_category", "coverage_rate", None),
        "risk_opportunity_heatmap_table": ("theme", "materiality", "severity"),
        "bubble_plot": ("doe_priority_tier", "amount", "funding_level"),
    }
    if chart_type in field_overrides:
        requested_x, requested_y, requested_series = field_overrides[chart_type]
        x = requested_x if requested_x in {key for row in data for key in row} else x
        y = requested_y if requested_y in {key for row in data for key in row} else y
        series = (
            requested_series if requested_series in {key for row in data for key in row} else None
        )
    size = _first_key(data, ("amount", "affected_dollars", "row_count"))
    color = _first_key(data, ("severity", "funding_level", "acquisition_type", "status"))
    return VisualizationSpec(
        type=chart_type,
        x=x,
        y=y,
        series=series,
        size=size if "bubble" in chart_type else None,
        color=color,
        sort=("rank",) if any("rank" in row for row in data) else (),
        format={"y": _column_format(y) if y else "text"},
        accessible_description=(
            f"{title}. The visualization uses aggregate fields {x or 'category'} and "
            f"{y or 'status'}; the complete accessible data table follows the chart."
        ),
    )


def _filter_options(data: list[dict[str, Any]]) -> dict[str, list[Any]]:
    """Expose only bounded aggregate dimensions that exist in the payload."""
    candidates = (
        "fiscal_year",
        "funding_level",
        "organization",
        "site",
        "doe_priority_tier",
        "acquisition_type",
        "severity",
    )
    options: dict[str, list[Any]] = {}
    for key in candidates:
        values = sorted(
            {row[key] for row in data if key in row and isinstance(row[key], (str, int, float))},
            key=str,
        )
        if values and len(values) <= 100:
            options[key] = values
    return options


def _completeness_for_layer(
    source_submission_type: str, metadata: Mapping[str, Any], record_count: int
) -> dict[str, Any]:
    """Return layer-specific completeness or a truthful not-evaluated fallback."""
    layer_health = metadata.get("layer_health", {})
    value = layer_health.get(source_submission_type)
    if value:
        return dict(value)
    return {
        "amount": None,
        "valid_amount_row_count": 0,
        "blank_amount_row_count": 0,
        "invalid_amount_row_count": 0,
        "excluded_amount_row_count": 0,
        "total_source_row_count": record_count,
        "completeness_percentage": None,
        "aggregate_status": "not_evaluated",
    }


def _enrich_financial_records(
    data: list[dict[str, Any]], completeness: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Ensure displayed financial aggregates disclose a status even for legacy calculations."""
    enriched: list[dict[str, Any]] = []
    for original in data:
        row = dict(original)
        financial = any(
            isinstance(value, (int, float))
            and any(
                token in key.casefold()
                for token in ("amount", "dollars", "exposure", "materiality")
            )
            for key, value in row.items()
        )
        if financial:
            row.setdefault(
                "aggregate_status", completeness.get("aggregate_status", "not_evaluated")
            )
            row.setdefault("completeness_percentage", completeness.get("completeness_percentage"))
        enriched.append(row)
    return enriched


def make_payload(
    *,
    dashboard_id: str,
    dashboard_title: str,
    question_id: str,
    question_text: str,
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
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """Create and validate one complete schema-v2 question payload."""
    chart_id = f"{dashboard_id}_{question_id}"
    effective_filter = {**dict(metadata.get("base_filter", {})), **dict(row_filter)}
    completeness = _completeness_for_layer(source_submission_type, metadata, record_count)
    enriched_data = _enrich_financial_records(data, completeness)
    status = _health_status(completeness)
    quality = QualitySummary(
        overall_status=status,
        status_rule=(
            "RED for invalid monetary values; AMBER for blank/excluded monetary values; GREEN when all included canonical amounts are valid."
        ),
        financial_completeness=dict(completeness),
        quality_check_summary="Deterministic contract and amount checks precede dashboard aggregation.",
        reconciliation_status=str(
            metadata.get("data_health", {}).get("reconciliation_status", "not evaluated")
        ),
    )
    metrics = tuple(
        MetricCard(
            label=str(card["label"]),
            value=card.get("value"),
            display=str(card.get("display", "Not available")),
            aggregate_status=str(
                card.get("aggregate_status", completeness.get("aggregate_status", "not_evaluated"))
            ),
            completeness_percentage=card.get(
                "completeness_percentage", completeness.get("completeness_percentage")
            ),
        )
        for card in metric_cards
    )
    ontology_ids = (node_id("Chart", chart_id),)
    traceability = {
        "chart_id": chart_id,
        "dashboard_id": dashboard_id,
        "source_file": metadata["source_file"],
        "source_file_sha256": metadata["source_file_sha256"],
        "source_submission_type": source_submission_type,
        "row_filter": effective_filter,
        "metric_definition": metric_definition,
        "grouping_columns": grouping_columns,
        "value_column": value_column,
        "generated_at": metadata["generated_at"],
        "record_count": record_count,
        "limitations": limitations,
        "lineage": dict(lineage),
        "ontology_node_ids": list(ontology_ids),
        "contract_version": metadata.get("contract_version", "2.0"),
        "contract_validation_status": metadata.get("contract_validation_status", "passed"),
    }
    source_metadata = (
        {
            "dataset": "FORMEX" if "FORMEX" in metric_definition else "Derived dashboard evidence",
            "source_file": metadata["source_file"],
            "source_file_sha256": metadata["source_file_sha256"],
            "submission_type": source_submission_type,
            "extract_date": metadata.get("data_health", {}).get("source_file_date"),
        },
    )
    narrative = [
        NarrativeRecord(
            origin="calculated_observation",
            text=summary,
            citations=(chart_id,),
            filter_state=effective_filter,
        )
    ]
    narrative.extend(
        NarrativeRecord(
            origin="limitation",
            text=limitation,
            citations=(chart_id,),
            filter_state=effective_filter,
        )
        for limitation in limitations[:3]
    )
    payload = DashboardQuestionPayload(
        schema_version=SCHEMA_VERSION,
        dashboard_id=dashboard_id,
        dashboard_title=dashboard_title,
        question_id=question_id,
        question_text=question_text,
        title=chart_title,
        subtitle=metric_definition,
        chart_id=chart_id,
        chart_type=chart_type,
        chart_title=chart_title,
        metrics=metrics,
        metric_cards=metrics,
        metric_definitions=(metric_definition,),
        metric_definition=metric_definition,
        data=enriched_data,
        columns=_column_schemas(enriched_data),
        visualization=_visualization(chart_type, enriched_data, chart_title),
        filter_options=_filter_options(enriched_data),
        active_filter_state=effective_filter,
        warnings=tuple(limitations),
        quality_summary=quality,
        traceability=traceability,
        source_metadata=source_metadata,
        lineage=dict(lineage),
        narrative=tuple(narrative),
        ontology_references=ontology_ids,
        generated_metadata={
            "generated_at": metadata["generated_at"],
            "pipeline_version": "dashboard_shared_v2",
            "git_commit": metadata.get("git_commit"),
        },
        source_file=str(metadata["source_file"]),
        source_submission_type=source_submission_type,
        row_filter=dict(row_filter),
        grouping_columns=tuple(grouping_columns),
        value_column=value_column,
        generated_at=str(metadata["generated_at"]),
        record_count=record_count,
        summary=summary,
        plain_language_summary=summary,
        limitations=tuple(limitations),
        build={"pipeline_version": "dashboard_shared_v2", "git_commit": metadata.get("git_commit")},
    )
    return payload.model_dump(mode="json")


def _json_default(value: object) -> object:
    """Convert dataframe/path values for JSON serialization."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        return float(value)
    if pd.isna(value):
        return None
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def write_json(path: Path, payload: Mapping[str, Any] | list[Any]) -> None:
    """Atomically write validated JSON after successful serialization."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, default=_json_default)
        handle.write("\n")
    os.replace(temporary, path)


def _lineage_values(lineage: Mapping[str, Any], key: str) -> list[str]:
    """Collect bounded lineage values from flat or per-layer structures."""
    direct = lineage.get(key)
    if isinstance(direct, list):
        return [str(value) for value in direct]
    values: list[str] = []
    for nested in lineage.values():
        if isinstance(nested, Mapping) and isinstance(nested.get(key), list):
            values.extend(str(value) for value in nested[key])
    if not values and key == "source_record_id_sample":
        return _lineage_values(lineage, "source_row_id_sample")
    return values


def write_rag_context(path: Path, payloads: Mapping[str, Mapping[str, Any]]) -> None:
    """Write validated, aggregate-only RAG packets with complete evidence references."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for question_id in sorted(payloads):
            payload = payloads[question_id]
            traceability = payload["traceability"]
            lineage = traceability.get("lineage", {})
            record = RagRecord(
                record_id=f"rag:{payload['chart_id']}",
                dashboard_id=str(payload["dashboard_id"]),
                question_id=question_id,
                question_text=str(payload["question_text"]),
                filter_state=dict(payload["active_filter_state"]),
                metric_definition=str(payload["metric_definition"]),
                calculated_values=tuple(payload.get("data", [])[:25]),
                calculated_observations=(str(payload["plain_language_summary"]),),
                quality_status=str(payload["quality_summary"]["overall_status"]),
                limitations=tuple(traceability["limitations"]),
                payload_ids=(str(payload["chart_id"]),),
                ontology_ids=tuple(traceability["ontology_node_ids"]),
                source_file_ids=(str(traceability["source_file"]),),
                source_hashes=(str(traceability["source_file_sha256"]),),
                lineage_ids=tuple(_lineage_values(lineage, "source_record_id_sample")),
                citation_labels=(f"payload:{payload['chart_id']}",),
                classification_metadata={"status": "not_applicable", "model": None},
                narrative_origin="calculated_observation",
            )
            handle.write(record.model_dump_json() + "\n")
    os.replace(temporary, path)


_DIMENSION_NODE_TYPES = {
    "funding_level": "FundingLevel",
    "fiscal_year": "FiscalYear",
    "organization": "Organization",
    "sub_office_number": "Organization",
    "site": "Site",
    "program_request": "ProgramRequest",
    "acquisition_id": "Acquisition",
    "acquisition_name": "Acquisition",
    "acquisition_type": "Acquisition",
}


def build_dashboard_graph(
    dashboard_id: str,
    dashboard_title: str,
    payloads: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Build and validate a compact collision-resistant aggregate graph."""
    nodes: dict[str, dict[str, str]] = {}
    edges: list[dict[str, str]] = []

    def add_node(identifier: str, node_type: str, label: str) -> None:
        existing = nodes.get(identifier)
        candidate = {"id": identifier, "node_type": node_type, "label": label}
        if existing is not None and existing != candidate:
            raise ValueError(f"Ontology identifier collision: {identifier}")
        nodes[identifier] = candidate

    def add_edge(source: str, target: str, edge_type: str) -> None:
        edge = {"source": source, "target": target, "edge_type": edge_type}
        if edge not in edges:
            edges.append(edge)

    dashboard_node = node_id("Dashboard", dashboard_id)
    integration_node = node_id("IntegrationArea", INTEGRATION_AREA)
    add_node(dashboard_node, "Dashboard", dashboard_title)
    add_node(integration_node, "IntegrationArea", INTEGRATION_AREA)
    for payload in payloads.values():
        chart_id = str(payload["chart_id"])
        traceability = payload["traceability"]
        question_node = node_id("Question", chart_id)
        chart_node = node_id("Chart", chart_id)
        metric_node = node_id("Metric", chart_id)
        source_node = node_id("SourceFile", str(traceability["source_file"]))
        add_node(question_node, "Question", str(payload["question_text"]))
        add_node(chart_node, "Chart", str(payload["chart_title"]))
        add_node(metric_node, "Metric", str(payload["metric_definition"]))
        add_node(source_node, "SourceFile", str(traceability["source_file"]))
        add_edge(dashboard_node, question_node, "dashboard_has_question")
        add_edge(question_node, chart_node, "question_answered_by_chart")
        add_edge(chart_node, metric_node, "chart_uses_metric")
        add_edge(metric_node, source_node, "metric_derived_from_source_file")
        add_edge(chart_node, integration_node, "chart_filtered_to_integration_area")
        for submission_type in str(traceability["source_submission_type"]).split(" and "):
            submission_node = node_id("SubmissionType", submission_type)
            add_node(submission_node, "SubmissionType", submission_type)
            add_edge(metric_node, submission_node, "metric_uses_submission_type")
        for row in payload.get("data", []):
            for field, node_type in _DIMENSION_NODE_TYPES.items():
                value = row.get(field)
                if value is None or str(value).strip() == "":
                    continue
                dimension_node = node_id(node_type, str(value))
                add_node(dimension_node, node_type, str(value))
                add_edge(metric_node, dimension_node, f"metric_grouped_by_{field}")
            finding_value = row.get("finding_id") or row.get("rule_id")
            if finding_value:
                finding_node = node_id("Finding", str(finding_value))
                # A finding can occur in both a detailed and a roll-up table.
                # Its identifier is the stable cross-payload label; titles remain
                # available in the payload records where they are evidence.
                add_node(finding_node, "Finding", str(finding_value))
                add_edge(finding_node, chart_node, "finding_supported_by_chart")
    node_ids = set(nodes)
    dangling = [
        edge for edge in edges if edge["source"] not in node_ids or edge["target"] not in node_ids
    ]
    if dangling:
        raise ValueError(f"Dashboard graph contains dangling references: {dangling[:3]}")
    return {
        "schema_version": SCHEMA_VERSION,
        "graph_id": f"{dashboard_id}_graph",
        "dashboard_id": dashboard_id,
        "nodes": sorted(nodes.values(), key=lambda item: item["id"]),
        "edges": sorted(
            edges, key=lambda item: (item["source"], item["edge_type"], item["target"])
        ),
    }


def _jsonld_from_graph(graph: Mapping[str, Any]) -> dict[str, Any]:
    """Return a lightweight JSON-LD representation of the validated graph."""
    entries: list[dict[str, Any]] = [
        {
            "@id": node["id"],
            "@type": f"cepe:{node['node_type']}",
            "rdfs:label": node["label"],
        }
        for node in graph["nodes"]
    ]
    entries.extend(
        {
            "@id": f"edge:{index}",
            "@type": "cepe:Relationship",
            "cepe:source": {"@id": edge["source"]},
            "cepe:target": {"@id": edge["target"]},
            "cepe:relationshipType": edge["edge_type"],
        }
        for index, edge in enumerate(graph["edges"], start=1)
    )
    return {
        "@context": {
            "cepe": "https://example.invalid/cepe-fynsp#",
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        },
        "@graph": entries,
    }


def write_dashboard_artifacts(
    *,
    root: Path,
    dashboard_id: str,
    dashboard_title: str,
    payloads: Mapping[str, Mapping[str, Any]],
    payload_files: Mapping[str, str],
    metadata: Mapping[str, Any],
    limitations: list[str],
    extra_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate and atomically write payloads, RAG packets, graph, JSON-LD, and manifest."""
    if set(payloads) != set(payload_files) or set(payloads) != {
        f"q{index}" for index in range(1, 7)
    }:
        raise ValueError(f"{dashboard_id} must emit each mandatory question exactly once.")
    validated_payloads = {
        question_id: DashboardQuestionPayload.model_validate(payload).model_dump(mode="json")
        for question_id, payload in payloads.items()
    }
    output_dir = root / "data" / "curated" / "dashboard_payloads" / dashboard_id
    for question_id, filename in payload_files.items():
        write_json(output_dir / filename, validated_payloads[question_id])
    graph = build_dashboard_graph(dashboard_id, dashboard_title, validated_payloads)
    graph_path = root / "data" / "ontology" / f"{dashboard_id}_graph.json"
    jsonld_path = root / "data" / "ontology" / f"{dashboard_id}_graph.jsonld"
    write_json(graph_path, graph)
    write_json(jsonld_path, _jsonld_from_graph(graph))
    graph_ids = {node["id"] for node in graph["nodes"]}
    for payload in validated_payloads.values():
        missing = set(payload["ontology_references"]) - graph_ids
        if missing:
            raise ValueError(f"Payload references missing ontology nodes: {sorted(missing)}")
    rag_path = (
        root
        / "data"
        / "curated"
        / "rag_chunks"
        / dashboard_id
        / (f"dashboard_{dashboard_id.split('_')[1]}_context.jsonl")
    )
    write_rag_context(rag_path, validated_payloads)
    extra = dict(extra_manifest or {})
    manifest = DashboardManifest(
        schema_version=SCHEMA_VERSION,
        dashboard_id=dashboard_id,
        title=dashboard_title,
        generated_at=str(metadata["generated_at"]),
        pipeline_version="dashboard_shared_v2",
        git_commit=metadata.get("git_commit"),
        source_file=str(metadata["source_file"]),
        source_file_sha256=str(metadata["source_file_sha256"]),
        filters=dict(metadata["base_filter"]),
        data_health=dict(metadata.get("data_health", {})),
        contract_version=str(metadata.get("contract_version", "2.0")),
        contract_validation_status=str(metadata.get("contract_validation_status", "passed")),
        payloads=tuple(
            ManifestEntry(
                question_id=question_id,
                chart_id=str(validated_payloads[question_id]["chart_id"]),
                question_text=str(validated_payloads[question_id]["question_text"]),
                file=filename,
                record_count=int(validated_payloads[question_id]["record_count"]),
            )
            for question_id, filename in payload_files.items()
        ),
        limitations=tuple(limitations),
        rag_context_file=str(rag_path.relative_to(root)).replace("\\", "/"),
        ontology_graph_file=str(graph_path.relative_to(root)).replace("\\", "/"),
        ontology_jsonld_file=str(jsonld_path.relative_to(root)).replace("\\", "/"),
        report_manifest_file=extra.get("report_manifest_file"),
        upstream_dashboards=tuple(extra.get("upstream_dashboards", ())),
    ).model_dump(mode="json")
    write_json(output_dir / "manifest.json", manifest)
    return manifest


__all__ = [
    "AMOUNT_COLUMN",
    "COMMON_LIMITATIONS",
    "CROSSCUTS_SUBMISSION_TYPE",
    "INTEGRATION_AREA",
    "SITE_SPLITS_SUBMISSION_TYPE",
    "blank_mask",
    "build_dashboard_graph",
    "display_value",
    "format_dollars",
    "load_pit_production_layers",
    "make_payload",
    "node_id",
    "source_row_lineage",
    "write_dashboard_artifacts",
    "write_json",
]
