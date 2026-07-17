"""Typed configuration loading rooted explicitly at the project checkout."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Base model that rejects accidental configuration drift."""

    model_config = ConfigDict(extra="forbid")


class ProjectSettings(StrictModel):
    """Project identity and default analytical selection."""

    name: str
    default_integration_area: str
    default_scenario: str


class PathsSettings(StrictModel):
    """Repository-relative input and artifact paths."""

    raw_formex: Path = Path("data/raw/formex/CSV Download.csv")
    raw_planex: Path = Path("data/raw/planex/idw_planex_202607171050.csv")
    raw_costex: Path = Path("data/raw/costex/idw_costex_202607171052.csv")
    interim_dir: Path = Path("data/interim")
    curated_dir: Path = Path("data/curated")
    ontology_dir: Path = Path("data/ontology")
    dashboard_payload_dir: Path = Path("data/curated/dashboard_payloads")
    reports_dir: Path = Path("data/reports")
    finding_dispositions: Path = Path("data/curated/finding_dispositions.json")


class FormexSettings(StrictModel):
    """FORMEX parsing and non-additive submission-layer rules."""

    encoding: str = "utf-16"
    separator: str = "\t"
    amount_column: str = "formulated_measure"
    default_total_submission_type: str = "Federal Crosscuts"
    site_submission_type: str = "Federal Site Splits"
    allowed_submission_types: tuple[str, ...] = (
        "Federal Crosscuts",
        "Federal Site Splits",
        "GPRA Constraints",
        "Federal STAT Table",
    )
    allowed_fiscal_years: tuple[int, ...] = (2028, 2029, 2030, 2031, 2032)


class DashboardSettings(StrictModel):
    """Static dashboard generation and safe-browser limits."""

    schema_version: str = "2.0"
    lineage_sample_limit: int = Field(default=250, ge=0, le=1000)
    table_page_size: int = Field(default=25, ge=5, le=100)
    client_filter_dimensions: tuple[str, ...] = (
        "fiscal_year",
        "funding_level",
        "organization",
        "site",
        "doe_priority_tier",
        "acquisition_type",
        "severity",
    )


class AskSageSettings(StrictModel):
    """Environment-variable bindings and transport safety controls."""

    instance_env: str = "ASKSAGE_INSTANCE"
    email_env: str = "ASKSAGE_EMAIL"
    api_key_env: str = "ASKSAGE_API_KEY"
    access_token_env: str = "ASKSAGE_ACCESS_TOKEN"
    model_env: str = "ASKSAGE_MODEL"
    approved_hosts: tuple[str, ...] = ("api.asksage.ai",)
    connect_timeout_seconds: float = Field(default=10.0, gt=0)
    read_timeout_seconds: float = Field(default=60.0, gt=0)
    max_retries: int = Field(default=3, ge=0, le=8)
    backoff_factor: float = Field(default=0.5, ge=0)


class ReportSettings(StrictModel):
    """Management-report output settings."""

    title: str = "CEPE Pit Production FYNSP Program Review"
    target_pages: str = "5-7"
    docx_subdir: Path = Path("docx")
    html_subdir: Path = Path("html")
    exhibit_subdir: Path = Path("exhibits")


class QualityThresholdSettings(StrictModel):
    """Deterministic materiality and health-status thresholds."""

    materiality_dollars: float = Field(default=100_000_000.0, ge=0)
    site_yoy_change: float = Field(default=0.25, ge=0)
    reconciliation_dollars: float = Field(default=1.0, ge=0)
    amber_completeness_percentage: float = Field(default=99.0, ge=0, le=100)


class Settings(StrictModel):
    """Complete validated application settings."""

    project: ProjectSettings
    paths: PathsSettings = Field(default_factory=PathsSettings)
    formex: FormexSettings = Field(default_factory=FormexSettings)
    dashboards: DashboardSettings = Field(default_factory=DashboardSettings)
    asksage: AskSageSettings = Field(default_factory=AskSageSettings)
    report: ReportSettings = Field(default_factory=ReportSettings)
    quality: QualityThresholdSettings = Field(default_factory=QualityThresholdSettings)
    project_root: Path = Field(default=Path("."), exclude=True)

    def resolve_path(self, value: Path) -> Path:
        """Resolve a configured path against the explicit project root."""
        return value if value.is_absolute() else (self.project_root / value).resolve()


def _default_project_root() -> Path:
    """Return the checkout root from this installed package location."""
    return Path(__file__).resolve().parents[2]


def load_settings(
    path: str | Path | None = None,
    *,
    project_root: str | Path | None = None,
) -> Settings:
    """Load and validate YAML settings from an explicit project root.

    ``path`` may be absolute or relative to ``project_root``. Existing callers that pass the
    settings path positionally remain supported.
    """
    root = Path(project_root).resolve() if project_root is not None else _default_project_root()
    configured_path = path or os.getenv("CEPE_SETTINGS_PATH")
    settings_path = (
        Path(configured_path) if configured_path is not None else Path("config/settings.yaml")
    )
    if not settings_path.is_absolute():
        settings_path = root / settings_path
    settings_path = settings_path.resolve()
    if (
        project_root is None
        and configured_path is not None
        and settings_path.parent.name == "config"
    ):
        root = settings_path.parent.parent
    with settings_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    settings = Settings.model_validate(payload)
    return settings.model_copy(update={"project_root": root.resolve()})
