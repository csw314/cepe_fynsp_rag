"""Executable source contracts for FORMEX, PLANEX, and COSTEX."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict, Field

from cepe_fynsp.etl.normalize import snake_case


class ContractError(ValueError):
    """Raised when a source violates its executable contract."""


class SourceFormat(BaseModel):
    """Delimited-source format metadata."""

    model_config = ConfigDict(extra="forbid")
    encoding: str
    separator: Literal["tab", "comma"]

    @property
    def delimiter(self) -> str:
        """Return the actual delimiter character."""
        return "\t" if self.separator == "tab" else ","


class DataContract(BaseModel):
    """Versioned contract loaded from ``config/data_contracts``."""

    model_config = ConfigDict(extra="forbid")
    dataset: Literal["formex", "planex", "costex"]
    contract_version: str = "1.0"
    raw_file: Path
    format: SourceFormat
    required_columns_raw: tuple[str, ...]
    canonical_amount_column: str
    amount_parse_rule: str | None = None
    additional_numeric_columns: tuple[str, ...] = ()
    allowed_fiscal_years: tuple[str | int, ...] = ()
    allowed_submission_types: tuple[str, ...] = ()
    allowed_funding_levels: tuple[str, ...] = ()
    analytic_layers: dict[str, str] = Field(default_factory=dict)
    use_case: str | None = None

    @property
    def required_columns(self) -> tuple[str, ...]:
        """Return normalized required column names."""
        return tuple(snake_case(value) for value in self.required_columns_raw)


class ContractValidationResult(BaseModel):
    """Serializable outcome included in build/profile manifests."""

    model_config = ConfigDict(extra="forbid")
    dataset: str
    contract_version: str
    status: Literal["passed", "failed"]
    row_count: int | None = None
    column_count: int
    warnings: tuple[str, ...] = ()


def load_contract(dataset: str, project_root: Path) -> DataContract:
    """Load one versioned YAML source contract."""
    path = project_root / "config" / "data_contracts" / f"{dataset}.yaml"
    if not path.is_file():
        # Tests and embedded consumers may supply a temporary project root that
        # contains data and settings but not a duplicate of the package contract.
        package_root = Path(__file__).resolve().parents[3]
        path = package_root / "config" / "data_contracts" / f"{dataset}.yaml"
    with path.open("r", encoding="utf-8") as handle:
        payload: dict[str, Any] = yaml.safe_load(handle) or {}
    return DataContract.model_validate(payload)


def normalized_headers(raw_headers: Sequence[object]) -> list[str]:
    """Normalize headers and reject collisions before dataframe construction."""
    normalized = [snake_case(str(value)) for value in raw_headers]
    duplicates = sorted({name for name in normalized if name and normalized.count(name) > 1})
    if duplicates:
        raise ContractError(f"Duplicate normalized column names: {duplicates}")
    return normalized


def validate_headers(raw_headers: Sequence[object], contract: DataContract) -> list[str]:
    """Validate normalized uniqueness and required source fields."""
    headers = normalized_headers(raw_headers)
    available = {name for name in headers if name}
    missing = sorted(set(contract.required_columns) - available)
    if missing:
        raise ContractError(
            f"{contract.dataset} contract {contract.contract_version} missing required columns: {missing}"
        )
    return headers


def _normalized_domain(series: pd.Series) -> set[str]:
    """Return nonblank, stripped domain values."""
    return set(series.astype("string").dropna().str.strip().loc[lambda value: value != ""])


def validate_dataframe(df: pd.DataFrame, contract: DataContract) -> ContractValidationResult:
    """Validate required columns and dataset-specific controlled domains."""
    validate_headers(list(df.columns), contract)
    warnings: list[str] = []
    if contract.dataset == "formex":
        checks = [
            ("fiscal_year", {str(value) for value in contract.allowed_fiscal_years}),
            ("submission_type", set(contract.allowed_submission_types)),
            ("funding_levels", set(contract.allowed_funding_levels)),
        ]
        for column, allowed in checks:
            if allowed and column in df.columns:
                observed = {value.casefold() for value in _normalized_domain(df[column])}
                normalized_allowed = {value.casefold() for value in allowed}
                unknown = sorted(observed - normalized_allowed)
                if unknown:
                    raise ContractError(f"Invalid {column} values: {unknown}")
        if "scenario" in df.columns and not _normalized_domain(df["scenario"]):
            raise ContractError("FORMEX scenario is blank for every row.")
    elif contract.allowed_fiscal_years and "gl_period_year" in df.columns:
        years = set(pd.to_numeric(df["gl_period_year"], errors="coerce").dropna().astype(int))
        allowed_years = {int(value) for value in contract.allowed_fiscal_years}
        unknown_years = sorted(years - allowed_years)
        if unknown_years:
            raise ContractError(f"Invalid gl_period_year values: {unknown_years}")
    return ContractValidationResult(
        dataset=contract.dataset,
        contract_version=contract.contract_version,
        status="passed",
        row_count=len(df),
        column_count=len(df.columns),
        warnings=tuple(warnings),
    )
