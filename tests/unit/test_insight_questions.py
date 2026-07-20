"""Five-dashboard prepared-question inventory and payload mapping tests."""

from __future__ import annotations

from cepe_fynsp.dashboards.insight_questions import (
    INSIGHT_QUESTIONS,
    insight_ui_config,
    validate_insight_question_inventory,
)


def test_all_thirty_prepared_questions_are_typed_and_nonblank() -> None:
    validate_insight_question_inventory()
    assert len(INSIGHT_QUESTIONS) == 5
    assert all(len(questions) == 6 for questions in INSIGHT_QUESTIONS.values())
    assert sum(len(questions) for questions in INSIGHT_QUESTIONS.values()) == 30
    for dashboard_id, questions in INSIGHT_QUESTIONS.items():
        for question_id, expected in questions.items():
            config = insight_ui_config(dashboard_id, question_id)
            assert config.enabled
            assert config.suggested_question == expected
            assert config.context_version == "1.0"


def test_expected_questions_map_to_representative_visualizations() -> None:
    assert INSIGHT_QUESTIONS["dashboard_01_pit_production"]["q1"].startswith("Which fiscal year")
    assert "LI TEC or LI OPC" in INSIGHT_QUESTIONS["dashboard_02_acquisition_schedule"]["q5"]
    assert "top three sites" in INSIGHT_QUESTIONS["dashboard_03_site_capacity"]["q1"]
    assert "Account Integrator" in INSIGHT_QUESTIONS["dashboard_04_priority_challenge"]["q6"]
    assert (
        "three most important management conclusions"
        in (INSIGHT_QUESTIONS["dashboard_05_findings_report_generator"]["q6"])
    )
