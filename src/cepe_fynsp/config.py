"""Configuration helpers for the CEPE FYNSP dashboard project."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class ProjectSettings(BaseModel):
    """Typed subset of project settings."""

    name: str
    default_integration_area: str
    default_scenario: str


class Settings(BaseModel):
    """Top-level settings object."""

    project: ProjectSettings
    paths: dict[str, str]
    formex: dict[str, Any]
    asksage: dict[str, Any]


def load_settings(path: str | Path = "config/settings.yaml") -> Settings:
    """Load YAML settings from the project config directory."""
    with Path(path).open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f)
    return Settings.model_validate(payload)
