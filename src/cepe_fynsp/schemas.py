"""Versioned schemas shared by dashboards, RAG, findings, and reports."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "2.0"


class StrictSchema(BaseModel):
    """Reject unexpected fields in generated analytical artifacts."""

    model_config = ConfigDict(extra="forbid")


class ColumnSchema(StrictSchema):
    """Explicit table field and display contract."""

    key: str
    label: str
    format: Literal["text", "integer", "number", "currency", "percentage", "date", "status"]
    sortable: bool = True
    searchable: bool = True
    visible: bool = True


class VisualizationSpec(StrictSchema):
    """Declarative static visualization mapping."""

    type: str
    x: str | None = None
    y: str | None = None
    series: str | None = None
    size: str | None = None
    color: str | None = None
    sort: tuple[str, ...] = ()
    format: dict[str, str] = Field(default_factory=dict)
    accessible_description: str


class MetricCard(StrictSchema):
    """A generated dashboard metric with completeness disclosure."""

    label: str
    value: Any = None
    display: str
    aggregate_status: str = "not_evaluated"
    completeness_percentage: float | None = None


class NarrativeRecord(StrictSchema):
    """Narrative text with unambiguous deterministic/human/AI origin."""

    origin: Literal[
        "calculated_observation",
        "deterministic_analytical_conclusion",
        "analyst_interpretation",
        "ai_generated_narrative",
        "source_evidence",
        "limitation",
    ]
    text: str
    citations: tuple[str, ...] = ()
    filter_state: dict[str, Any] = Field(default_factory=dict)

    @field_validator("citations")
    @classmethod
    def require_citations(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Every generated narrative must identify its approved evidence."""
        if not value:
            raise ValueError("Narrative records require at least one evidence citation.")
        return value


class QualitySummary(StrictSchema):
    """Deterministic health status carried by every question payload."""

    overall_status: Literal["GREEN", "AMBER", "RED", "NOT EVALUATED"]
    status_rule: str
    financial_completeness: dict[str, Any]
    quality_check_summary: str
    reconciliation_status: str


class DashboardQuestionPayload(StrictSchema):
    """Complete aggregate-only contract for one mandatory question."""

    schema_version: str
    dashboard_id: str
    dashboard_title: str
    question_id: str
    question_text: str
    title: str
    subtitle: str
    chart_id: str
    chart_type: str
    chart_title: str
    metrics: tuple[MetricCard, ...]
    metric_cards: tuple[MetricCard, ...]
    metric_definitions: tuple[str, ...]
    metric_definition: str
    data: list[dict[str, Any]]
    columns: tuple[ColumnSchema, ...]
    visualization: VisualizationSpec
    filter_options: dict[str, list[Any]]
    active_filter_state: dict[str, Any]
    warnings: tuple[str, ...]
    quality_summary: QualitySummary
    traceability: dict[str, Any]
    source_metadata: tuple[dict[str, Any], ...]
    lineage: dict[str, Any]
    narrative: tuple[NarrativeRecord, ...]
    ontology_references: tuple[str, ...]
    generated_metadata: dict[str, Any]
    source_file: str
    source_submission_type: str
    row_filter: dict[str, Any]
    grouping_columns: tuple[str, ...]
    value_column: str
    generated_at: str
    record_count: int
    summary: str
    plain_language_summary: str
    limitations: tuple[str, ...]
    build: dict[str, Any]

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        """Reject artifacts that the static renderer cannot interpret."""
        if value != SCHEMA_VERSION:
            raise ValueError(f"Unsupported dashboard payload schema version: {value}")
        return value


class ManifestEntry(StrictSchema):
    """One payload entry in a dashboard manifest."""

    question_id: str
    chart_id: str
    question_text: str
    file: str
    record_count: int
    schema_version: str = SCHEMA_VERSION

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        """Reject entries produced for an unsupported renderer contract."""
        if value != SCHEMA_VERSION:
            raise ValueError(f"Unsupported manifest-entry schema version: {value}")
        return value


class DashboardManifest(StrictSchema):
    """Discoverable manifest for one six-question dashboard."""

    schema_version: str
    dashboard_id: str
    title: str
    generated_at: str
    pipeline_version: str
    git_commit: str | None
    source_file: str
    source_file_sha256: str
    filters: dict[str, Any]
    data_health: dict[str, Any]
    contract_version: str
    contract_validation_status: str
    payloads: tuple[ManifestEntry, ...]
    limitations: tuple[str, ...]
    rag_context_file: str
    ontology_graph_file: str
    ontology_jsonld_file: str
    report_manifest_file: str | None = None
    upstream_dashboards: tuple[str, ...] = ()

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        """Reject unsupported manifest versions."""
        if value != SCHEMA_VERSION:
            raise ValueError(f"Unsupported dashboard manifest schema version: {value}")
        return value


class RagRecord(StrictSchema):
    """Evidence-bounded retrieval packet generated from approved artifacts."""

    schema_version: str = SCHEMA_VERSION
    record_id: str
    dashboard_id: str
    question_id: str
    question_text: str
    filter_state: dict[str, Any]
    metric_definition: str
    calculated_values: tuple[dict[str, Any], ...]
    calculated_observations: tuple[str, ...]
    quality_status: str
    limitations: tuple[str, ...]
    payload_ids: tuple[str, ...]
    ontology_ids: tuple[str, ...]
    source_file_ids: tuple[str, ...]
    source_hashes: tuple[str, ...]
    lineage_ids: tuple[str, ...]
    citation_labels: tuple[str, ...]
    classification_metadata: dict[str, Any]
    narrative_origin: str

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        """Reject retrieval packets built for an unsupported contract."""
        if value != SCHEMA_VERSION:
            raise ValueError(f"Unsupported RAG schema version: {value}")
        return value

    @field_validator("payload_ids", "citation_labels")
    @classmethod
    def require_payload_citations(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Prevent ungrounded retrieval packets from entering the RAG corpus."""
        if not value:
            raise ValueError("RAG records require payload and citation identifiers.")
        return value


class RagAnswer(StrictSchema):
    """Evidence-bounded deterministic answer with optional reviewed AI text."""

    schema_version: str = SCHEMA_VERSION
    question: str
    interpreted_filter_state: dict[str, Any]
    status: Literal["answered", "insufficient_evidence"]
    observed_facts: tuple[str, ...]
    interpretations: tuple[str, ...] = ()
    limitations: tuple[str, ...]
    citation_labels: tuple[str, ...]
    payload_ids: tuple[str, ...]
    ontology_ids: tuple[str, ...]
    narrative_origin: Literal["deterministic_analytical_conclusion"] = (
        "deterministic_analytical_conclusion"
    )
    ai_generated_narrative: str | None = None
    ai_prompt_version: str | None = None
    ai_model: str | None = None
    ai_review_status: Literal["not_requested", "pending_human_review"] = "not_requested"

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        if value != SCHEMA_VERSION:
            raise ValueError(f"Unsupported RAG answer schema version: {value}")
        return value

    @model_validator(mode="after")
    def require_grounding_for_answer(self) -> RagAnswer:
        """An answered response cannot omit its evidence identifiers."""
        if self.status == "answered" and not (
            self.observed_facts and self.citation_labels and self.payload_ids and self.ontology_ids
        ):
            raise ValueError(
                "Answered RAG responses require facts and complete evidence citations."
            )
        return self


class Finding(StrictSchema):
    """Read-only operational finding record."""

    finding_id: str
    rule_id: str
    severity: Literal["low", "medium", "high", "critical", "limitation", "not_evaluated"]
    category: str
    title: str
    analytical_conclusion: str
    financial_exposure: float | None
    affected_organizations: tuple[str, ...] = ()
    affected_sites: tuple[str, ...] = ()
    affected_fiscal_years: tuple[str, ...] = ()
    evidence: tuple[str, ...]
    source_lineage: tuple[str, ...] = ()
    evidence_strength: Literal["strong", "moderate", "limited", "not_evaluated"]
    owner: str | None = None
    status: Literal["new", "under_review", "response_received", "resolved", "accepted_risk"] = "new"
    due_date: str | None = None
    management_response: str | None = None
    analyst_disposition: str | None = None


class FindingDisposition(StrictSchema):
    """Optional separately maintained read-only disposition input."""

    finding_id: str
    owner: str | None = None
    status: Literal["new", "under_review", "response_received", "resolved", "accepted_risk"]
    due_date: str | None = None
    management_response: str | None = None
    analyst_disposition: str | None = None

    @field_validator("due_date")
    @classmethod
    def validate_due_date(cls, value: str | None) -> str | None:
        """Require an unambiguous ISO calendar date when a due date is provided."""
        if value is not None:
            date.fromisoformat(value)
        return value


class CitationRecord(StrictSchema):
    """A report claim and its reproducible evidence reference."""

    report_id: str
    paragraph_id: str
    claim_text: str
    citation_type: str
    citation_id: str
    source_file: str | None = None
    source_filter: dict[str, Any] = Field(default_factory=dict)
    chart_id: str | None = None
    dashboard_id: str | None = None
    metric_definition: str | None = None
    finding_ids: tuple[str, ...] = ()
    retrieval_chunk_id: str | None = None
    ontology_path: tuple[str, ...] = ()
