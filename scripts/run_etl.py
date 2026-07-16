"""Run supported local ETL and dashboard artifact builds."""

from __future__ import annotations

import argparse

from cepe_fynsp.config import load_settings
from cepe_fynsp.dashboards.dashboard_01_pit_production import build_dashboard_01_payloads


def main() -> None:
    """Parse CLI arguments and run the selected local build."""
    parser = argparse.ArgumentParser(description="Run CEPE FYNSP local ETL/dashboard builds.")
    parser.add_argument(
        "--dashboard",
        choices=["01"],
        help="Build generated artifacts for a supported dashboard.",
    )
    args = parser.parse_args()
    settings = load_settings()
    print(f"Loaded settings for {settings.project.name}")
    if args.dashboard == "01":
        manifest = build_dashboard_01_payloads()
        print(
            "Built Dashboard 1 payloads for "
            f"{manifest['filters']['program_int_area']} at {manifest['generated_at']}."
        )
        return
    print("No dashboard was selected. Use --dashboard 01 to build Dashboard 1 artifacts.")


if __name__ == "__main__":
    main()
