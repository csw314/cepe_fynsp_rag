"""Run one live insight and print only content-free status/validation metadata."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from cepe_fynsp.insights.schemas import InsightAction, InsightRequest
from cepe_fynsp.insights.service import InsightService


def main() -> None:
    """Execute a bounded diagnostic request without printing model or evidence text."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--dashboard-id", default="dashboard_01_pit_production")
    parser.add_argument(
        "--question-id", choices=[f"q{index}" for index in range(1, 7)], default="q1"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    service = InsightService(args.project_root)
    chart_id = f"{args.dashboard_id}_{args.question_id}"
    request = InsightRequest(
        dashboard_id=args.dashboard_id,
        question_id=args.question_id,
        chart_id=chart_id,
        action=InsightAction.SUMMARIZE,
        active_filter_state={},
    )
    response = service.answer(request)
    print(f"status={response.status.value}")
    print(f"request_id={response.ai_metadata.request_id}")
    print(f"citation_count={len(response.citations)}")
    print(f"limitation_count={len(response.limitations)}")


if __name__ == "__main__":
    main()
