"""Run source ingestion, dashboards, executive summary, and management report builds."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from cepe_fynsp.config import load_settings
from cepe_fynsp.dashboards.dashboard_01_pit_production import build_dashboard_01_payloads
from cepe_fynsp.dashboards.dashboard_02_acquisition_schedule import build_dashboard_02_payloads
from cepe_fynsp.dashboards.dashboard_03_site_capacity import build_dashboard_03_payloads
from cepe_fynsp.dashboards.dashboard_04_priority_challenge import build_dashboard_04_payloads
from cepe_fynsp.dashboards.dashboard_05_findings_report_generator import build_dashboard_05_payloads
from cepe_fynsp.dashboards.landing import build_landing_summary
from cepe_fynsp.etl.pipeline import ingest_all_sources
from cepe_fynsp.reporting.generator import generate_management_report


def main() -> None:
    """Parse CLI arguments and run deterministic local builds."""
    parser = argparse.ArgumentParser(description="Run CEPE FYNSP local ETL/dashboard builds.")
    parser.add_argument(
        "--dashboard",
        choices=["01", "02", "03", "04", "05", "all"],
        help="Build generated artifacts for a supported dashboard.",
    )
    parser.add_argument(
        "--ingest-sources",
        action="store_true",
        help="Validate and convert FORMEX, PLANEX, and COSTEX to normalized Parquet first.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Explicit repository root (defaults to this script's checkout).",
    )
    parser.add_argument(
        "--settings",
        type=Path,
        help="Explicit settings YAML path, absolute or relative to the project root.",
    )
    args = parser.parse_args()
    root = args.project_root.resolve()
    if args.settings:
        settings_path = args.settings if args.settings.is_absolute() else root / args.settings
        os.environ["CEPE_SETTINGS_PATH"] = str(settings_path.resolve())
    settings = load_settings(args.settings, project_root=root)
    print(f"Loaded settings for {settings.project.name} from project root {root}.")
    if args.ingest_sources:
        source_manifest = ingest_all_sources(root, args.settings)
        print(
            "Validated and normalized FORMEX, PLANEX, and COSTEX; "
            f"source health is {source_manifest['overall_status']}."
        )
    builders = {
        "01": build_dashboard_01_payloads,
        "02": build_dashboard_02_payloads,
        "03": build_dashboard_03_payloads,
        "04": build_dashboard_04_payloads,
        "05": build_dashboard_05_payloads,
    }
    selected = ["01", "02", "03", "04", "05"] if args.dashboard == "all" else [args.dashboard]
    for dashboard_id in (item for item in selected if item is not None):
        manifest = builders[dashboard_id](root)
        print(f"Built Dashboard {dashboard_id} payloads at {manifest['generated_at']}.")
    if args.dashboard in {"05", "all"}:
        build_landing_summary(root)
        report = generate_management_report(root)
        print(f"Generated landing summary and report {report['report_id']}.")
    if args.dashboard is None and not args.ingest_sources:
        print(
            "No action selected. Use --ingest-sources and/or --dashboard 01, 02, 03, 04, 05, or all."
        )


if __name__ == "__main__":
    main()
