"""Secure orchestration of context construction and AskSage insight synthesis."""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from cepe_fynsp.asksage.client import AskSageClient, AskSageError
from cepe_fynsp.config import Settings, load_settings
from cepe_fynsp.insights.context import (
    InsightContextError,
    build_insight_context,
)
from cepe_fynsp.insights.images import InvalidChartImageError, validate_chart_image
from cepe_fynsp.insights.prompt import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_grounded_prompt,
    build_image_interpretation_prompt,
    build_schema_repair_prompt,
    evidence_citation_inventory,
)
from cepe_fynsp.insights.schemas import (
    InsightAiMetadata,
    InsightContextPacket,
    InsightContextUsed,
    InsightHealthResponse,
    InsightRequest,
    InsightResponse,
    InsightStatus,
    ModelInsightOutput,
)

LOGGER = logging.getLogger(__name__)
JSON_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*(\{.*\})\s*```$", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class GroundedResponseDiagnostic:
    """Content-free structural metadata for a rejected model completion."""

    stage: str
    message_length: int = 0
    markdown_fence: bool = False
    issues: tuple[str, ...] = ()


class GroundedResponseError(ValueError):
    """A model completion failed the strict grounded response boundary."""

    def __init__(self, diagnostic: GroundedResponseDiagnostic):
        super().__init__("AskSage grounded response failed structural validation.")
        self.diagnostic = diagnostic


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def _configured_from_environment() -> bool:
    return bool(
        os.getenv("ASKSAGE_ACCESS_TOKEN")
        or (os.getenv("ASKSAGE_EMAIL") and os.getenv("ASKSAGE_API_KEY"))
    )


def _completion_message(payload: object) -> str:
    """Extract only the completion field documented by the AskSage OpenAPI schema."""
    if not isinstance(payload, dict):
        raise ValueError("AskSage returned an invalid completion envelope.")
    message = payload.get("message")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("AskSage completion did not contain message text.")
    return message.strip()


def _validation_issues(error: ValidationError) -> tuple[str, ...]:
    """Return bounded field/type diagnostics without rejected input values."""
    issues: list[str] = []
    for item in error.errors(
        include_url=False,
        include_context=False,
        include_input=False,
    )[:12]:
        location = ".".join(str(part) for part in item.get("loc", ())) or "<root>"
        issues.append(f"{location}:{item.get('type', 'validation_error')}")
    return tuple(issues)


def parse_grounded_model_output(payload: object) -> ModelInsightOutput:
    """Parse exact JSON or one exact JSON Markdown fence into the strict model schema."""
    try:
        message = _completion_message(payload)
    except ValueError as exc:
        raise GroundedResponseError(
            GroundedResponseDiagnostic(stage="completion_envelope")
        ) from exc

    fence_match = JSON_FENCE_PATTERN.fullmatch(message)
    candidate = fence_match.group(1) if fence_match else message
    try:
        decoded = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise GroundedResponseError(
            GroundedResponseDiagnostic(
                stage="json_decode",
                message_length=len(message),
                markdown_fence=message.startswith("```"),
                issues=(f"{exc.msg}@{exc.lineno}:{exc.colno}",),
            )
        ) from exc
    try:
        output = ModelInsightOutput.model_validate(decoded)
    except ValidationError as exc:
        raise GroundedResponseError(
            GroundedResponseDiagnostic(
                stage="schema_validation",
                message_length=len(message),
                markdown_fence=fence_match is not None,
                issues=_validation_issues(exc),
            )
        ) from exc
    LOGGER.info(
        "AskSage grounded response structurally accepted message_length=%s markdown_fence=%s",
        len(message),
        fence_match is not None,
    )
    return output


def _log_grounded_rejection(
    *, request_id: str, chart_id: str, attempt: str, error: GroundedResponseError
) -> None:
    """Log content-free rejection metadata for operator diagnosis."""
    diagnostic = error.diagnostic
    LOGGER.warning(
        "Insight grounded response rejected request_id=%s chart_id=%s attempt=%s "
        "stage=%s message_length=%s markdown_fence=%s issues=%s",
        request_id,
        chart_id,
        attempt,
        diagnostic.stage,
        diagnostic.message_length,
        diagnostic.markdown_fence,
        ";".join(diagnostic.issues) or "none",
    )


class InsightService:
    """Evidence-grounded service used by the same-origin HTTP handler and tests."""

    def __init__(
        self,
        project_root: Path,
        *,
        client: AskSageClient | None = None,
        settings: Settings | None = None,
        image_input_supported: bool | None = None,
    ):
        self.project_root = project_root.resolve()
        self.settings = settings or load_settings(project_root=self.project_root)
        configured = _configured_from_environment()
        self.client = client or (AskSageClient.from_env() if configured else None)
        self.image_input_supported = (
            image_input_supported
            if image_input_supported is not None
            else _truthy(os.getenv(self.settings.insights.image_capability_env))
        )

    @property
    def dataset_ids(self) -> tuple[str, ...]:
        """Return configured approved dataset identifiers without logging their values."""
        environment_names = (
            self.settings.asksage.dataset_guidance_env,
            self.settings.asksage.dataset_dashboard_payload_env,
            self.settings.asksage.dataset_ontology_env,
        )
        return tuple(
            dict.fromkeys(
                value.strip()
                for name in environment_names
                if (value := os.getenv(name)) and value.strip()
            )
        )

    def health(self) -> InsightHealthResponse:
        """Report capabilities without probing upstream or exposing configuration values."""
        payload_root = self.project_root / "data" / "curated" / "dashboard_payloads"
        ontology_available = any((self.project_root / "data" / "ontology").glob("*_graph.json"))
        document_index = self.settings.resolve_path(self.settings.insights.document_index)
        document_available = document_index.is_file() and document_index.stat().st_size > 0
        return InsightHealthResponse(
            service_available=payload_root.is_dir(),
            asksage_configured=self.client is not None,
            image_input_supported=self.client is not None and self.image_input_supported,
            document_context_available=document_available,
            ontology_context_available=ontology_available,
        )

    def _metadata(self, request_id: str) -> InsightAiMetadata:
        return InsightAiMetadata(
            model=self.client.config.model if self.client else None,
            prompt_version=PROMPT_VERSION,
            request_id=request_id,
        )

    def _context_used(
        self,
        packet: InsightContextPacket,
        *,
        image_used: bool,
    ) -> InsightContextUsed:
        image_hash = (
            str(packet.image_metadata.get("sha256"))
            if image_used and packet.image_metadata.get("sha256")
            else None
        )
        source_ids = tuple(
            dict.fromkeys(str(source.get("source_file", "")) for source in packet.source_metadata)
        )
        return InsightContextUsed(
            dashboard_id=packet.dashboard_id,
            question_id=packet.question_id,
            chart_id=packet.chart_id,
            payload_ids=packet.payload_ids,
            active_filter_state=packet.active_filter_state,
            ontology_node_ids=tuple(node.id for node in packet.ontology.nodes),
            ontology_edge_ids=tuple(edge.id for edge in packet.ontology.edges),
            ontology_path_ids=tuple(path.id for path in packet.ontology.paths),
            guidance_chunk_ids=tuple(chunk.chunk_id for chunk in packet.document_chunks),
            source_file_ids=tuple(value for value in source_ids if value),
            image_used=image_used,
            image_sha256=image_hash,
            context_truncated=packet.context_truncated,
        )

    def _error(
        self,
        *,
        status: InsightStatus,
        request_id: str,
        limitation: str,
        packet: InsightContextPacket | None = None,
        image_used: bool = False,
    ) -> InsightResponse:
        return InsightResponse(
            status=status,
            answer=None,
            limitations=(limitation,),
            context_used=(
                self._context_used(packet, image_used=image_used) if packet is not None else None
            ),
            ai_metadata=self._metadata(request_id),
        )

    def answer(self, request: InsightRequest) -> InsightResponse:
        """Build one authoritative packet and use it for any of the three actions."""
        request_id = str(uuid.uuid4())
        validated_image = None
        if request.chart_image is not None:
            try:
                validated_image = validate_chart_image(request.chart_image)
            except InvalidChartImageError:
                return self._error(
                    status=InsightStatus.INVALID_REQUEST,
                    request_id=request_id,
                    limitation="The visualization image was invalid or exceeded the allowed limits.",
                )
        try:
            packet = build_insight_context(
                self.project_root,
                request.dashboard_id,
                request.question_id,
                request.chart_id,
                request.active_filter_state,
                validated_image,
                retrieval_query=request.query,
            )
        except (InsightContextError, ValidationError, OSError, json.JSONDecodeError):
            return self._error(
                status=InsightStatus.INVALID_REQUEST,
                request_id=request_id,
                limitation="The requested dashboard context or filter state is invalid.",
            )
        if self.client is None:
            return self._error(
                status=InsightStatus.UNAVAILABLE,
                request_id=request_id,
                limitation=(
                    "Live insights are unavailable. The dashboard and deterministic analysis remain available."
                ),
                packet=packet,
            )

        image_interpretation: str | None = None
        image_limitation: str | None = None
        if validated_image is not None and self.image_input_supported:
            try:
                image_payload = self.client.query_with_file(
                    build_image_interpretation_prompt(packet),
                    file_content=validated_image.content,
                    filename="chart.png",
                    mime_type=validated_image.mime_type,
                    system_prompt=SYSTEM_PROMPT,
                    model=self.client.config.model,
                    temperature=0.0,
                    limit_references=1,
                )
                image_interpretation = _completion_message(image_payload)
            except (AskSageError, ValueError):
                image_limitation = (
                    "The visualization image could not be processed; the answer used validated data "
                    "and available evidence instead."
                )
        elif validated_image is not None:
            image_limitation = (
                "Image input is not verified for the configured model; the answer used validated data "
                "and available evidence instead."
            )

        prompt = build_grounded_prompt(
            action=request.action,
            packet=packet,
            custom_query=request.query,
            image_interpretation=image_interpretation,
        )
        query_arguments = {
            "system_prompt": SYSTEM_PROMPT,
            "model": self.client.config.model,
            "dataset": list(self.dataset_ids) if self.dataset_ids else "none",
            "temperature": 0.0,
            "limit_references": 1,
            "live": 0,
            "streaming": False,
            "usage": True,
        }
        try:
            completion = self.client.query(prompt, **query_arguments)
        except AskSageError:
            LOGGER.warning(
                "Insight upstream unavailable request_id=%s chart_id=%s",
                request_id,
                request.chart_id,
            )
            return self._error(
                status=InsightStatus.UPSTREAM_ERROR,
                request_id=request_id,
                limitation="AskSage could not complete the request. Deterministic evidence remains available.",
                packet=packet,
                image_used=image_interpretation is not None,
            )
        try:
            output = parse_grounded_model_output(completion)
        except GroundedResponseError as exc:
            _log_grounded_rejection(
                request_id=request_id,
                chart_id=request.chart_id,
                attempt="initial",
                error=exc,
            )
            try:
                repaired_completion = self.client.query(
                    build_schema_repair_prompt(prompt), **query_arguments
                )
                output = parse_grounded_model_output(repaired_completion)
            except AskSageError:
                return self._error(
                    status=InsightStatus.UPSTREAM_ERROR,
                    request_id=request_id,
                    limitation=(
                        "AskSage could not regenerate a grounded structured response. "
                        "Deterministic evidence remains available."
                    ),
                    packet=packet,
                    image_used=image_interpretation is not None,
                )
            except GroundedResponseError as repair_error:
                _log_grounded_rejection(
                    request_id=request_id,
                    chart_id=request.chart_id,
                    attempt="repair",
                    error=repair_error,
                )
                return self._error(
                    status=InsightStatus.UPSTREAM_ERROR,
                    request_id=request_id,
                    limitation=(
                        "AskSage returned responses that did not satisfy the grounded response "
                        "schema. Deterministic evidence remains available."
                    ),
                    packet=packet,
                    image_used=image_interpretation is not None,
                )

        allowed = {
            (citation.type, citation.id): citation
            for citation in evidence_citation_inventory(packet)
        }
        if any((citation.type, citation.id) not in allowed for citation in output.citations):
            return self._error(
                status=InsightStatus.INSUFFICIENT_EVIDENCE,
                request_id=request_id,
                limitation="AskSage cited evidence outside the validated context; no answer was accepted.",
                packet=packet,
                image_used=image_interpretation is not None,
            )
        canonical_citations = tuple(
            allowed[(citation.type, citation.id)] for citation in output.citations
        )
        limitations = list(output.limitations)
        limitations.extend(packet.limitations)
        if image_limitation:
            limitations.append(image_limitation)
        status = (
            InsightStatus.ANSWERED
            if output.status == "answered"
            else InsightStatus.INSUFFICIENT_EVIDENCE
        )
        response = InsightResponse(
            status=status,
            answer=output.answer.strip() or None,
            key_observations=output.key_observations,
            review_triggers=output.review_triggers,
            limitations=tuple(dict.fromkeys(limitations)),
            citations=canonical_citations,
            context_used=self._context_used(packet, image_used=image_interpretation is not None),
            ai_metadata=self._metadata(request_id),
        )
        LOGGER.info(
            "Insight request completed request_id=%s chart_id=%s status=%s",
            request_id,
            request.chart_id,
            response.status.value,
        )
        return response
