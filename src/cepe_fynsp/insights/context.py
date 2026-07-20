"""Authoritative server-side construction of visualization insight evidence packets."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from cepe_fynsp.dashboards.insight_questions import insight_ui_config
from cepe_fynsp.insights.documents import load_document_index, retrieve_document_chunks
from cepe_fynsp.insights.images import ValidatedChartImage
from cepe_fynsp.insights.ontology import resolve_ontology_context
from cepe_fynsp.insights.schemas import InsightContextPacket
from cepe_fynsp.schemas import DashboardManifest, DashboardQuestionPayload

MAX_AGGREGATE_RECORDS = 50
MAX_LINEAGE_IDS = 250


class InsightContextError(ValueError):
    """Base error for invalid authoritative insight context."""


class InsightIdentityError(InsightContextError):
    """Dashboard, question, chart, or payload identity mismatch."""


class InsightFilterError(InsightContextError):
    """Unknown, unsupported, or contradictory active filter state."""


def _safe_child(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise InsightContextError(
            "An authoritative artifact path escapes its expected root."
        ) from exc
    return candidate


def _load_payload(
    project_root: Path, dashboard_id: str, question_id: str, chart_id: str
) -> tuple[DashboardManifest, DashboardQuestionPayload, Path, Path]:
    payload_root = project_root / "data" / "curated" / "dashboard_payloads"
    manifest_path = payload_root / dashboard_id / "manifest.json"
    if not manifest_path.is_file():
        raise InsightIdentityError("The requested dashboard payload manifest is unavailable.")
    manifest = DashboardManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    if manifest.dashboard_id != dashboard_id:
        raise InsightIdentityError("Dashboard identity does not match its authoritative manifest.")
    entries = [entry for entry in manifest.payloads if entry.question_id == question_id]
    if len(entries) != 1:
        raise InsightIdentityError("The requested dashboard question is unknown.")
    entry = entries[0]
    if entry.chart_id != chart_id:
        raise InsightIdentityError("Dashboard, question, and chart identifiers do not match.")
    payload_path = _safe_child(manifest_path.parent, entry.file)
    if not payload_path.is_file():
        raise InsightIdentityError("The requested dashboard payload is unavailable.")
    payload = DashboardQuestionPayload.model_validate_json(payload_path.read_text(encoding="utf-8"))
    if (payload.dashboard_id, payload.question_id, payload.chart_id) != (
        dashboard_id,
        question_id,
        chart_id,
    ):
        raise InsightIdentityError("Authoritative payload identity is inconsistent.")
    expected_insights = insight_ui_config(dashboard_id, question_id)
    if payload.insights != expected_insights:
        raise InsightIdentityError(
            "Prepared question metadata does not match server configuration."
        )
    graph_path = _safe_child(project_root, manifest.ontology_graph_file)
    return manifest, payload, manifest_path, graph_path


def _normalize_active_filters(
    payload: DashboardQuestionPayload, requested: Mapping[str, tuple[str, ...]]
) -> dict[str, tuple[str, ...]]:
    allowed_options = payload.filter_options
    unknown = set(requested) - set(allowed_options)
    if unknown:
        raise InsightFilterError(f"Unsupported active filter: {sorted(unknown)[0]}")
    if "submission_type" in requested or "source_submission_type" in requested:
        raise InsightFilterError(
            "Submission-layer filters cannot be overridden by an insight request."
        )
    resolved: dict[str, tuple[str, ...]] = {}
    for field in sorted(requested):
        authoritative = {
            str(value).casefold(): str(value) for value in allowed_options.get(field, [])
        }
        values: list[str] = []
        for selected in requested[field]:
            canonical = authoritative.get(str(selected).casefold())
            if canonical is None:
                raise InsightFilterError(f"Unsupported value for active filter {field}.")
            if canonical not in values:
                values.append(canonical)
        resolved[field] = tuple(values)
    return resolved


def _row_matches(row: Mapping[str, Any], filters: Mapping[str, tuple[str, ...]]) -> bool:
    for field, selected in filters.items():
        if field not in row:
            continue
        allowed = {value.casefold() for value in selected}
        if str(row[field]).casefold() not in allowed:
            return False
    return True


def _numeric_values(payload: DashboardQuestionPayload, rows: list[dict[str, Any]]) -> list[float]:
    key = payload.visualization.y
    if not key:
        return []
    values: list[float] = []
    for row in rows:
        value = row.get(key)
        if isinstance(value, bool):
            continue
        if not isinstance(value, (int, float, str)):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number == number and number not in {float("inf"), float("-inf")}:
            values.append(number)
    return values


def _row_identity(row: Mapping[str, Any]) -> str:
    return json.dumps(row, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))


def _bounded_records(
    payload: DashboardQuestionPayload, rows: list[dict[str, Any]]
) -> tuple[dict[str, Any], ...]:
    if len(rows) <= MAX_AGGREGATE_RECORDS:
        return tuple(rows)
    key = payload.visualization.y

    def materiality(row: Mapping[str, Any]) -> tuple[float, str]:
        try:
            value = abs(float(row.get(key, 0))) if key else 0.0
        except (TypeError, ValueError):
            value = 0.0
        return (-value, _row_identity(row))

    ranked = sorted(rows, key=materiality)
    candidates = [*ranked[:40], *rows[:5], *rows[-5:]]
    unique: dict[str, dict[str, Any]] = {}
    for row in candidates:
        unique.setdefault(_row_identity(row), row)
    return tuple(list(unique.values())[:MAX_AGGREGATE_RECORDS])


def _lineage_ids(value: object) -> tuple[str, ...]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if key in {
                "source_record_id_sample",
                "source_row_id_sample",
                "source_row_hashes",
            } and isinstance(nested, list):
                found.extend(str(item) for item in nested)
            else:
                found.extend(_lineage_ids(nested))
    elif isinstance(value, list):
        for nested in value:
            found.extend(_lineage_ids(nested))
    return tuple(dict.fromkeys(found))[:MAX_LINEAGE_IDS]


def _quality_findings(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    findings: list[dict[str, Any]] = []
    allowed = {
        "finding_id",
        "rule_id",
        "severity",
        "category",
        "title",
        "affected_dollars",
        "financial_exposure",
        "row_count",
        "evidence_strength",
        "aggregate_status",
    }
    for row in rows:
        if row.get("finding_id") or row.get("rule_id"):
            findings.append({key: row[key] for key in sorted(allowed & set(row))})
    return tuple(findings[:25])


def _seed_labels(
    payload: DashboardQuestionPayload,
    rows: list[dict[str, Any]],
    active_filters: Mapping[str, tuple[str, ...]],
) -> tuple[str, ...]:
    labels = [value for values in active_filters.values() for value in values]
    dimension_fields = {
        "funding_level",
        "fiscal_year",
        "organization",
        "sub_office_number",
        "site",
        "program_request",
        "acquisition_id",
        "acquisition_name",
        "acquisition_type",
        "finding_id",
        "rule_id",
    }
    for row in rows[:MAX_AGGREGATE_RECORDS]:
        labels.extend(
            str(row[field]) for field in dimension_fields & set(row) if row[field] is not None
        )
    labels.extend((payload.dashboard_title, payload.question_text, payload.chart_title))
    return tuple(dict.fromkeys(label for label in labels if label.strip()))


def build_insight_context(
    project_root: Path,
    dashboard_id: str,
    question_id: str,
    chart_id: str,
    active_filter_state: Mapping[str, tuple[str, ...]],
    chart_image: ValidatedChartImage | None,
    *,
    retrieval_query: str | None = None,
) -> InsightContextPacket:
    """Build the one authoritative context packet shared by every insight action."""
    root = project_root.resolve()
    manifest, payload, manifest_path, graph_path = _load_payload(
        root, dashboard_id, question_id, chart_id
    )
    resolved_filters = _normalize_active_filters(payload, active_filter_state)
    filtered = [row for row in payload.data if _row_matches(row, resolved_filters)]
    transmitted = _bounded_records(payload, filtered)
    numeric = _numeric_values(payload, filtered)
    statistics: dict[str, Any] = {
        "filtered_record_count": len(filtered),
        "transmitted_record_count": len(transmitted),
        "numeric_value_count": len(numeric),
    }
    if numeric:
        statistics.update(
            {
                "numeric_total": sum(numeric),
                "numeric_minimum": min(numeric),
                "numeric_maximum": max(numeric),
            }
        )
    ontology = resolve_ontology_context(
        graph_path,
        seed_node_ids=payload.ontology_references,
        seed_labels=_seed_labels(payload, filtered, resolved_filters),
    )
    retrieval_text = "\n".join(
        [
            payload.question_text,
            payload.insights.suggested_question,
            retrieval_query or "",
            *payload.metric_definitions,
            *payload.warnings,
            *[value for values in resolved_filters.values() for value in values],
            *[node.label for node in ontology.nodes],
        ]
    )
    index_path = root / "data" / "curated" / "guidance_chunks" / "index.jsonl"
    indexed_chunks = load_document_index(index_path)
    document_chunks = retrieve_document_chunks(indexed_chunks, retrieval_text)
    limitations = list(payload.limitations)
    if ontology.unavailable_reason:
        limitations.append(ontology.unavailable_reason)
    if not indexed_chunks:
        limitations.append(
            "No approval-gated local guidance index is available; the answer cannot claim document support."
        )
    if chart_image is None:
        limitations.append(
            "The visualization image was not accepted; validated aggregate data remains authoritative."
        )
    context_truncated = len(filtered) > len(transmitted) or ontology.truncated
    manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    return InsightContextPacket(
        dashboard_id=dashboard_id,
        question_id=question_id,
        chart_id=chart_id,
        mandatory_question=payload.question_text,
        prepared_question=payload.insights.suggested_question,
        chart_title=payload.chart_title,
        chart_subtitle=payload.subtitle,
        metric_definitions=payload.metric_definitions,
        visualization_specification=payload.visualization.model_dump(mode="json"),
        build_filter_state=dict(payload.active_filter_state),
        active_filter_state=resolved_filters,
        filtered_aggregate_records=transmitted,
        total_filtered_record_count=len(filtered),
        transmitted_record_count=len(transmitted),
        deterministic_summary_statistics=statistics,
        data_completeness=dict(payload.quality_summary.financial_completeness),
        aggregate_status=payload.quality_summary.overall_status,
        quality_findings=_quality_findings(filtered),
        warnings=payload.warnings,
        limitations=tuple(dict.fromkeys(limitations)),
        source_metadata=payload.source_metadata,
        source_lineage_ids=_lineage_ids(payload.lineage),
        ontology=ontology,
        document_chunks=document_chunks,
        payload_ids=(payload.chart_id,),
        manifest_id=f"manifest:{dashboard_id}:{manifest_hash[:20]}",
        image_metadata=(
            {
                "accepted_for_processing": True,
                "mime_type": chart_image.mime_type,
                "width": chart_image.width,
                "height": chart_image.height,
                "sha256": chart_image.sha256,
            }
            if chart_image
            else {"accepted_for_processing": False}
        ),
        construction_metadata={
            "context_builder_version": "insight_context_v1",
            "aggregate_record_limit": MAX_AGGREGATE_RECORDS,
            "lineage_id_limit": MAX_LINEAGE_IDS,
            "ontology_limits": {"depth": 2, "nodes": 40, "edges": 80, "paths": 20},
            "document_chunk_limit": 5,
            "document_character_limit": 12_000,
            "submission_layer_override_allowed": False,
        },
        context_truncated=context_truncated,
    )
