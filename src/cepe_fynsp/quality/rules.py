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
    source_submission_type: str | None = None
    source_row_ids: tuple[str, ...] = ()
    status: str = "evaluated"


_BLANK_LIKE_VALUES = {"", "<na>", "n/a", "na", "nan", "none", "null"}


def _blank_mask(series: pd.Series) -> pd.Series:
    """Return a mask for null, blank, and common blank-like values."""
    normalized = series.astype("string").str.strip().str.casefold()
    return normalized.isna() | normalized.isin(_BLANK_LIKE_VALUES)


def _finding_from_mask(
    df: pd.DataFrame,
    mask: pd.Series,
    *,
    rule_id: str,
    severity: str,
    title: str,
    details: str,
    amount_col: str,
    source_submission_type: str,
    lineage_limit: int,
) -> QualityFinding:
    """Create a reproducible quality finding from a Boolean row mask."""
    affected_dollars: float | None = None
    if amount_col in df.columns:
        amounts = pd.to_numeric(df.loc[mask, amount_col], errors="coerce")
        total = amounts.sum(min_count=1)
        affected_dollars = None if pd.isna(total) else float(total)

    source_row_ids: tuple[str, ...] = ()
    if "source_row_id" in df.columns:
        source_row_ids = tuple(
            str(value)
            for value in df.loc[mask, "source_row_id"].dropna().head(lineage_limit).tolist()
        )

    return QualityFinding(
        rule_id=rule_id,
        severity=severity,
        title=title,
        row_count=int(mask.sum()),
        affected_dollars=affected_dollars,
        details=details,
        source_submission_type=source_submission_type,
        source_row_ids=source_row_ids,
    )


def _not_evaluated_finding(
    rule_id: str, title: str, details: str, source_submission_type: str
) -> QualityFinding:
    """Represent an optional rule that cannot run because a column is unavailable."""
    return QualityFinding(
        rule_id=rule_id,
        severity="not_evaluated",
        title=title,
        row_count=0,
        affected_dollars=None,
        details=details,
        source_submission_type=source_submission_type,
        status="not_evaluated",
    )


def missing_field_finding(
    df: pd.DataFrame,
    *,
    column: str,
    rule_id: str,
    severity: str,
    title: str,
    details: str,
    amount_col: str = "formulated_measure",
    source_submission_type: str = "Federal Crosscuts",
    lineage_limit: int = 100,
    eligible_mask: pd.Series | None = None,
) -> QualityFinding:
    """Evaluate a blank-field rule without failing when an optional column is absent."""
    if column not in df.columns:
        return _not_evaluated_finding(
            rule_id,
            title,
            f"Not evaluated because FORMEX column '{column}' is unavailable.",
            source_submission_type,
        )
    mask = _blank_mask(df[column])
    if eligible_mask is not None:
        mask = mask & eligible_mask
    return _finding_from_mask(
        df,
        mask,
        rule_id=rule_id,
        severity=severity,
        title=title,
        details=details,
        amount_col=amount_col,
        source_submission_type=source_submission_type,
        lineage_limit=lineage_limit,
    )


def tier1_above_baseline_finding(
    df: pd.DataFrame,
    *,
    amount_col: str = "formulated_measure",
    source_submission_type: str = "Federal Crosscuts",
    lineage_limit: int = 100,
) -> QualityFinding:
    """Flag Tier 1 rows in ROT or UFR, if the necessary columns are available."""
    required = {"funding_levels", "doe_priority_tier"}
    missing = sorted(required - set(df.columns))
    if missing:
        return _not_evaluated_finding(
            "FQ009",
            "Tier 1 above-baseline rows",
            f"Not evaluated because FORMEX columns are unavailable: {', '.join(missing)}.",
            source_submission_type,
        )
    above_baseline = df["funding_levels"].astype("string").str.upper().isin(["ROT", "UFR"])
    mask = above_baseline & (pd.to_numeric(df["doe_priority_tier"], errors="coerce") == 1)
    return _finding_from_mask(
        df,
        mask,
        rule_id="FQ009",
        severity="high",
        title="Tier 1 above-baseline rows",
        details="Tier 1 rows in ROT or UFR are a CEPE review trigger because mandated work is expected in baseline.",
        amount_col=amount_col,
        source_submission_type=source_submission_type,
        lineage_limit=lineage_limit,
    )


def acquisition_metadata_finding(
    df: pd.DataFrame,
    *,
    amount_col: str = "formulated_measure",
    source_submission_type: str = "Federal Crosscuts",
    lineage_limit: int = 100,
) -> QualityFinding:
    """Flag acquisition-tagged rows that lack required acquisition metadata."""
    required = {
        "acquisition_type",
        "acquisition_id",
        "acquisition_name",
        "acquisition_start_date",
        "acquisition_end_date",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        return _not_evaluated_finding(
            "FQ010",
            "Incomplete acquisition metadata",
            f"Not evaluated because FORMEX columns are unavailable: {', '.join(missing)}.",
            source_submission_type,
        )
    acquisition_related = ~_blank_mask(df["acquisition_type"])
    for non_acquisition_value in {"none", "not applicable", "n/a", "na"}:
        acquisition_related &= (
            df["acquisition_type"].astype("string").str.strip().str.casefold()
            != non_acquisition_value
        )
    missing_metadata = pd.Series(False, index=df.index)
    for column in required - {"acquisition_type"}:
        missing_metadata |= _blank_mask(df[column])
    return _finding_from_mask(
        df,
        acquisition_related & missing_metadata,
        rule_id="FQ010",
        severity="high",
        title="Incomplete acquisition metadata",
        details="Rows with an acquisition type are missing one or more ID, name, start-date, or end-date fields.",
        amount_col=amount_col,
        source_submission_type=source_submission_type,
        lineage_limit=lineage_limit,
    )


def negative_amount_finding(
    df: pd.DataFrame,
    *,
    amount_col: str = "formulated_measure",
    source_submission_type: str = "Federal Crosscuts",
    lineage_limit: int = 100,
) -> QualityFinding:
    """Flag negative dollars as potential offsets, restorations, or corrections."""
    if amount_col not in df.columns:
        return _not_evaluated_finding(
            "FQ012",
            "Negative-dollar review",
            f"Not evaluated because FORMEX column '{amount_col}' is unavailable.",
            source_submission_type,
        )
    mask = pd.to_numeric(df[amount_col], errors="coerce") < 0
    return _finding_from_mask(
        df,
        mask,
        rule_id="FQ012",
        severity="medium",
        title="Negative-dollar review",
        details="Negative dollars are review triggers and may represent offsets, restorations, or corrections; they are not automatically errors.",
        amount_col=amount_col,
        source_submission_type=source_submission_type,
        lineage_limit=lineage_limit,
    )


def reconciliation_finding(
    crosscuts_total: float,
    site_splits_total: float,
    *,
    tolerance_dollars: float = 1.0,
) -> QualityFinding:
    """Represent a Crosscuts-to-Site-Splits reconciliation result as a quality finding."""
    variance = site_splits_total - crosscuts_total
    severity = "high" if abs(variance) > tolerance_dollars else "low"
    return QualityFinding(
        rule_id="FQ004",
        severity=severity,
        title="Federal Crosscuts versus Federal Site Splits reconciliation",
        row_count=1 if abs(variance) > tolerance_dollars else 0,
        affected_dollars=abs(float(variance)),
        details=(
            "Federal Site Splits minus Federal Crosscuts equals "
            f"{variance:,.2f}; tolerance is {tolerance_dollars:,.2f}."
        ),
        source_submission_type="Federal Crosscuts and Federal Site Splits",
    )


def evaluate_dashboard_01_quality_rules(
    crosscuts: pd.DataFrame,
    site_splits: pd.DataFrame,
    *,
    amount_col: str = "formulated_measure",
    lineage_limit: int = 100,
) -> list[QualityFinding]:
    """Run column-tolerant, deterministic Dashboard 1 quality checks.

    This checks only the two submission layers used by Dashboard 1. Missing optional
    FORMEX fields are reported as ``not_evaluated`` rather than causing an error.
    """
    source = "Federal Crosscuts"
    above_baseline = (
        crosscuts["funding_levels"].astype("string").str.upper().isin(["ROT", "UFR"])
        if "funding_levels" in crosscuts.columns
        else None
    )
    findings = [
        missing_field_finding(
            crosscuts,
            column="program_request",
            rule_id="FQ005",
            severity="high",
            title="Missing program request on above-baseline rows",
            details="ROT and UFR rows without a program request are difficult to challenge and trace.",
            amount_col=amount_col,
            source_submission_type=source,
            lineage_limit=lineage_limit,
            eligible_mask=above_baseline,
        )
        if above_baseline is not None
        else _not_evaluated_finding(
            "FQ005",
            "Missing program request on above-baseline rows",
            "Not evaluated because FORMEX column 'funding_levels' is unavailable.",
            source,
        ),
        missing_field_finding(
            crosscuts,
            column="scope_description",
            rule_id="FQ006",
            severity="medium",
            title="Missing scope description",
            details="Rows without a scope description do not provide enough detail for a thorough review.",
            amount_col=amount_col,
            source_submission_type=source,
            lineage_limit=lineage_limit,
        ),
        missing_field_finding(
            crosscuts,
            column="wbs",
            rule_id="FQ015",
            severity="medium",
            title="Missing WBS traceability",
            details="Rows without WBS cannot be readily traced to budget structure.",
            amount_col=amount_col,
            source_submission_type=source,
            lineage_limit=lineage_limit,
        ),
        missing_field_finding(
            crosscuts,
            column="bnr_code",
            rule_id="FQ016",
            severity="medium",
            title="Missing BNR traceability",
            details="Rows without a BNR code have incomplete budget-structure traceability.",
            amount_col=amount_col,
            source_submission_type=source,
            lineage_limit=lineage_limit,
        ),
        missing_field_finding(
            site_splits,
            column="site_planex",
            rule_id="FQ014",
            severity="medium",
            title="Missing site on Federal Site Splits",
            details="Site Split rows without a site cannot support site-level integration review.",
            amount_col=amount_col,
            source_submission_type="Federal Site Splits",
            lineage_limit=lineage_limit,
        ),
        missing_field_finding(
            crosscuts,
            column="doe_priority_tier",
            rule_id="FQ018",
            severity="medium",
            title="Missing DOE Priority Tier on above-baseline rows",
            details="ROT and UFR rows without a DOE Priority Tier cannot be fully prioritized for review.",
            amount_col=amount_col,
            source_submission_type=source,
            lineage_limit=lineage_limit,
            eligible_mask=above_baseline,
        )
        if above_baseline is not None
        else _not_evaluated_finding(
            "FQ018",
            "Missing DOE Priority Tier on above-baseline rows",
            "Not evaluated because FORMEX column 'funding_levels' is unavailable.",
            source,
        ),
        tier1_above_baseline_finding(
            crosscuts,
            amount_col=amount_col,
            source_submission_type=source,
            lineage_limit=lineage_limit,
        ),
        acquisition_metadata_finding(
            crosscuts,
            amount_col=amount_col,
            source_submission_type=source,
            lineage_limit=lineage_limit,
        ),
        negative_amount_finding(
            crosscuts,
            amount_col=amount_col,
            source_submission_type=source,
            lineage_limit=lineage_limit,
        ),
        missing_field_finding(
            crosscuts,
            column="account_integrator_decision",
            rule_id="FQ007",
            severity="limitation",
            title="Missing Account Integrator Decision",
            details="Decision traceability is unavailable for these rows in the provided extract.",
            amount_col=amount_col,
            source_submission_type=source,
            lineage_limit=lineage_limit,
        ),
    ]

    if "account_integrator_priority" not in crosscuts.columns:
        findings.append(
            _not_evaluated_finding(
                "FQ008",
                "Account Integrator Priority usability",
                "Not evaluated because FORMEX column 'account_integrator_priority' is unavailable.",
                source,
            )
        )
    else:
        priority_values = crosscuts["account_integrator_priority"].astype("string").str.strip()
        unusable = priority_values.isna() | priority_values.isin(["", "0", "0.0"])
        findings.append(
            QualityFinding(
                rule_id="FQ008",
                severity="limitation" if bool(unusable.all()) else "low",
                title="Account Integrator Priority usability",
                row_count=int(unusable.sum()),
                affected_dollars=(
                    float(pd.to_numeric(crosscuts.loc[unusable, amount_col], errors="coerce").sum())
                    if amount_col in crosscuts.columns
                    else None
                ),
                details=(
                    "All Account Integrator Priority values are blank or zero; the field is not analytically useful."
                    if bool(unusable.all())
                    else "Some Account Integrator Priority values are blank or zero."
                ),
                source_submission_type=source,
                source_row_ids=tuple(
                    str(value)
                    for value in crosscuts.loc[unusable, "source_row_id"].dropna().head(lineage_limit)
                )
                if "source_row_id" in crosscuts.columns
                else (),
            )
        )
    return findings


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
