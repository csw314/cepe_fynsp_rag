"""Authoritative prepared questions for dashboard visualization insights."""

from __future__ import annotations

from types import MappingProxyType

from cepe_fynsp.schemas import InsightUiConfig

_QUESTIONS: dict[str, dict[str, str]] = {
    "dashboard_01_pit_production": {
        "q1": "Which fiscal year and funding level drives the largest change in total funding, and which programs explain that change?",
        "q2": "How concentrated is funding among the top organizations, and which organization creates the greatest portfolio dependency?",
        "q3": "Which sites account for most funding, and where does site concentration create the greatest execution or integration risk?",
        "q4": "Which above-baseline requests contribute most to the total ask, and are the largest requests aligned with the highest priorities?",
        "q5": "Which data-quality issue affects the most dollars and should be resolved first?",
        "q6": "Where are Crosscut and Site Split variances largest, and are they explainable by submission-layer structure or missing data?",
    },
    "dashboard_02_acquisition_schedule": {
        "q1": "Which acquisition categories have the largest untagged or above-baseline funding exposure?",
        "q2": "Which high-dollar acquisition lines combine material funding with weak descriptive or schedule evidence?",
        "q3": "Which funding profiles appear misaligned with acquisition start and end dates, and what drives the misalignment?",
        "q4": "Which date anomalies create the greatest uncertainty in executability analysis?",
        "q5": "Which site-year combinations have the greatest LI TEC or LI OPC concentration or imbalance?",
        "q6": "Which above-baseline acquisition requests are both high-dollar and high-priority but have the weakest schedule or traceability support?",
    },
    "dashboard_03_site_capacity": {
        "q1": "How much of total site funding is concentrated in the top three sites, and what does that imply for portfolio resilience?",
        "q2": "Which sites show the largest cumulative funding growth or decline across FY2028–FY2032?",
        "q3": "Which sites would experience the largest funding shortfall if above-baseline requests were not approved?",
        "q4": "Which organization-to-site relationships create the most significant cross-organizational integration burden?",
        "q5": "Which site funding surge or cliff is most material, and which programs or funding levels drive it?",
        "q6": "Which missing descriptive fields most often prevent a defensible site-level review?",
    },
    "dashboard_04_priority_challenge": {
        "q1": "What share of the total ROT and UFR request is concentrated in the largest requests, and which requests dominate?",
        "q2": "Which Tier 1 above-baseline requests require the strongest challenge because of amount, evidence gaps, or prioritization ambiguity?",
        "q3": "Where are priorities duplicated or nonsequential, and how much funding is affected?",
        "q4": "Which negative and positive requests appear related, and what evidence supports treating them as offsets, restorations, or delays?",
        "q5": "Which high-dollar requests have the weakest end-to-end traceability from title through acquisition and site?",
        "q6": "How much funding lacks Account Integrator decision traceability, and which organizations contribute most to the gap?",
    },
    "dashboard_05_findings_report_generator": {
        "q1": "Which accuracy finding has the highest combination of severity, financial exposure, and evidence strength?",
        "q2": "Which coverage gap most limits a complete CEPE review, and what additional evidence is needed?",
        "q3": "Which risk or opportunity is most material after considering likelihood, dollar exposure, and affected sites?",
        "q4": "Which exhibit provides the strongest support for the highest-priority finding, and what does it demonstrate?",
        "q5": "Are the most material findings supported by complete and consistent source-row, document, and ontology citations?",
        "q6": "What are the three most important management conclusions and actions that the final CEPE report should contain?",
    },
}

INSIGHT_QUESTIONS = MappingProxyType(
    {dashboard_id: MappingProxyType(questions) for dashboard_id, questions in _QUESTIONS.items()}
)


def insight_ui_config(dashboard_id: str, question_id: str) -> InsightUiConfig:
    """Return the one prepared question configured for a dashboard visualization."""
    try:
        question = INSIGHT_QUESTIONS[dashboard_id][question_id]
    except KeyError as exc:
        raise ValueError(
            f"Missing prepared insights question for {dashboard_id}/{question_id}."
        ) from exc
    return InsightUiConfig(suggested_question=question)


def validate_insight_question_inventory() -> None:
    """Reject missing, extra, or blank entries in the five-by-six inventory."""
    expected_dashboards = {
        "dashboard_01_pit_production",
        "dashboard_02_acquisition_schedule",
        "dashboard_03_site_capacity",
        "dashboard_04_priority_challenge",
        "dashboard_05_findings_report_generator",
    }
    if set(INSIGHT_QUESTIONS) != expected_dashboards:
        raise ValueError("Prepared insights inventory must contain exactly five dashboards.")
    expected_questions = {f"q{index}" for index in range(1, 7)}
    for dashboard_id, questions in INSIGHT_QUESTIONS.items():
        if set(questions) != expected_questions or any(
            not text.strip() for text in questions.values()
        ):
            raise ValueError(
                f"Prepared insights inventory for {dashboard_id} must contain six nonblank questions."
            )


validate_insight_question_inventory()
