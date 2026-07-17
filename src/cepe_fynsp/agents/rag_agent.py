"""Evidence-bounded retrieval and optional AskSage narrative orchestration."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from cepe_fynsp.asksage.client import AskSageClient
from cepe_fynsp.schemas import (
    DashboardManifest,
    DashboardQuestionPayload,
    RagAnswer,
    RagRecord,
)

PROMPT_VERSION = "rag_chart_summary_v1"
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _lineage_values(value: object) -> set[str]:
    """Collect only explicit bounded source-record lineage values."""
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if key in {"source_record_id_sample", "source_row_id_sample"} and isinstance(
                nested, list
            ):
                found.update(str(item) for item in nested)
            else:
                found.update(_lineage_values(nested))
    elif isinstance(value, list):
        for nested in value:
            found.update(_lineage_values(nested))
    return found


def load_validated_rag_corpus(project_root: Path) -> tuple[RagRecord, ...]:
    """Load RAG packets and reject invalid payload, ontology, or lineage references."""
    root = project_root.resolve()
    payload_root = root / "data" / "curated" / "dashboard_payloads"
    records: list[RagRecord] = []
    for manifest_path in sorted(payload_root.glob("dashboard_*/manifest.json")):
        manifest = DashboardManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
        payload_ids: set[str] = set()
        lineage_ids: set[str] = set()
        for entry in manifest.payloads:
            payload = DashboardQuestionPayload.model_validate_json(
                (manifest_path.parent / entry.file).read_text(encoding="utf-8")
            )
            payload_ids.add(payload.chart_id)
            lineage_ids.update(_lineage_values(payload.lineage))
        graph = json.loads((root / manifest.ontology_graph_file).read_text(encoding="utf-8"))
        ontology_ids = {str(node["id"]) for node in graph.get("nodes", [])}
        for line in (root / manifest.rag_context_file).read_text(encoding="utf-8").splitlines():
            record = RagRecord.model_validate_json(line)
            missing_payloads = set(record.payload_ids) - payload_ids
            missing_ontology = set(record.ontology_ids) - ontology_ids
            missing_lineage = set(record.lineage_ids) - lineage_ids
            if missing_payloads or missing_ontology or missing_lineage:
                raise ValueError(
                    f"Invalid RAG references in {record.record_id}: "
                    f"payload={sorted(missing_payloads)}, ontology={sorted(missing_ontology)}, "
                    f"lineage={sorted(missing_lineage)}"
                )
            records.append(record)
    return tuple(records)


def _tokens(value: str) -> set[str]:
    return set(TOKEN_PATTERN.findall(value.casefold()))


def retrieve_records(
    records: Iterable[RagRecord],
    question: str,
    *,
    filter_state: Mapping[str, Any] | None = None,
    limit: int = 5,
) -> tuple[RagRecord, ...]:
    """Return locally ranked records whose declared filters do not conflict."""
    requested = dict(filter_state or {})
    query_tokens = _tokens(question)
    ranked: list[tuple[int, str, RagRecord]] = []
    for record in records:
        conflict = any(
            key in record.filter_state
            and str(record.filter_state[key]).casefold() != str(value).casefold()
            for key, value in requested.items()
        )
        if conflict:
            continue
        evidence_text = " ".join(
            [record.question_text, record.metric_definition, *record.calculated_observations]
        )
        score = len(query_tokens & _tokens(evidence_text))
        if score:
            ranked.append((score, record.record_id, record))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return tuple(item[2] for item in ranked[: max(0, limit)])


def answer_question(
    records: Iterable[RagRecord],
    question: str,
    *,
    filter_state: Mapping[str, Any] | None = None,
    asksage_client: AskSageClient | None = None,
) -> RagAnswer:
    """Answer from approved derived evidence and optionally request a bounded AI narrative."""
    requested = dict(filter_state or {})
    retrieved = retrieve_records(records, question, filter_state=requested)
    if not retrieved:
        return RagAnswer(
            question=question,
            interpreted_filter_state=requested,
            status="insufficient_evidence",
            observed_facts=(),
            limitations=("No approved retrieval packet matched the question and filter state.",),
            citation_labels=(),
            payload_ids=(),
            ontology_ids=(),
        )
    facts = tuple(
        dict.fromkeys(
            observation for record in retrieved for observation in record.calculated_observations
        )
    )
    limitations = tuple(dict.fromkeys(item for record in retrieved for item in record.limitations))
    citations = tuple(
        dict.fromkeys(item for record in retrieved for item in record.citation_labels)
    )
    payload_ids = tuple(dict.fromkeys(item for record in retrieved for item in record.payload_ids))
    ontology_ids = tuple(
        dict.fromkeys(item for record in retrieved for item in record.ontology_ids)
    )
    answer = RagAnswer(
        question=question,
        interpreted_filter_state=requested,
        status="answered",
        observed_facts=facts,
        interpretations=(),
        limitations=limitations,
        citation_labels=citations,
        payload_ids=payload_ids,
        ontology_ids=ontology_ids,
    )
    if asksage_client is None:
        return answer
    bounded_context = [
        {
            "record_id": record.record_id,
            "question_text": record.question_text,
            "filter_state": record.filter_state,
            "metric_definition": record.metric_definition,
            "calculated_values": list(record.calculated_values[:10]),
            "calculated_observations": record.calculated_observations,
            "limitations": record.limitations,
            "citation_labels": record.citation_labels,
        }
        for record in retrieved
    ]
    response = asksage_client.safe_chat_completion(
        [
            {
                "role": "system",
                "content": (
                    f"Prompt version {PROMPT_VERSION}. Summarize only the supplied aggregate "
                    "evidence. Separate observation from interpretation, state filters and conflicts, "
                    "and cite the supplied citation labels. Do not invent recommendations or citations."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"question": question, "filter_state": requested, "records": bounded_context},
                    ensure_ascii=False,
                ),
            },
        ]
    )
    if response["status"] != "available":
        return answer
    choices = response["response"].get("choices", [])
    content = choices[0].get("message", {}).get("content") if choices else None
    if not isinstance(content, str) or not content.strip():
        return answer
    return answer.model_copy(
        update={
            "ai_generated_narrative": content.strip(),
            "ai_prompt_version": PROMPT_VERSION,
            "ai_model": asksage_client.config.model,
            "ai_review_status": "pending_human_review",
        }
    )
