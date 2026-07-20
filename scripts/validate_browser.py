"""Render the generated landing/dashboard pages in a locally installed headless browser."""

from __future__ import annotations

import contextlib
import http.server
import re
import subprocess
import tempfile
import threading
from pathlib import Path


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    """Serve the repository without writing request paths to validation logs."""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


def _browser_path() -> Path:
    candidates = (
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path("/usr/bin/google-chrome"),
        Path("/usr/bin/chromium"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("No supported local Chrome/Edge executable was found.")


def validate_browser(project_root: Path) -> list[str]:
    """Execute local JavaScript and verify all six pages reach rendered states."""
    root = project_root.resolve()
    browser = _browser_path()
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(root), **kwargs)  # noqa: E731
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    results: list[str] = []
    pages = (
        "web/",
        "web/dashboards/01_overview/",
        "web/dashboards/02_acquisition/",
        "web/dashboards/03_site_capacity/",
        "web/dashboards/04_priority_challenge/",
        "web/dashboards/05_findings_report_generator/",
    )
    try:
        with tempfile.TemporaryDirectory(prefix="cepe_browser_profile_") as profile:
            for page in pages:
                completed = subprocess.run(
                    [
                        str(browser),
                        "--headless=new",
                        "--disable-gpu",
                        "--no-sandbox",
                        "--virtual-time-budget=8000",
                        f"--user-data-dir={profile}",
                        "--dump-dom",
                        f"http://127.0.0.1:{server.server_port}/{page}",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                dom = completed.stdout
                errors = len(re.findall(r"panel-error", dom))
                metrics = len(re.findall(r'class="metric-card', dom))
                if page == "web/":
                    if errors or metrics < 6:
                        raise ValueError(
                            f"Landing render failed: errors={errors}, generated metrics={metrics}."
                        )
                    results.append(f"{page}: generated_metrics={metrics}, errors={errors}")
                    continue
                ready = len(re.findall(r'data-render-state="ready"', dom))
                tables = len(re.findall(r'class="data-table', dom))
                filters = len(re.findall(r'class="filter-control', dom))
                visuals = len(
                    re.findall(
                        r'class="(?:ranked-chart|stacked-chart|heatmap-wrap|variance-chart|timeline-chart|bubble-chart|finding-grid)',
                        dom,
                    )
                )
                insights = len(re.findall(r'class="insights-toggle', dom))
                if errors or ready != 6 or tables != 6 or visuals != 6 or insights != 6:
                    raise ValueError(
                        f"{page} render failed: ready={ready}, visuals={visuals}, "
                        f"tables={tables}, insights={insights}, errors={errors}."
                    )
                results.append(
                    f"{page}: ready_panels={ready}, visuals={visuals}, tables={tables}, "
                    f"insights={insights}, filters={filters}, errors={errors}"
                )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    return results


if __name__ == "__main__":
    with contextlib.suppress(BrokenPipeError):
        for result in validate_browser(Path(__file__).resolve().parents[1]):
            print(result)
