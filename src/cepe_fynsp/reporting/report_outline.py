"""Report outline helpers."""

from __future__ import annotations


def default_report_outline() -> list[str]:
    """Return the required CEPE report section titles."""
    return [
        "Executive Summary",
        "Review Scope and Data Sources",
        "Dashboard Question Answers",
        "Accuracy Findings",
        "Thoroughness Findings",
        "Uncertainty, Risk, and Opportunity Findings",
        "Data Limitations and Recommended Follow-Up",
        "Appendix: Source Lineage and Guidance Citations",
    ]
