"""Shared deterministic artifact helpers for Dashboards 2 through 5.

The helpers deliberately keep dashboard payloads aggregate-only.  They reuse
Dashboard 1's FORMEX normalization and Pit Production filter so submission-layer
discipline cannot drift between dashboard builds.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from numbers import Integral, Real
from pathlib import Path
from typing import Any, Mapping

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
from cepe_fynsp.etl.loaders import load_formex

LINEAGE_SAMPLE_LIMIT = 250
COMMON_LIMITATIONS = [
    "FORMEX submission types are overlapping views and are not additive.",
    "PLANEX and COSTEX are FY2026 context and are not reconciled to these FY2028-FY2032 dashboards.",
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
    """Return bounded source-row identifiers without exporting source records."""
    identifiers = df.get("source_row_id", pd.Series(dtype="string")).dropna().astype(str).tolist()
    return {
        "source_row_id_sample": identifiers[:LINEAGE_SAMPLE_LIMIT],
        "lineage_truncated": len(identifiers) > LINEAGE_SAMPLE_LIMIT,
        "source_row_id_count": len(identifiers),
    }


def node_id(node_type: str, value: str) -> str:
    """Create a stable, readable identifier for a dashboard graph node."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return f"{node_type.casefold()}:{slug or 'unspecified'}"


def sha256_file(path: Path) -> str:
    """Return the SHA-256 for a source file used by a payload build."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit(project_root: Path) -> str | None:
    """Return the git commit when available without treating it as a build requirement."""
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


def load_pit_production_layers(
    project_root: Path | None = None,
) -> tuple[Path, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Load normalized FORMEX and return explicit Crosscuts and Site Splits slices."""
    root = (project_root or project_root_from_module()).resolve()
    formex_path = find_formex_csv(root)
    settings = load_settings(root / "config" / "settings.yaml")
    prepared = prepare_formex_dataframe(load_formex(formex_path))
    scenario = select_scenario(prepared, settings.project.default_scenario)
    crosscuts = filter_pit_production(
        prepared, CROSSCUTS_SUBMISSION_TYPE, scenario=scenario
    )
    site_splits = filter_pit_production(
        prepared, SITE_SPLITS_SUBMISSION_TYPE, scenario=scenario
    )
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    metadata = {
        "project_root": root,
        "generated_at": generated_at,
        "source_file": str(formex_path.relative_to(root)).replace("\\", "/"),
        "source_file_sha256": sha256_file(formex_path),
        "scenario": scenario,
        "git_commit": git_commit(root),
        "base_filter": {"program_int_area": INTEGRATION_AREA, "scenario": scenario},
    }
    return root, crosscuts, site_splits, metadata


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
    """Create one schema-versioned static dashboard payload with traceability."""
    chart_id = f"{dashboard_id}_{question_id}"
    traceability = {
        "chart_id": chart_id,
        "dashboard_id": dashboard_id,
        "source_file": metadata["source_file"],
        "source_file_sha256": metadata["source_file_sha256"],
        "source_submission_type": source_submission_type,
        "row_filter": dict(row_filter),
        "metric_definition": metric_definition,
        "grouping_columns": grouping_columns,
        "value_column": value_column,
        "generated_at": metadata["generated_at"],
        "record_count": record_count,
        "limitations": limitations,
        "lineage": dict(lineage),
        "ontology_node_ids": [node_id("Chart", chart_id)],
    }
    return {
        "schema_version": "1.1",
        "dashboard_id": dashboard_id,
        "dashboard_title": dashboard_title,
        "question_id": question_id,
        "question_text": question_text,
        "chart_id": chart_id,
        "chart_type": chart_type,
        "chart_title": chart_title,
        "source_file": metadata["source_file"],
        "source_submission_type": source_submission_type,
        "row_filter": dict(row_filter),
        "metric_definition": metric_definition,
        "grouping_columns": grouping_columns,
        "value_column": value_column,
        "generated_at": metadata["generated_at"],
        "record_count": record_count,
        "data": data,
        "summary": summary,
        "plain_language_summary": summary,
        "limitations": limitations,
        "metric_cards": metric_cards,
        "traceability": traceability,
        "build": {"pipeline_version": "dashboard_02_to_05_v1", "git_commit": metadata["git_commit"]},
    }


def _json_default(value: object) -> object:
    """Convert common dataframe and path values for JSON serialization."""
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
    """Write formatted JSON, creating its parent directory when necessary."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, default=_json_default)
        handle.write("\n")


def write_rag_context(path: Path, payloads: Mapping[str, Mapping[str, Any]]) -> None:
    """Write one compact aggregate-only RAG packet per chart or finding payload."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for question_id in sorted(payloads):
            payload = payloads[question_id]
            traceability = payload["traceability"]
            record = {
                "dashboard_id": payload["dashboard_id"],
                "chart_id": payload["chart_id"],
                "question_id": question_id,
                "question_text": payload["question_text"],
                "metric_definition": payload["metric_definition"],
                "plain_language_summary": payload["plain_language_summary"],
                "source_filter": traceability["row_filter"],
                "source_files": [traceability["source_file"]],
                "source_submission_type": traceability["source_submission_type"],
                "limitations": traceability["limitations"],
                "traceability_refs": {
                    "chart_id": payload["chart_id"],
                    "ontology_node_ids": traceability["ontology_node_ids"],
                    "source_row_id_count": traceability["lineage"].get("source_row_id_count"),
                },
            }
            json.dump(record, handle, ensure_ascii=False, default=_json_default)
            handle.write("\n")


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
    """Build a compact, explicit graph from dashboard aggregates and findings."""
    nodes: dict[str, dict[str, str]] = {}
    edges: list[dict[str, str]] = []

    def add_node(identifier: str, node_type: str, label: str) -> None:
        nodes.setdefault(identifier, {"id": identifier, "node_type": node_type, "label": label})

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
                add_node(finding_node, "Finding", str(row.get("title") or finding_value))
                add_edge(finding_node, chart_node, "finding_supported_by_chart")
    return {
        "schema_version": "1.1",
        "graph_id": f"{dashboard_id}_graph",
        "dashboard_id": dashboard_id,
        "nodes": sorted(nodes.values(), key=lambda item: item["id"]),
        "edges": sorted(edges, key=lambda item: (item["source"], item["edge_type"], item["target"])),
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
    """Write chart payloads, RAG packets, graph, and a discoverable manifest."""
    output_dir = root / "data" / "curated" / "dashboard_payloads" / dashboard_id
    for question_id, filename in payload_files.items():
        write_json(output_dir / filename, payloads[question_id])
    graph = build_dashboard_graph(dashboard_id, dashboard_title, payloads)
    graph_path = root / "data" / "ontology" / f"{dashboard_id}_graph.json"
    write_json(graph_path, graph)
    rag_path = root / "data" / "curated" / "rag_chunks" / dashboard_id / (
        f"dashboard_{dashboard_id.split('_')[1]}_context.jsonl"
    )
    write_rag_context(rag_path, payloads)
    manifest: dict[str, Any] = {
        "schema_version": "1.1",
        "dashboard_id": dashboard_id,
        "title": dashboard_title,
        "generated_at": metadata["generated_at"],
        "pipeline_version": "dashboard_02_to_05_v1",
        "git_commit": metadata["git_commit"],
        "source_file": metadata["source_file"],
        "source_file_sha256": metadata["source_file_sha256"],
        "filters": metadata["base_filter"],
        "payloads": [
            {
                "question_id": question_id,
                "chart_id": payloads[question_id]["chart_id"],
                "question_text": payloads[question_id]["question_text"],
                "file": filename,
                "record_count": payloads[question_id]["record_count"],
            }
            for question_id, filename in payload_files.items()
        ],
        "limitations": limitations,
        "rag_context_file": str(rag_path.relative_to(root)).replace("\\", "/"),
        "ontology_graph_file": str(graph_path.relative_to(root)).replace("\\", "/"),
    }
    if extra_manifest:
        manifest.update(extra_manifest)
    write_json(output_dir / "manifest.json", manifest)
    return manifest


__all__ = [
    "AMOUNT_COLUMN",
    "COMMON_LIMITATIONS",
    "CROSSCUTS_SUBMISSION_TYPE",
    "INTEGRATION_AREA",
    "SITE_SPLITS_SUBMISSION_TYPE",
    "blank_mask",
    "display_value",
    "format_dollars",
    "load_pit_production_layers",
    "make_payload",
    "node_id",
    "source_row_lineage",
    "write_dashboard_artifacts",
    "write_json",
]
