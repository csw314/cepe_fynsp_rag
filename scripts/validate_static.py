"""Offline/static acceptance checks for the CEPE dashboard web assets."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from cepe_fynsp.dashboards.dashboard_01_pit_production import QUESTION_TEXT as QUESTIONS_1
from cepe_fynsp.dashboards.dashboard_02_acquisition_schedule import QUESTION_TEXT as QUESTIONS_2
from cepe_fynsp.dashboards.dashboard_03_site_capacity import QUESTION_TEXT as QUESTIONS_3
from cepe_fynsp.dashboards.dashboard_04_priority_challenge import QUESTION_TEXT as QUESTIONS_4
from cepe_fynsp.dashboards.dashboard_05_findings_report_generator import (
    QUESTION_TEXT as QUESTIONS_5,
)

EXTERNAL_REFERENCE = re.compile(r"(?:https?:)?//", re.IGNORECASE)


def validate_static(project_root: Path) -> None:
    """Raise for online assets, missing questions, secrets, or committed raw source data."""
    root = project_root.resolve()
    web = root / "web"
    asset_files = sorted(
        path for pattern in ("*.html", "*.css", "*.js") for path in web.rglob(pattern)
    )
    external = [
        path.relative_to(root).as_posix()
        for path in asset_files
        if EXTERNAL_REFERENCE.search(path.read_text(encoding="utf-8"))
    ]
    if external:
        raise ValueError(f"Runtime external references are prohibited: {external}")
    page_questions = [
        (web / "dashboards" / "01_overview" / "index.html", QUESTIONS_1),
        (web / "dashboards" / "02_acquisition" / "index.html", QUESTIONS_2),
        (web / "dashboards" / "03_site_capacity" / "index.html", QUESTIONS_3),
        (web / "dashboards" / "04_priority_challenge" / "index.html", QUESTIONS_4),
        (web / "dashboards" / "05_findings_report_generator" / "index.html", QUESTIONS_5),
    ]
    for page, questions in page_questions:
        content = page.read_text(encoding="utf-8")
        for question in questions.values():
            if content.count(question) != 1:
                raise ValueError(
                    f"Mandatory question must occur exactly once in {page}: {question}"
                )
        for required in ("skip-link", "suite-nav", "data-health", "dashboard-filters"):
            if required not in content:
                raise ValueError(f"{page} is missing required accessible component: {required}")
    renderer = (web / "assets" / "js" / "dashboard_renderer.js").read_text(encoding="utf-8")
    for behavior in (
        "Promise.allSettled",
        "payload.columns",
        "Export filtered aggregate CSV",
        "aria-sort",
    ):
        if behavior not in renderer:
            raise ValueError(f"Shared renderer is missing acceptance behavior: {behavior}")
    secret_markers = ("ASKSAGE_API_KEY", "ASKSAGE_ACCESS_TOKEN", "x-access-tokens")
    for path in asset_files:
        content = path.read_text(encoding="utf-8")
        if any(marker in content for marker in secret_markers):
            raise ValueError(f"Browser asset contains a credential marker: {path}")
    tracked = subprocess.run(
        ["git", "ls-files", "data/raw"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    controlled_extensions = {".csv", ".xlsx", ".xls", ".docx", ".pdf", ".parquet"}
    prohibited = [path for path in tracked if Path(path).suffix.casefold() in controlled_extensions]
    if prohibited:
        raise ValueError(f"Raw source data must not be committed: {prohibited}")


if __name__ == "__main__":
    validate_static(Path(__file__).resolve().parents[1])
    print("Static offline validation passed for the landing page and five dashboards.")
