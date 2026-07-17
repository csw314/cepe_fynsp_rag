"""Build and validate the complete dashboard suite from synthetic FORMEX data."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from zipfile import is_zipfile

import pandas as pd

from cepe_fynsp.dashboards.dashboard_01_pit_production import build_dashboard_01_payloads
from cepe_fynsp.dashboards.dashboard_02_acquisition_schedule import build_dashboard_02_payloads
from cepe_fynsp.dashboards.dashboard_03_site_capacity import build_dashboard_03_payloads
from cepe_fynsp.dashboards.dashboard_04_priority_challenge import build_dashboard_04_payloads
from cepe_fynsp.dashboards.dashboard_05_findings_report_generator import (
    build_dashboard_05_payloads,
)
from cepe_fynsp.dashboards.landing import build_landing_summary
from cepe_fynsp.reporting.generator import generate_management_report
from cepe_fynsp.schemas import DashboardManifest, DashboardQuestionPayload, RagRecord


def synthetic_formex() -> pd.DataFrame:
    """Return synthetic, contract-complete Crosscuts and Site Splits records."""
    rows: list[dict[str, object]] = []
    sites = ("Synthetic Alpha", "Synthetic Beta", "Synthetic Gamma")
    levels = ("BASELINE", "ROT", "UFR")
    for layer in ("Federal Crosscuts", "Federal Site Splits"):
        for index, year in enumerate(range(2028, 2033)):
            for level_index, level in enumerate(levels):
                amount = float((index + 1) * (level_index + 1) * 1_000_000)
                if year == 2032 and level == "UFR":
                    amount = -amount
                site = sites[(index + level_index) % len(sites)]
                rows.append(
                    {
                        "NNSA Appropriation": "Synthetic Appropriation",
                        "STAT L3 (Programming)": "Synthetic L3",
                        "STAT L4 (Programming)": "Synthetic L4",
                        "STAT L5 (Programming)": "Synthetic L5",
                        "Construction or Operating": "Operating",
                        "Sub Office Number": f"SYN-{level_index + 1}",
                        "Site Grouping": "Synthetic Group",
                        "Site - PlanEX": site,
                        "Site Name": site,
                        "BNR Code": f"SYN-BNR-{index + 1}",
                        "Program Value": "Synthetic Program",
                        "Fiscal Year": f"FY{year}",
                        "Scenario": "Synthetic FYNSP Scenario",
                        "Submission Type": layer,
                        "Funding Levels": level,
                        "Scope Description": "Synthetic, unclassified scope used only for CI.",
                        "Program Request": f"Synthetic request {index + 1}",
                        "Program Int. Area": "Pit Production",
                        "Process Imp. Area": "Synthetic Process",
                        "Acquisition Type": "LI TEC" if level_index == 0 else "None",
                        "Acquisition ID": f"SYN-A-{index + 1}" if level_index == 0 else None,
                        "Acquisition Name": f"Synthetic acquisition {index + 1}"
                        if level_index == 0
                        else None,
                        "Acquisition Start Date": "2028-01-01" if level_index == 0 else None,
                        "Acquisition End Date": "2032-09-30" if level_index == 0 else None,
                        "Program Priority": index + 1,
                        "DOE Priority Tier": 0 if level == "BASELINE" else level_index,
                        "Account Integrator Priority": 0,
                        "Account Integrator Decision": None,
                        "WBS": f"1.{index + 1}",
                        "WBS Name": f"Synthetic WBS {index + 1}",
                        "WBS Level": 2,
                        "Formulated Measure": amount,
                    }
                )
    return pd.DataFrame(rows)


def prepare_project(root: Path) -> None:
    """Write only synthetic input and minimal typed settings below a temporary root."""
    raw = root / "data" / "raw" / "formex"
    raw.mkdir(parents=True)
    synthetic_formex().to_csv(
        raw / "synthetic_formex.csv", sep="\t", encoding="utf-16", index=False
    )
    config = root / "config"
    config.mkdir()
    (config / "settings.yaml").write_text(
        """project:
  name: synthetic-ci
  default_integration_area: Pit Production
  default_scenario: Synthetic FYNSP Scenario
paths: {}
formex: {}
dashboards: {}
asksage: {}
report: {}
quality: {}
""",
        encoding="utf-8",
    )


def validate_synthetic_outputs(root: Path) -> dict[str, int]:
    """Validate every dashboard, RAG packet, graph reference, and report container."""
    counts = {"dashboards": 0, "payloads": 0, "rag_records": 0, "graph_nodes": 0}
    payload_root = root / "data" / "curated" / "dashboard_payloads"
    for manifest_path in sorted(payload_root.glob("dashboard_*/manifest.json")):
        manifest = DashboardManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
        if len(manifest.payloads) != 6:
            raise ValueError(f"{manifest.dashboard_id} does not contain exactly six questions.")
        counts["dashboards"] += 1
        for entry in manifest.payloads:
            DashboardQuestionPayload.model_validate_json(
                (manifest_path.parent / entry.file).read_text(encoding="utf-8")
            )
            counts["payloads"] += 1
        rag_path = root / manifest.rag_context_file
        for line in rag_path.read_text(encoding="utf-8").splitlines():
            RagRecord.model_validate_json(line)
            counts["rag_records"] += 1
        graph = json.loads((root / manifest.ontology_graph_file).read_text(encoding="utf-8"))
        node_ids = {node["id"] for node in graph["nodes"]}
        if any(
            edge["source"] not in node_ids or edge["target"] not in node_ids
            for edge in graph["edges"]
        ):
            raise ValueError(f"{manifest.dashboard_id} graph has dangling references.")
        counts["graph_nodes"] += len(node_ids)
    if counts["dashboards"] != 5 or counts["payloads"] != 30:
        raise ValueError(f"Incomplete synthetic build: {counts}")
    landing = json.loads((payload_root / "landing_summary.json").read_text(encoding="utf-8"))
    if landing.get("schema_version") != "2.0" or not landing.get("metrics"):
        raise ValueError("Landing summary is missing or invalid.")
    report_manifest = json.loads(
        (root / "data" / "reports" / "html" / "dashboard_05_report_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    docx = root / report_manifest["docx_file"]
    if not docx.is_file() or not is_zipfile(docx):
        raise ValueError("Generated DOCX is not a valid Open XML container.")
    return counts


def run_synthetic_build(root: Path) -> dict[str, int]:
    """Run all build stages beneath an explicit temporary project root."""
    prepare_project(root)
    for builder in (
        build_dashboard_01_payloads,
        build_dashboard_02_payloads,
        build_dashboard_03_payloads,
        build_dashboard_04_payloads,
        build_dashboard_05_payloads,
    ):
        builder(root)
    build_landing_summary(root)
    generate_management_report(root)
    return validate_synthetic_outputs(root)


def main() -> None:
    """Execute an isolated CI build without requiring repository raw data."""
    with tempfile.TemporaryDirectory(prefix="cepe_fynsp_synthetic_") as directory:
        counts = run_synthetic_build(Path(directory))
    print(
        "Synthetic build passed: "
        f"{counts['dashboards']} dashboards, {counts['payloads']} payloads, "
        f"{counts['rag_records']} RAG records, {counts['graph_nodes']} graph nodes."
    )


if __name__ == "__main__":
    main()
