"""Unit tests for Dashboard 5 deterministic findings and report artifacts."""

from __future__ import annotations

from cepe_fynsp.dashboards.dashboard_05_findings_report_generator import (
    build_citation_lineage,
    build_coverage_matrix,
    build_exhibit_gallery,
    create_report_manifest,
    synthesize_accuracy_findings,
)


def _dashboards() -> dict:
    return {
        "dashboard_01_pit_production": {"manifest": {"payloads": [{"question_id": "q6", "file": "q6.json"}]}, "payloads": {"q6": {"chart_id": "d1q6", "question_text": "Reconcile?", "chart_title": "Reconcile", "metric_definition": "variance", "traceability": {"source_submission_type": "Federal Crosscuts"}, "data": [{"variance_amount": 25.0}]}}},
        "dashboard_02_acquisition_schedule": {"manifest": {"payloads": [{"question_id": "q4", "file": "q4.json"}]}, "payloads": {"q4": {"chart_id": "d2q4", "question_text": "Dates?", "chart_title": "Dates", "metric_definition": "checks", "traceability": {"source_submission_type": "Federal Crosscuts"}, "data": [{"rule_id": "AQ003", "title": "Missing start", "status": "evaluated", "severity": "high", "row_count": 2, "affected_dollars": 20.0}]}}},
        "dashboard_03_site_capacity": {"manifest": {"payloads": [{"question_id": "q1", "file": "q1.json"}]}, "payloads": {"q1": {"chart_id": "d3q1", "question_text": "Sites?", "chart_title": "Sites", "metric_definition": "sites", "traceability": {"source_submission_type": "Federal Site Splits"}, "data": []}}},
        "dashboard_04_priority_challenge": {"manifest": {"payloads": [{"question_id": key, "file": f"{key}.json"} for key in ["q2", "q3", "q4", "q5", "q6"]]}, "payloads": {
            "q2": {"chart_id": "d4q2", "question_text": "Tiers?", "chart_title": "Tiers", "metric_definition": "tiers", "traceability": {"source_submission_type": "Federal Crosscuts"}, "data": [{"funding_level": "ROT", "doe_priority_tier": "1", "tier1_above_baseline_review_trigger": True, "amount": 50.0, "row_count": 1}]},
            "q3": {"chart_id": "d4q3", "question_text": "Priority?", "chart_title": "Priority", "metric_definition": "priority", "traceability": {"source_submission_type": "Federal Crosscuts"}, "data": [{"program_priority": "Blank", "row_count": 3}]},
            "q4": {"chart_id": "d4q4", "question_text": "Offsets?", "chart_title": "Offsets", "metric_definition": "intent", "traceability": {"source_submission_type": "Federal Crosscuts"}, "data": [{"negative_dollar_review_trigger": True, "amount": -5.0}]},
            "q5": {"chart_id": "d4q5", "question_text": "Trace?", "chart_title": "Trace", "metric_definition": "coverage", "traceability": {"source_submission_type": "Federal Crosscuts"}, "data": [{"component_coverage": {"scope_description": 1.0, "program_request": 0.5, "wbs": 1.0, "bnr": 1.0, "site": 1.0, "acquisition": 0.5, "fiscal_year": 1.0, "funding_level": 1.0}}]},
            "q6": {"chart_id": "d4q6", "question_text": "AI?", "chart_title": "AI", "metric_definition": "AI", "traceability": {"source_submission_type": "Federal Crosscuts"}, "data": [{"rule_id": "FQ007", "row_count": 4, "affected_dollars": 100.0, "status": "evaluated"}, {"rule_id": "FQ008", "row_count": 4, "affected_dollars": 100.0, "status": "evaluated"}]},
        }},
    }


def test_findings_synthesis_and_coverage_matrix() -> None:
    dashboards = _dashboards()
    findings = synthesize_accuracy_findings(dashboards)
    coverage = build_coverage_matrix(dashboards)
    assert any(row["finding_id"] == "accuracy_reconciliation" for row in findings)
    assert any(row["coverage_category"] == "Scope description" for row in coverage)
    assert any(row["coverage_category"] == "Account Integrator decision" for row in coverage)


def test_exhibit_gallery_and_citation_lineage() -> None:
    dashboards = _dashboards()
    exhibits = build_exhibit_gallery(dashboards)
    lineage = build_citation_lineage(synthesize_accuracy_findings(dashboards), exhibits)
    assert len(exhibits) == 8
    assert lineage
    assert all(row["guidance_reference"] == "pending guidance chunk ingestion" for row in lineage)


def test_report_manifest_creation(tmp_path) -> None:
    dashboards = _dashboards()
    findings = synthesize_accuracy_findings(dashboards)
    exhibits = build_exhibit_gallery(dashboards)
    manifest = create_report_manifest(tmp_path, {"generated_at": "2026-07-16T00:00:00+00:00"}, findings, exhibits)
    assert manifest["status"] == "manifest_ready_docx_not_generated"
    assert (tmp_path / "data" / "reports" / "html" / "dashboard_05_report_manifest.json").exists()
