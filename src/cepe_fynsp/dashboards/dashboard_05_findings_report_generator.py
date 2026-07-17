"""Build Dashboard 5 deterministic findings and report-preparation artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, Mapping, cast

from cepe_fynsp.config import load_settings
from cepe_fynsp.dashboards.dashboard_01_pit_production import build_dashboard_01_payloads
from cepe_fynsp.dashboards.dashboard_02_acquisition_schedule import build_dashboard_02_payloads
from cepe_fynsp.dashboards.dashboard_03_site_capacity import build_dashboard_03_payloads
from cepe_fynsp.dashboards.dashboard_04_priority_challenge import build_dashboard_04_payloads
from cepe_fynsp.dashboards.dashboard_support import (
    COMMON_LIMITATIONS,
    format_dollars,
    load_pit_production_layers,
    make_payload,
    write_dashboard_artifacts,
    write_json,
)
from cepe_fynsp.reporting.report_outline import default_report_outline
from cepe_fynsp.schemas import Finding, FindingDisposition

DASHBOARD_ID = "dashboard_05_findings_report_generator"
DASHBOARD_TITLE = "CEPE Findings, Evidence, and Report Generator"
PRIOR_DASHBOARDS = [
    "dashboard_01_pit_production",
    "dashboard_02_acquisition_schedule",
    "dashboard_03_site_capacity",
    "dashboard_04_priority_challenge",
]

QUESTION_TEXT = {
    "q1": "What are the top accuracy findings for the Pit Production FYNSP?",
    "q2": "What are the top thoroughness findings?",
    "q3": "What are the most material uncertainties, risks, and opportunities?",
    "q4": "Which exhibits best support the findings?",
    "q5": "Which source rows and guidance passages support each statement?",
    "q6": "What should be included in the 5-7 page CEPE report?",
}

PAYLOAD_FILES = {
    "q1": "q1_accuracy_findings.json",
    "q2": "q2_thoroughness_findings.json",
    "q3": "q3_risk_opportunity_heatmap.json",
    "q4": "q4_exhibit_gallery.json",
    "q5": "q5_citation_lineage_graph.json",
    "q6": "q6_report_outline_status.json",
}


def _payload_path(root: Path, dashboard_id: str, filename: str) -> Path:
    """Return an artifact path below the established payload root."""
    return root / "data" / "curated" / "dashboard_payloads" / dashboard_id / filename


def _ensure_prior_dashboard_artifacts(root: Path) -> None:
    """Build missing upstream artifacts so Dashboard 5 has deterministic evidence."""
    builders = {
        "dashboard_01_pit_production": build_dashboard_01_payloads,
        "dashboard_02_acquisition_schedule": build_dashboard_02_payloads,
        "dashboard_03_site_capacity": build_dashboard_03_payloads,
        "dashboard_04_priority_challenge": build_dashboard_04_payloads,
    }
    for dashboard_id, builder in builders.items():
        if not _payload_path(root, dashboard_id, "manifest.json").exists():
            builder(root)


def load_dashboard_payloads(
    root: Path, dashboard_ids: list[str] = PRIOR_DASHBOARDS
) -> dict[str, dict[str, Any]]:
    """Read upstream manifests and payloads; only aggregate artifacts are loaded."""
    dashboards: dict[str, dict[str, Any]] = {}
    for dashboard_id in dashboard_ids:
        manifest_path = _payload_path(root, dashboard_id, "manifest.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        payloads = {}
        for entry in manifest["payloads"]:
            payloads[entry["question_id"]] = json.loads(
                _payload_path(root, dashboard_id, entry["file"]).read_text(encoding="utf-8")
            )
        dashboards[dashboard_id] = {"manifest": manifest, "payloads": payloads}
    return dashboards


def _finding(
    finding_id: str,
    title: str,
    finding_type: str,
    severity: str,
    *,
    affected_dollars: float | None,
    affected_row_count: int | None,
    source_dashboard_ids: list[str],
    source_chart_ids: list[str],
    limitations: list[str],
) -> dict[str, Any]:
    """Create a report-safe derived finding with explicit evidence references."""
    allowed_severity = cast(
        Literal["low", "medium", "high", "critical", "limitation", "not_evaluated"],
        severity
        if severity in {"low", "medium", "high", "critical", "limitation", "not_evaluated"}
        else "medium",
    )
    finding = Finding(
        finding_id=finding_id,
        rule_id=finding_id,
        severity=allowed_severity,
        category=finding_type,
        title=title,
        analytical_conclusion=(
            f"{title}. This deterministic result is a review trigger unless the cited evidence establishes otherwise."
        ),
        financial_exposure=affected_dollars,
        evidence=tuple(source_chart_ids),
        evidence_strength="moderate" if source_chart_ids else "limited",
    ).model_dump(mode="json")
    finding.update(
        {
            "finding_type": finding_type,
            "affected_dollars": affected_dollars,
            "affected_dollars_display": format_dollars(affected_dollars),
            "affected_row_count": affected_row_count,
            "source_dashboard_ids": source_dashboard_ids,
            "source_chart_ids": source_chart_ids,
            "limitations": limitations,
            "ownership_status": "missing" if not finding.get("owner") else "assigned",
        }
    )
    return finding


def apply_finding_dispositions(
    findings: list[dict[str, Any]], disposition_path: Path
) -> list[dict[str, Any]]:
    """Apply validated, separately maintained read-only finding dispositions when present."""
    if not disposition_path.exists():
        return findings
    payload = json.loads(disposition_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Finding disposition input must be a JSON array.")
    validated = [FindingDisposition.model_validate(record) for record in payload]
    disposition_ids = [item.finding_id for item in validated]
    duplicates = sorted({value for value in disposition_ids if disposition_ids.count(value) > 1})
    if duplicates:
        raise ValueError(f"Finding disposition input contains duplicate finding IDs: {duplicates}")
    known_ids = {str(finding["finding_id"]) for finding in findings}
    unknown = sorted(set(disposition_ids) - known_ids)
    if unknown:
        raise ValueError(f"Finding disposition input references unknown finding IDs: {unknown}")
    dispositions = {item.finding_id: item for item in validated}
    merged: list[dict[str, Any]] = []
    for finding in findings:
        updated = dict(finding)
        disposition = dispositions.get(str(finding["finding_id"]))
        if disposition:
            updated.update(disposition.model_dump(mode="json", exclude={"finding_id"}))
            updated["ownership_status"] = "assigned" if disposition.owner else "missing"
        merged.append(updated)
    return merged


def synthesize_accuracy_findings(
    dashboards: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Derive accuracy findings from prior dashboard evidence without inventing claims."""
    findings: list[dict[str, Any]] = []
    d1 = dashboards.get("dashboard_01_pit_production", {}).get("payloads", {})
    d2 = dashboards.get("dashboard_02_acquisition_schedule", {}).get("payloads", {})
    d4 = dashboards.get("dashboard_04_priority_challenge", {}).get("payloads", {})
    reconciliation = d1.get("q6", {})
    variance = sum(
        abs(float(row.get("variance_amount", 0.0))) for row in reconciliation.get("data", [])
    )
    findings.append(
        _finding(
            "accuracy_reconciliation",
            "Federal Crosscuts and Federal Site Splits reconciliation evidence",
            "accuracy",
            "high" if variance > 1 else "low",
            affected_dollars=variance,
            affected_row_count=1 if variance > 1 else 0,
            source_dashboard_ids=["dashboard_01_pit_production"],
            source_chart_ids=[reconciliation.get("chart_id", "dashboard_01_pit_production_q6")],
            limitations=[
                "The two layers have different analytic grain; a variance is a review trigger, not a confirmed error."
            ],
        )
    )
    schedule = d2.get("q4", {})
    for row in schedule.get("data", []):
        if row.get("status") == "evaluated" and int(row.get("row_count", 0)) > 0:
            findings.append(
                _finding(
                    f"accuracy_{row.get('rule_id')}",
                    str(row.get("title", "Acquisition schedule metadata review trigger")),
                    "accuracy",
                    str(row.get("severity", "medium")),
                    affected_dollars=row.get("affected_dollars"),
                    affected_row_count=int(row.get("row_count", 0)),
                    source_dashboard_ids=["dashboard_02_acquisition_schedule"],
                    source_chart_ids=[
                        schedule.get("chart_id", "dashboard_02_acquisition_schedule_q4")
                    ],
                    limitations=[
                        "Schedule exceptions are deterministic review triggers, not validated acquisition-status conclusions."
                    ],
                )
            )
    tiers = d4.get("q2", {})
    for row in tiers.get("data", []):
        if row.get("tier1_above_baseline_review_trigger"):
            findings.append(
                _finding(
                    "accuracy_tier1_above_baseline",
                    "Tier 1 above-baseline consistency review trigger",
                    "accuracy",
                    "high",
                    affected_dollars=float(row.get("amount", 0.0)),
                    affected_row_count=int(row.get("row_count", 0)),
                    source_dashboard_ids=["dashboard_04_priority_challenge"],
                    source_chart_ids=[tiers.get("chart_id", "dashboard_04_priority_challenge_q2")],
                    limitations=[
                        "Tier 1 ROT/UFR rows should be reviewed for consistency with guidance; they are not automatic errors."
                    ],
                )
            )
    classes = d4.get("q4", {})
    for row in classes.get("data", []):
        if row.get("negative_dollar_review_trigger"):
            findings.append(
                _finding(
                    "accuracy_negative_dollar_offsets",
                    "Negative-dollar offset or restoration traceability review",
                    "accuracy",
                    "medium",
                    affected_dollars=abs(float(row.get("amount", 0.0))),
                    affected_row_count=None,
                    source_dashboard_ids=["dashboard_04_priority_challenge"],
                    source_chart_ids=[
                        classes.get("chart_id", "dashboard_04_priority_challenge_q4")
                    ],
                    limitations=[
                        "Negative dollars may be offsets, restorations, or corrections and are not automatically errors."
                    ],
                )
            )
    findings.append(
        _finding(
            "accuracy_submission_layer_discipline",
            "Submission-layer mixing risk must remain controlled",
            "accuracy",
            "medium",
            affected_dollars=None,
            affected_row_count=None,
            source_dashboard_ids=["dashboard_01_pit_production"],
            source_chart_ids=["dashboard_01_pit_production_q6"],
            limitations=[
                "FORMEX submission layers are overlapping views and cannot be summed together."
            ],
        )
    )
    return findings


def build_coverage_matrix(dashboards: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Build a coverage matrix from Dashboard 2 and 4 completeness evidence."""
    d2 = dashboards.get("dashboard_02_acquisition_schedule", {}).get("payloads", {})
    d4 = dashboards.get("dashboard_04_priority_challenge", {}).get("payloads", {})
    traceability = d4.get("q5", {}).get("data", [])
    coverage_keys = {
        "scope_description": "Scope description",
        "program_request": "Program request",
        "wbs": "WBS",
        "bnr": "BNR",
        "site": "Site",
        "acquisition": "Acquisition ID/name/type",
        "fiscal_year": "Fiscal year",
        "funding_level": "Funding level",
    }
    records = []
    for key, label in coverage_keys.items():
        values = [row.get("component_coverage", {}).get(key) for row in traceability]
        valid = [float(value) for value in values if isinstance(value, (int, float))]
        records.append(
            {
                "coverage_category": label,
                "coverage_rate": sum(valid) / len(valid) if valid else None,
                "covered_request_count": sum(value == 1.0 for value in valid),
                "request_count": len(valid),
                "affected_dollars": None,
                "evidence_chart_id": d4.get("q5", {}).get("chart_id"),
                "status": "derived" if valid else "not_available",
            }
        )
    schedule_rows = d2.get("q4", {}).get("data", [])
    schedule_by_rule = {row.get("rule_id"): row for row in schedule_rows}
    for label, rule_ids in {
        "Acquisition ID": ["AQ001"],
        "Acquisition name": ["AQ002"],
        "Acquisition dates": ["AQ003", "AQ004", "AQ005", "AQ006"],
    }.items():
        evaluated = [
            schedule_by_rule[item]
            for item in rule_ids
            if schedule_by_rule.get(item, {}).get("status") == "evaluated"
        ]
        row_count = sum(int(item.get("row_count", 0)) for item in evaluated)
        dollars = sum(float(item.get("affected_dollars", 0.0) or 0.0) for item in evaluated)
        records.append(
            {
                "coverage_category": label,
                "coverage_rate": None,
                "covered_request_count": None,
                "request_count": row_count,
                "affected_dollars": dollars if evaluated else None,
                "evidence_chart_id": d2.get("q4", {}).get("chart_id"),
                "status": "exception_evidence" if evaluated else "not_available",
            }
        )
    priority_rows = d4.get("q3", {}).get("data", [])
    blank_priority = sum(
        int(row.get("row_count", 0))
        for row in priority_rows
        if row.get("program_priority") in {"Blank", "Zero"}
    )
    records.append(
        {
            "coverage_category": "Program priority",
            "coverage_rate": None,
            "covered_request_count": None,
            "request_count": blank_priority,
            "affected_dollars": None,
            "evidence_chart_id": d4.get("q3", {}).get("chart_id"),
            "status": "exception_evidence",
        }
    )
    tier_rows = d4.get("q2", {}).get("data", [])
    missing_tier = sum(
        int(row.get("row_count", 0))
        for row in tier_rows
        if row.get("doe_priority_tier") == "Unspecified"
    )
    records.append(
        {
            "coverage_category": "DOE priority tier",
            "coverage_rate": None,
            "covered_request_count": None,
            "request_count": missing_tier,
            "affected_dollars": None,
            "evidence_chart_id": d4.get("q2", {}).get("chart_id"),
            "status": "exception_evidence",
        }
    )
    for row in d4.get("q6", {}).get("data", []):
        label = (
            "Account Integrator decision"
            if row.get("rule_id") == "FQ007"
            else "Account Integrator priority"
        )
        records.append(
            {
                "coverage_category": label,
                "coverage_rate": None,
                "covered_request_count": None,
                "request_count": row.get("row_count"),
                "affected_dollars": row.get("affected_dollars"),
                "evidence_chart_id": d4.get("q6", {}).get("chart_id"),
                "status": row.get("status", "not_available"),
            }
        )
    return records


def build_risk_opportunity_heatmap(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map evidence-backed findings to deterministic review themes and severity."""
    theme_map = {
        "reconciliation": "reconciliation",
        "schedule": "acquisition schedule",
        "tier": "priority defensibility",
        "negative": "traceability",
        "submission": "data quality",
    }
    records = []
    for finding in findings:
        identifier = finding["finding_id"]
        theme = next(
            (mapped for key, mapped in theme_map.items() if key in identifier), "data quality"
        )
        records.append(
            {
                "theme": theme,
                "severity": finding["severity"],
                "materiality": finding["affected_dollars"],
                "materiality_display": finding["affected_dollars_display"],
                "finding_id": identifier,
                "finding_type": finding["finding_type"],
                "evidence_status": "derived finding",
            }
        )
    records.extend(
        [
            {
                "theme": "site executability",
                "severity": "medium",
                "materiality": None,
                "materiality_display": "Not available",
                "finding_id": "site_capacity_review",
                "finding_type": "review trigger",
                "evidence_status": "See Dashboard 3 site surges and dependency exhibits.",
            },
            {
                "theme": "above-baseline dependency",
                "severity": "medium",
                "materiality": None,
                "materiality_display": "Not available",
                "finding_id": "above_baseline_dependency_review",
                "finding_type": "review trigger",
                "evidence_status": "See Dashboard 3 above-baseline dependency exhibit.",
            },
            {
                "theme": "opportunity / acceleration",
                "severity": "low",
                "materiality": None,
                "materiality_display": "Not available",
                "finding_id": "opportunity_pending_evidence",
                "finding_type": "data limitation",
                "evidence_status": "No deterministic opportunity finding is asserted; analyst evidence or guidance is needed.",
            },
        ]
    )
    return records


def build_exhibit_gallery(dashboards: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return report-insertion metadata for every upstream chart payload."""
    exhibits = []
    for dashboard_id, dashboard in dashboards.items():
        manifest = dashboard["manifest"]
        payloads = dashboard["payloads"]
        for entry in manifest["payloads"]:
            payload = payloads[entry["question_id"]]
            exhibits.append(
                {
                    "dashboard_id": dashboard_id,
                    "chart_id": payload["chart_id"],
                    "question_text": payload["question_text"],
                    "chart_title": payload["chart_title"],
                    "payload_path": f"data/curated/dashboard_payloads/{dashboard_id}/{entry['file']}",
                    "source_layer": payload["traceability"]["source_submission_type"],
                    "metric_definition": payload["metric_definition"],
                    "why_it_supports_findings": "Traceable aggregate exhibit for the associated natural-language review question.",
                }
            )
    return exhibits


def build_citation_lineage(
    findings: list[dict[str, Any]], exhibits: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Create citation-lineage table records with explicit pending guidance references."""
    exhibits_by_dashboard: dict[str, list[dict[str, Any]]] = {}
    for exhibit in exhibits:
        exhibits_by_dashboard.setdefault(exhibit["dashboard_id"], []).append(exhibit)
    records = []
    for finding in findings:
        for dashboard_id, chart_id in zip(
            finding["source_dashboard_ids"], finding["source_chart_ids"], strict=True
        ):
            exhibit = next(
                (
                    item
                    for item in exhibits_by_dashboard.get(dashboard_id, [])
                    if item["chart_id"] == chart_id
                ),
                {},
            )
            records.append(
                {
                    "finding_id": finding["finding_id"],
                    "dashboard_id": dashboard_id,
                    "chart_id": chart_id,
                    "payload_path": exhibit["payload_path"]
                    if exhibit
                    else "pending payload reference",
                    "rag_chunk_file": f"data/curated/rag_chunks/{dashboard_id}/dashboard_{dashboard_id.split('_')[1]}_context.jsonl",
                    "ontology_graph_file": f"data/ontology/{dashboard_id}_graph.json",
                    "guidance_reference": "pending guidance chunk ingestion",
                    "lineage_status": "aggregate source-row identifiers retained in payload traceability",
                }
            )
    return records


def create_report_manifest(
    root: Path,
    metadata: Mapping[str, Any],
    findings: list[dict[str, Any]],
    exhibits: list[dict[str, Any]],
) -> dict[str, Any]:
    """Write the evidence manifest consumed by the deterministic report generator."""
    report_manifest = {
        "schema_version": "1.0",
        "report_id": "cepe_pit_production_fynsp_review_draft",
        "generated_at": metadata["generated_at"],
        "status": "evidence_manifest_ready",
        "target_length": "5-7 pages",
        "sections": default_report_outline(),
        "exhibits": exhibits,
        "finding_ids": [finding["finding_id"] for finding in findings],
        "citation_requirements": "Each report claim must cite chart IDs, source-row lineage where available, and guidance chunks when ingested.",
        "limitations": [
            "The complete CLI build invokes the DOCX generator after dashboard validation.",
            "Guidance citations remain pending guidance chunk ingestion.",
            "Live AskSage drafting is optional and is not required.",
        ],
    }
    write_json(
        root / "data" / "reports" / "html" / "dashboard_05_report_manifest.json", report_manifest
    )
    return report_manifest


def build_dashboard_05_payloads(project_root: Path | None = None) -> dict[str, Any]:
    """Build Dashboard 5 by synthesizing deterministic Dashboard 1-4 artifacts."""
    root, _, _, metadata = load_pit_production_layers(project_root)
    _ensure_prior_dashboard_artifacts(root)
    dashboards = load_dashboard_payloads(root)
    accuracy = synthesize_accuracy_findings(dashboards)
    settings = load_settings(project_root=root)
    accuracy = apply_finding_dispositions(
        accuracy, settings.resolve_path(settings.paths.finding_dispositions)
    )
    coverage = build_coverage_matrix(dashboards)
    risks = build_risk_opportunity_heatmap(accuracy)
    exhibits = build_exhibit_gallery(dashboards)
    lineage = build_citation_lineage(accuracy, exhibits)
    report_manifest = create_report_manifest(root, metadata, accuracy, exhibits)
    limitations = COMMON_LIMITATIONS + [
        "Dashboard 5 synthesizes generated dashboard artifacts; it does not independently validate raw source rows.",
        "Guidance references are marked pending until approved guidance chunks are ingested.",
        "The deterministic report generator runs after all five dashboards validate; live AskSage drafting remains optional.",
    ]
    derived_source = "Derived findings from Dashboard 1-4 aggregate payloads"
    payloads = {
        "q1": make_payload(
            dashboard_id=DASHBOARD_ID,
            dashboard_title=DASHBOARD_TITLE,
            question_id="q1",
            question_text=QUESTION_TEXT["q1"],
            chart_type="finding_cards",
            chart_title="Top accuracy findings",
            metric_definition="Deterministic accuracy findings synthesized from Dashboard 1-4 aggregate payloads and their traceability metadata.",
            source_submission_type=derived_source,
            row_filter={"dashboard_ids": PRIOR_DASHBOARDS},
            grouping_columns=["finding_type", "severity"],
            value_column="affected_dollars",
            record_count=len(accuracy),
            data=accuracy,
            summary=f"{len(accuracy)} evidence-linked accuracy findings or review controls are available.",
            limitations=limitations,
            lineage={"source_dashboard_ids": PRIOR_DASHBOARDS, "source_row_id_count": None},
            metric_cards=[
                {
                    "label": "Accuracy findings",
                    "value": len(accuracy),
                    "display": str(len(accuracy)),
                }
            ],
            metadata=metadata,
        ),
        "q2": make_payload(
            dashboard_id=DASHBOARD_ID,
            dashboard_title=DASHBOARD_TITLE,
            question_id="q2",
            question_text=QUESTION_TEXT["q2"],
            chart_type="coverage_matrix",
            chart_title="Thoroughness coverage matrix",
            metric_definition="Coverage and exception evidence derived from Dashboard 2 acquisition checks and Dashboard 4 traceability/priority checks.",
            source_submission_type=derived_source,
            row_filter={
                "dashboard_ids": [
                    "dashboard_02_acquisition_schedule",
                    "dashboard_04_priority_challenge",
                ]
            },
            grouping_columns=["coverage_category"],
            value_column="coverage rate or affected dollars",
            record_count=len(coverage),
            data=coverage,
            summary=f"{len(coverage)} traceability and metadata coverage categories are presented for review.",
            limitations=limitations,
            lineage={
                "source_dashboard_ids": [
                    "dashboard_02_acquisition_schedule",
                    "dashboard_04_priority_challenge",
                ],
                "source_row_id_count": None,
            },
            metric_cards=[
                {
                    "label": "Coverage categories",
                    "value": len(coverage),
                    "display": str(len(coverage)),
                }
            ],
            metadata=metadata,
        ),
        "q3": make_payload(
            dashboard_id=DASHBOARD_ID,
            dashboard_title=DASHBOARD_TITLE,
            question_id="q3",
            question_text=QUESTION_TEXT["q3"],
            chart_type="risk_opportunity_heatmap_table",
            chart_title="Material uncertainties, risks, and opportunities",
            metric_definition="Deterministic mapping of evidence-linked findings to review themes and severity/materiality fields.",
            source_submission_type=derived_source,
            row_filter={"finding_source": "Dashboards 1-4"},
            grouping_columns=["theme", "severity"],
            value_column="materiality",
            record_count=len(risks),
            data=risks,
            summary="Risk and opportunity entries distinguish evidence-linked findings, review triggers, and unavailable opportunity evidence.",
            limitations=limitations,
            lineage={"source_dashboard_ids": PRIOR_DASHBOARDS, "source_row_id_count": None},
            metric_cards=[
                {
                    "label": "Review themes",
                    "value": len({row["theme"] for row in risks}),
                    "display": str(len({row["theme"] for row in risks})),
                }
            ],
            metadata=metadata,
        ),
        "q4": make_payload(
            dashboard_id=DASHBOARD_ID,
            dashboard_title=DASHBOARD_TITLE,
            question_id="q4",
            question_text=QUESTION_TEXT["q4"],
            chart_type="exhibit_gallery_table",
            chart_title="Report-ready dashboard exhibits",
            metric_definition="Manifest and payload metadata from Dashboards 1-4, retained for report exhibit selection and citation.",
            source_submission_type=derived_source,
            row_filter={"dashboard_ids": PRIOR_DASHBOARDS},
            grouping_columns=["dashboard_id", "chart_id"],
            value_column="not applicable",
            record_count=len(exhibits),
            data=exhibits,
            summary=f"{len(exhibits)} traceable chart exhibits are available for a future report draft.",
            limitations=limitations,
            lineage={"source_dashboard_ids": PRIOR_DASHBOARDS, "source_row_id_count": None},
            metric_cards=[
                {
                    "label": "Available exhibits",
                    "value": len(exhibits),
                    "display": str(len(exhibits)),
                }
            ],
            metadata=metadata,
        ),
        "q5": make_payload(
            dashboard_id=DASHBOARD_ID,
            dashboard_title=DASHBOARD_TITLE,
            question_id="q5",
            question_text=QUESTION_TEXT["q5"],
            chart_type="citation_lineage_table",
            chart_title="Finding citation and source-lineage references",
            metric_definition="Finding-to-chart, payload, RAG packet, and ontology graph references; guidance is explicitly marked pending when not ingested.",
            source_submission_type=derived_source,
            row_filter={"finding_source": "Dashboard 1-4 artifacts"},
            grouping_columns=["finding_id", "chart_id"],
            value_column="not applicable",
            record_count=len(lineage),
            data=lineage,
            summary=f"{len(lineage)} evidence-path records connect findings to generated artifacts; guidance chunks are pending ingestion.",
            limitations=limitations,
            lineage={"source_dashboard_ids": PRIOR_DASHBOARDS, "source_row_id_count": None},
            metric_cards=[
                {
                    "label": "Citation-lineage records",
                    "value": len(lineage),
                    "display": str(len(lineage)),
                }
            ],
            metadata=metadata,
        ),
        "q6": make_payload(
            dashboard_id=DASHBOARD_ID,
            dashboard_title=DASHBOARD_TITLE,
            question_id="q6",
            question_text=QUESTION_TEXT["q6"],
            chart_type="report_outline_status",
            chart_title="CEPE report outline and generation status",
            metric_definition="Structured report evidence manifest consumed by the deterministic DOCX/HTML report generator after all dashboard payloads validate.",
            source_submission_type=derived_source,
            row_filter={"report_manifest": "data/reports/html/dashboard_05_report_manifest.json"},
            grouping_columns=["section"],
            value_column="not applicable",
            record_count=len(report_manifest["sections"]),
            data=[
                {
                    "section_number": index + 1,
                    "section": section,
                    "report_status": report_manifest["status"],
                }
                for index, section in enumerate(report_manifest["sections"])
            ],
            summary="The complete CLI build generates a deterministic Word-compatible report, HTML companion, exhibits, and citation manifest without requiring AskSage.",
            limitations=limitations,
            lineage={"source_dashboard_ids": PRIOR_DASHBOARDS, "source_row_id_count": None},
            metric_cards=[
                {
                    "label": "Report sections",
                    "value": len(report_manifest["sections"]),
                    "display": str(len(report_manifest["sections"])),
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
        extra_manifest={
            "report_manifest_file": "data/reports/html/dashboard_05_report_manifest.json",
            "upstream_dashboards": PRIOR_DASHBOARDS,
        },
    )


if __name__ == "__main__":  # pragma: no cover
    print(build_dashboard_05_payloads())
