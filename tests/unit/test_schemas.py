"""Strict narrative and RAG grounding-schema regressions."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cepe_fynsp.schemas import NarrativeRecord, RagRecord


def _rag_payload() -> dict[str, object]:
    return {
        "record_id": "rag:synthetic",
        "dashboard_id": "dashboard_synthetic",
        "question_id": "q1",
        "question_text": "What does the synthetic evidence show?",
        "filter_state": {"scenario": "Synthetic"},
        "metric_definition": "Sum of valid synthetic amounts.",
        "calculated_values": ({"amount": 1.0},),
        "calculated_observations": ("One synthetic unit was observed.",),
        "quality_status": "GREEN",
        "limitations": ("Synthetic test only.",),
        "payload_ids": ("dashboard_synthetic_q1",),
        "ontology_ids": ("metric:synthetic:123",),
        "source_file_ids": ("synthetic.csv",),
        "source_hashes": ("abc123",),
        "lineage_ids": ("synthetic:row:1",),
        "citation_labels": ("payload:dashboard_synthetic_q1",),
        "classification_metadata": {"status": "not_applicable"},
        "narrative_origin": "calculated_observation",
    }


def test_rag_record_rejects_missing_payload_citation() -> None:
    payload = _rag_payload()
    payload["payload_ids"] = ()
    with pytest.raises(ValidationError, match="require payload"):
        RagRecord.model_validate(payload)


def test_rag_record_rejects_unsupported_schema_version() -> None:
    payload = _rag_payload()
    payload["schema_version"] = "1.0"
    with pytest.raises(ValidationError, match="Unsupported RAG schema"):
        RagRecord.model_validate(payload)


def test_narrative_record_requires_evidence_citation() -> None:
    with pytest.raises(ValidationError, match="evidence citation"):
        NarrativeRecord(origin="calculated_observation", text="Observed.", citations=())
