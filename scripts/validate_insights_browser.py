"""Execute the dependency-free insights interaction harness in headless Chrome or Edge."""

from __future__ import annotations

import contextlib
import http.server
import json
import re
import subprocess
import tempfile
import threading
from pathlib import Path

from validate_browser import QuietHandler, _browser_path


def validate_insights_browser(project_root: Path) -> dict[str, bool]:
    """Run keyboard, state, safe-rendering, fallback, capture, and responsive checks."""
    root = project_root.resolve()
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(root), **kwargs)  # noqa: E731
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="cepe_insights_browser_") as profile:
            completed = subprocess.run(
                [
                    str(_browser_path()),
                    "--headless=new",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--window-size=390,900",
                    "--virtual-time-budget=12000",
                    f"--user-data-dir={profile}",
                    "--dump-dom",
                    f"http://127.0.0.1:{server.server_port}/tests/frontend/insights_harness.html",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=40,
            )
        match = re.search(r'<pre id="results" data-complete="true">([^<]+)</pre>', completed.stdout)
        if not match:
            raise ValueError("Insights browser harness did not complete.")
        result = json.loads(match.group(1).replace("&quot;", '"').replace("&amp;", "&"))
        failures = sorted(name for name, passed in result.items() if passed is False)
        if failures:
            raise ValueError(f"Insights browser checks failed: {failures}; details={result}")
        return result
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    with contextlib.suppress(BrokenPipeError):
        result = validate_insights_browser(Path(__file__).resolve().parents[1])
        print(f"Insights browser validation passed: {len(result)} interaction checks.")
