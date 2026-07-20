"""Windows PowerShell launcher regressions for the secure insights server."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = PROJECT_ROOT / "scripts" / "start_insights.ps1"
POWERSHELL = shutil.which("powershell.exe") or shutil.which("pwsh.exe")

DASHBOARDS = (
    ("dashboard_01_pit_production", "01_overview"),
    ("dashboard_02_acquisition_schedule", "02_acquisition"),
    ("dashboard_03_site_capacity", "03_site_capacity"),
    ("dashboard_04_priority_challenge", "04_priority_challenge"),
    ("dashboard_05_findings_report_generator", "05_findings_report_generator"),
)

pytestmark = pytest.mark.skipif(
    os.name != "nt" or POWERSHELL is None,
    reason="The launcher targets Windows PowerShell.",
)


def _prepare_synthetic_project(root: Path, env_text: str) -> None:
    """Create only the harmless file structure required for validation-only startup."""
    (root / ".env").write_text(env_text, encoding="utf-8")
    (root / ".venv" / "Scripts").mkdir(parents=True)
    (root / ".venv" / "Scripts" / "python.exe").touch()
    (root / "scripts").mkdir()
    (root / "scripts" / "run_insights_server.py").write_text("", encoding="utf-8")
    (root / "web").mkdir()
    (root / "web" / "index.html").write_text("<!doctype html>", encoding="utf-8")

    for payload_directory, page_directory in DASHBOARDS:
        (root / "data" / "curated" / "dashboard_payloads" / payload_directory).mkdir(parents=True)
        page_root = root / "web" / "dashboards" / page_directory
        page_root.mkdir(parents=True)
        (page_root / "index.html").write_text("<!doctype html>", encoding="utf-8")


def _run_validation(
    root: Path, *, environment_overrides: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the launcher without inheriting any real AskSage or CA configuration."""
    environment = os.environ.copy()
    for name in tuple(environment):
        if name.startswith("ASKSAGE_") or name in {"REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"}:
            environment.pop(name)
    environment.update(environment_overrides or {})

    return subprocess.run(
        [
            str(POWERSHELL),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(LAUNCHER),
            "-ProjectRoot",
            str(root),
            "-ValidateOnly",
        ],
        capture_output=True,
        check=False,
        env=environment,
        text=True,
        timeout=30,
    )


def test_launcher_loads_approved_values_without_printing_secrets(tmp_path: Path) -> None:
    """A ready project reports booleans and overrides the local false image flag."""
    secret_email = "sensitive-user@example.test"
    secret_key = "$(throw 'dotenv-content-must-not-run')"
    ignored_value = "unapproved-value-must-not-appear"
    _prepare_synthetic_project(
        tmp_path,
        "\n".join(
            (
                'export ASKSAGE_INSTANCE="asksage.ai"',
                f"ASKSAGE_EMAIL='{secret_email}'",
                f"ASKSAGE_API_KEY={secret_key}",
                "ASKSAGE_MODEL=approved-model",
                "ASKSAGE_IMAGE_INPUT_SUPPORTED=false",
                f"UNAPPROVED_SETTING={ignored_value}",
            )
        ),
    )

    result = _run_validation(tmp_path)
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "AskSage authentication configured=True" in output
    assert "Image input enabled=True" in output
    assert "Dashboard suite available=True" in output
    assert "Startup validation completed; the server was not started." in output
    assert secret_email not in output
    assert secret_key not in output
    assert ignored_value not in output


def test_launcher_rejects_incomplete_authentication_without_leaking_values(
    tmp_path: Path,
) -> None:
    """An incomplete email/key pair fails with names, never configured values."""
    secret_email = "partial-credential@example.test"
    _prepare_synthetic_project(
        tmp_path,
        "\n".join(
            (
                "ASKSAGE_INSTANCE=asksage.ai",
                f"ASKSAGE_EMAIL={secret_email}",
                "ASKSAGE_MODEL=approved-model",
            )
        ),
    )

    result = _run_validation(tmp_path)
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert "AskSage authentication configured=False" in output
    assert "ASKSAGE_ACCESS_TOKEN" in output
    assert "ASKSAGE_API_KEY" in output
    assert secret_email not in output


def test_blank_dotenv_value_clears_stale_access_token(tmp_path: Path) -> None:
    """A blank local token cannot silently leave an inherited token in precedence."""
    stale_token = "stale-token-must-not-appear"
    _prepare_synthetic_project(
        tmp_path,
        "\n".join(
            (
                "ASKSAGE_INSTANCE=asksage.ai",
                "ASKSAGE_ACCESS_TOKEN=",
                "ASKSAGE_EMAIL=incomplete-user@example.test",
                "ASKSAGE_MODEL=approved-model",
            )
        ),
    )

    result = _run_validation(
        tmp_path,
        environment_overrides={"ASKSAGE_ACCESS_TOKEN": stale_token},
    )
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert "AskSage authentication configured=False" in output
    assert stale_token not in output
