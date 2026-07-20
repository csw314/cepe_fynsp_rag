"""Static security, accessibility, and shared-renderer regression tests for insights."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RENDERER = ROOT / "web" / "assets" / "js" / "dashboard_renderer.js"


def test_frontend_uses_one_shared_control_without_credentials_or_asksage_url() -> None:
    source = RENDERER.read_text(encoding="utf-8")
    assert source.count("function createInsightsState") == 1
    assert "Get Insights" in source
    assert "Summarize Data" in source
    assert "Write Your Own Query" in source
    assert "Which fiscal year and funding level drives" not in source
    assert "ASKSAGE_API_KEY" not in source
    assert "ASKSAGE_ACCESS_TOKEN" not in source
    assert "x-access-tokens" not in source
    assert "api.asksage" not in source
    assert "fetch(INSIGHTS_ENDPOINT" in source


def test_frontend_contract_covers_accessibility_safety_and_failure_states() -> None:
    source = RENDERER.read_text(encoding="utf-8")
    for behavior in (
        "aria-expanded",
        "aria-controls",
        "aria-live",
        "AbortController",
        "MAX_INSIGHT_QUERY_LENGTH = 2000",
        "event.ctrlKey || event.metaKey",
        "textContent",
        "insufficient_evidence",
        "capturing_image",
        "building_request",
        "cancelled",
        "static_unavailable",
    ):
        if behavior == "static_unavailable":
            assert "Live insights are unavailable" in source
        else:
            assert behavior in source
    assert ".innerHTML" not in source


def test_capture_target_excludes_insights_and_evidence_table() -> None:
    source = RENDERER.read_text(encoding="utf-8")
    capture_append = source.index("chartContainer.appendChild(captureTarget)")
    insights_append = source.index("ensureInsightsControl", capture_append)
    table_append = source.index("makeDataTable", insights_append)
    assert capture_append < insights_append < table_append
