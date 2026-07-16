"""Deterministic data-quality rules for CEPE FYNSP review."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class QualityFinding:
    """A deterministic quality finding."""

    rule_id: str
    severity: str
    title: str
    row_count: int
    affected_dollars: float | None
    details: str


def flag_tier1_above_baseline(df: pd.DataFrame, amount_col: str = "formulated_measure") -> QualityFinding:
    """Flag Tier 1 rows that are above baseline."""
    mask = (
        df["funding_levels"].astype("string").str.upper().isin(["ROT", "UFR"])
        & (pd.to_numeric(df["doe_priority_tier"], errors="coerce") == 1)
    )
    affected = df.loc[mask, amount_col].sum() if amount_col in df else None
    return QualityFinding(
        rule_id="FQ009",
        severity="high",
        title="Tier 1 above-baseline rows",
        row_count=int(mask.sum()),
        affected_dollars=float(affected) if affected is not None else None,
        details="Tier 1 rows in ROT or UFR are review triggers.",
    )


def flag_missing_account_integrator_decision(
    df: pd.DataFrame, amount_col: str = "formulated_measure"
) -> QualityFinding:
    """Flag missing Account Integrator Decision values."""
    mask = df["account_integrator_decision"].isna() | (
        df["account_integrator_decision"].astype("string").str.strip() == ""
    )
    affected = df.loc[mask, amount_col].sum() if amount_col in df else None
    return QualityFinding(
        rule_id="FQ007",
        severity="limitation",
        title="Missing Account Integrator Decision",
        row_count=int(mask.sum()),
        affected_dollars=float(affected) if affected is not None else None,
        details="Decision traceability is unavailable for these rows in the provided extract.",
    )
