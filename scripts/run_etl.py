"""Run supported local ETL and dashboard artifact builds."""

from __future__ import annotations

import argparse

from cepe_fynsp.config import load_settings
from cepe_fynsp.dashboards.dashboard_01_pit_production import build_dashboard_01_payloads
from cepe_fynsp.dashboards.dashboard_02_acquisition_schedule import build_dashboard_02_payloads
from cepe_fynsp.dashboards.dashboard_03_site_capacity import build_dashboard_03_payloads
from cepe_fynsp.dashboards.dashboard_04_priority_challenge import build_dashboard_04_payloads
from cepe_fynsp.dashboards.dashboard_05_findings_report_generator import build_dashboard_05_payloads


def main() -> None:
    """Parse CLI arguments and run the selected local build."""
    parser = argparse.ArgumentParser(description="Run CEPE FYNSP local ETL/dashboard builds.")
    parser.add_argument(
        "--dashboard",
        choices=["01", "02", "03", "04", "05", "all"],
        help="Build generated artifacts for a supported dashboard.",
    )
    args = parser.parse_args()
    settings = load_settings()
    print(f"Loaded settings for {settings.project.name}")
    builders = {
        "01": build_dashboard_01_payloads,
        "02": build_dashboard_02_payloads,
        "03": build_dashboard_03_payloads,
        "04": build_dashboard_04_payloads,
        "05": build_dashboard_05_payloads,
    }
    if args.dashboard in builders:
        manifest = builders[args.dashboard]()
        print(f"Built Dashboard {args.dashboard} payloads at {manifest['generated_at']}.")
        return
    if args.dashboard == "all":
        for dashboard_id in ["01", "02", "03", "04", "05"]:
            manifest = builders[dashboard_id]()
            print(f"Built Dashboard {dashboard_id} payloads at {manifest['generated_at']}.")
        return
    print("No dashboard was selected. Use --dashboard 01, 02, 03, 04, 05, or all.")


if __name__ == "__main__":
    main()
