"""Strict request, response, and internal context schemas for live insights."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

INSIGHT_SCHEMA_VERSION = "1.0"
MAX_QUERY_LENGTH = 2000
MAX_IMAGE_BASE64_CHARS = 6_000_000
ID_PATTERN = r"^[a-z0-9_]+$"
FILTER_PATTERN = r"^[a-z][a-z0-9_]*$"


class StrictInsightSchema(BaseModel):
    """Reject unexpected workflow fields at every trust boundary."""

    model_config = ConfigDict(extra="forbid")


class InsightAction(str, Enum):
    """Allowed user actions for a visualization."""

    SUMMARIZE = "summarize"
    SUGGESTED_QUESTION = "suggested_question"
    CUSTOM_QUERY = "custom_query"


class InsightStatus(str, Enum):
    """Explicit service outcomes rendered by the browser."""

    ANSWERED = "answered"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNAVAILABLE = "unavailable"
    INVALID_REQUEST = "invalid_request"
    UPSTREAM_ERROR = "upstream_error"


class ChartImageInput(StrictInsightSchema):
    """Untrusted browser capture metadata and base64 PNG content."""

    mime_type: Literal["image/png"]
    data_base64: str = Field(min_length=1, max_length=MAX_IMAGE_BASE64_CHARS)
    width: int = Field(ge=1, le=2400)
    height: int = Field(ge=1, le=2400)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class InsightClientMetadata(StrictInsightSchema):
    """Non-authoritative, non-sensitive capture status supplied by the browser."""

    image_capture_status: Literal["captured", "unavailable", "failed"]
    device_pixel_ratio: float | None = Field(default=None, ge=0.5, le=4.0)


class InsightRequest(StrictInsightSchema):
    """Strict same-origin POST body accepted by the insights service."""

    schema_version: str = INSIGHT_SCHEMA_VERSION
    dashboard_id: str = Field(min_length=1, max_length=64, pattern=ID_PATTERN)
    question_id: str = Field(min_length=2, max_length=8, pattern=r"^q[1-6]$")
    chart_id: str = Field(min_length=1, max_length=80, pattern=ID_PATTERN)
    action: InsightAction
    active_filter_state: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    query: str | None = Field(default=None, max_length=MAX_QUERY_LENGTH)
    chart_image: ChartImageInput | None = None
    client_metadata: InsightClientMetadata | None = None

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        """Reject incompatible clients."""
        if value != INSIGHT_SCHEMA_VERSION:
            raise ValueError(f"Unsupported insights schema version: {value}")
        return value

    @field_validator("active_filter_state")
    @classmethod
    def validate_filter_shape(cls, value: dict[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
        """Bound filter names and values before authoritative validation."""
        if len(value) > 12:
            raise ValueError("Too many active filters.")
        for name, selected in value.items():
            if not __import__("re").fullmatch(FILTER_PATTERN, name):
                raise ValueError("Invalid filter name.")
            if not selected or len(selected) > 10:
                raise ValueError("Each active filter requires one to ten values.")
            if any(not item.strip() or len(item) > 200 for item in selected):
                raise ValueError("Filter values must be nonblank and at most 200 characters.")
        return value

    @model_validator(mode="after")
    def validate_action_query(self) -> InsightRequest:
        """Require a nonblank custom query and reject query overrides for fixed actions."""
        if self.action is InsightAction.CUSTOM_QUERY:
            if self.query is None or not self.query.strip():
                raise ValueError("A nonblank query is required for custom_query.")
        elif self.query is not None:
            raise ValueError("query is allowed only for custom_query.")
        return self


class InsightCitation(StrictInsightSchema):
    """Browser-safe reference to evidence retained by the server."""

    type: Literal[
        "dashboard_payload",
        "quality_finding",
        "ontology_node",
        "ontology_relationship",
        "ontology_path",
        "guidance_document",
        "source_file_lineage",
    ]
    id: str = Field(min_length=1, max_length=300)
    label: str = Field(min_length=1, max_length=500)
    source_file_id: str | None = Field(default=None, max_length=300)
    page: int | None = Field(default=None, ge=1)
    section: str | None = Field(default=None, max_length=300)


class InsightContextUsed(StrictInsightSchema):
    """Evidence identifiers and construction disclosures safe for the browser."""

    dashboard_id: str
    question_id: str
    chart_id: str
    payload_ids: tuple[str, ...]
    active_filter_state: dict[str, tuple[str, ...]]
    ontology_node_ids: tuple[str, ...]
    ontology_edge_ids: tuple[str, ...]
    ontology_path_ids: tuple[str, ...]
    guidance_chunk_ids: tuple[str, ...]
    source_file_ids: tuple[str, ...]
    image_used: bool
    image_sha256: str | None = None
    context_truncated: bool


class InsightAiMetadata(StrictInsightSchema):
    """Auditable AI-output metadata without prompt or credential contents."""

    model: str | None = None
    prompt_version: str
    request_id: str
    review_status: Literal["unreviewed_ai_output"] = "unreviewed_ai_output"


class InsightResponse(StrictInsightSchema):
    """Strict structured response returned by the same-origin service."""

    schema_version: str = INSIGHT_SCHEMA_VERSION
    status: InsightStatus
    answer: str | None = Field(default=None, max_length=20_000)
    key_observations: tuple[str, ...] = ()
    review_triggers: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    citations: tuple[InsightCitation, ...] = ()
    context_used: InsightContextUsed | None = None
    ai_metadata: InsightAiMetadata

    @model_validator(mode="after")
    def require_grounded_answer(self) -> InsightResponse:
        """Prevent plausible-looking answered responses without evidence citations."""
        if self.status is InsightStatus.ANSWERED and (
            not self.answer or not self.citations or self.context_used is None
        ):
            raise ValueError("Answered insights require answer text and evidence citations.")
        return self


class InsightHealthResponse(StrictInsightSchema):
    """Non-sensitive capability report for the same-origin browser client."""

    schema_version: str = INSIGHT_SCHEMA_VERSION
    service_available: bool
    asksage_configured: bool
    image_input_supported: bool
    document_context_available: bool
    ontology_context_available: bool


class DocumentChunk(StrictInsightSchema):
    """Approved, derived local guidance chunk retained only on the server."""

    chunk_id: str
    source_file_id: str
    source_file_hash: str
    document_title: str
    document_type: str
    page_number: int | None = None
    section_heading: str | None = None
    chunk_index: int = Field(ge=0)
    chunk_text: str = Field(min_length=1)
    classification_metadata: dict[str, str]
    generated_at: str
    parser_version: str


class OntologyNodeContext(StrictInsightSchema):
    """One validated graph node in a relevant bounded subgraph."""

    id: str
    label: str
    node_type: str


class OntologyEdgeContext(StrictInsightSchema):
    """One validated graph relationship with a stable derived edge ID."""

    id: str
    source: str
    target: str
    relationship_type: str


class OntologyPathContext(StrictInsightSchema):
    """One relevant traversal path through the bounded subgraph."""

    id: str
    node_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]


class OntologyContext(StrictInsightSchema):
    """Deterministic relevant graph context and truncation disclosure."""

    graph_id: str | None
    nodes: tuple[OntologyNodeContext, ...]
    edges: tuple[OntologyEdgeContext, ...]
    paths: tuple[OntologyPathContext, ...]
    truncated: bool
    unavailable_reason: str | None = None


class InsightContextPacket(StrictInsightSchema):
    """Authoritative evidence packet shared by all three user actions."""

    context_version: str = "1.0"
    dashboard_id: str
    question_id: str
    chart_id: str
    mandatory_question: str
    prepared_question: str
    chart_title: str
    chart_subtitle: str
    metric_definitions: tuple[str, ...]
    visualization_specification: dict[str, Any]
    build_filter_state: dict[str, Any]
    active_filter_state: dict[str, tuple[str, ...]]
    filtered_aggregate_records: tuple[dict[str, Any], ...]
    total_filtered_record_count: int
    transmitted_record_count: int
    deterministic_summary_statistics: dict[str, Any]
    data_completeness: dict[str, Any]
    aggregate_status: str
    quality_findings: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]
    source_metadata: tuple[dict[str, Any], ...]
    source_lineage_ids: tuple[str, ...]
    ontology: OntologyContext
    document_chunks: tuple[DocumentChunk, ...]
    payload_ids: tuple[str, ...]
    manifest_id: str
    image_metadata: dict[str, Any]
    construction_metadata: dict[str, Any]
    context_truncated: bool


class ModelInsightOutput(StrictInsightSchema):
    """Exact JSON shape required from the final AskSage synthesis."""

    status: Literal["answered", "insufficient_evidence"]
    answer: str = Field(max_length=20_000)
    key_observations: tuple[str, ...] = ()
    review_triggers: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    citations: tuple[InsightCitation, ...] = ()

    @model_validator(mode="after")
    def require_citations(self) -> ModelInsightOutput:
        """Require model-cited evidence for every claimed answered result."""
        if self.status == "answered" and (not self.answer.strip() or not self.citations):
            raise ValueError("Answered model output requires answer text and citations.")
        return self
