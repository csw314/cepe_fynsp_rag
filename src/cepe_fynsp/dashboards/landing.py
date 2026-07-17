"""Generated executive landing-page summary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cepe_fynsp.dashboards.dashboard_support import format_dollars, write_json
from cepe_fynsp.schemas import DashboardManifest, DashboardQuestionPayload, SCHEMA_VERSION


def _payload(root: Path, dashboard_id: str, question_id: str) -> DashboardQuestionPayload:
    """Load one payload through its validated dashboard manifest."""
    directory = root / "data" / "curated" / "dashboard_payloads" / dashboard_id
    manifest = DashboardManifest.model_validate_json(
        (directory / "manifest.json").read_text(encoding="utf-8")
    )
    entry = next(item for item in manifest.payloads if item.question_id == question_id)
    return DashboardQuestionPayload.model_validate_json(
        (directory / entry.file).read_text(encoding="utf-8")
    )


def build_landing_summary(project_root: Path) -> dict[str, Any]:
    """Build aggregate-only portfolio metrics for the executive landing page."""
    root = project_root.resolve()
    funding = _payload(root, "dashboard_01_pit_production", "q1")
    above = _payload(root, "dashboard_01_pit_production", "q4")
    sites = _payload(root, "dashboard_01_pit_production", "q3")
    reconciliation = _payload(root, "dashboard_01_pit_production", "q6")
    findings = _payload(root, "dashboard_05_findings_report_generator", "q1")
    programmed = sum(float(row.get("amount") or 0) for row in funding.data)
    above_baseline = sum(float(row.get("amount") or 0) for row in above.data)
    critical = sum(str(row.get("severity")) == "critical" for row in findings.data)
    high = sum(str(row.get("severity")) == "high" for row in findings.data)
    leading_site = sites.data[0] if sites.data else {}
    completeness = funding.quality_summary.financial_completeness.get("completeness_percentage")
    source_profile_path = root / "data" / "curated" / "source_profiles" / "source_manifest.json"
    source_health = (
        json.loads(source_profile_path.read_text(encoding="utf-8"))
        if source_profile_path.exists()
        else {"overall_status": "NOT EVALUATED", "sources": []}
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "title": "CEPE FYNSP Pit Production Executive Portfolio Summary",
        "generated_at": funding.generated_at,
        "metrics": [
            {
                "label": "Programmed funding",
                "value": programmed,
                "display": format_dollars(programmed),
                "payload_id": funding.chart_id,
            },
            {
                "label": "Above-baseline request",
                "value": above_baseline,
                "display": format_dollars(above_baseline),
                "payload_id": above.chart_id,
            },
            {
                "label": "Critical / high findings",
                "value": critical + high,
                "display": f"{critical} critical / {high} high",
                "payload_id": findings.chart_id,
            },
            {
                "label": "Reconciliation",
                "value": reconciliation.quality_summary.reconciliation_status,
                "display": reconciliation.quality_summary.reconciliation_status.replace(
                    "_", " "
                ).title(),
                "payload_id": reconciliation.chart_id,
            },
            {
                "label": "FORMEX completeness",
                "value": completeness,
                "display": f"{float(completeness):.2f}%"
                if completeness is not None
                else "Not available",
                "payload_id": funding.chart_id,
            },
            {
                "label": "Leading site concentration",
                "value": leading_site.get("share_of_total"),
                "display": f"{leading_site.get('site', 'Not available')} · {float(leading_site.get('share_of_total') or 0):.1%}",
                "payload_id": sites.chart_id,
            },
        ],
        "highest_priority_actions": [
            "Review high-severity deterministic findings and assign controlled dispositions.",
            "Resolve material Crosscuts-to-Site-Splits variances before relying on site totals.",
            "Obtain an approved crosswalk before detailed FORMEX-to-PLANEX/COSTEX reconciliation.",
        ],
        "data_health": funding.quality_summary.model_dump(mode="json"),
        "source_health": source_health,
        "source_payload_ids": [
            funding.chart_id,
            above.chart_id,
            sites.chart_id,
            reconciliation.chart_id,
            findings.chart_id,
        ],
    }
    write_json(root / "data" / "curated" / "dashboard_payloads" / "landing_summary.json", payload)
    return payload
