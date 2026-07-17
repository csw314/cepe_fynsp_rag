"""Central monetary parsing and completeness-preserving aggregation."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import pandas as pd

AmountParseStatus = Literal["valid", "blank", "invalid", "excluded"]
AggregateStatus = Literal["complete", "partial", "unavailable", "invalid", "not_evaluated"]

BLANK_LIKE_VALUES = {"", "<na>", "n/a", "na", "nan", "none", "null"}


def parse_amount_series(
    series: pd.Series,
    *,
    excluded_mask: pd.Series | None = None,
) -> pd.DataFrame:
    """Parse monetary text while preserving blank, invalid, and excluded states."""
    raw = series.copy()
    text = raw.astype("string").str.strip()
    blank = text.isna() | text.str.casefold().isin(BLANK_LIKE_VALUES)
    cleaned = text.str.replace(",", "", regex=False).str.replace("$", "", regex=False)
    cleaned = cleaned.str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    normalized = pd.to_numeric(cleaned, errors="coerce")
    invalid = ~blank & normalized.isna()
    excluded = (
        excluded_mask.reindex(series.index, fill_value=False).astype(bool)
        if excluded_mask is not None
        else pd.Series(False, index=series.index)
    )
    status = pd.Series("valid", index=series.index, dtype="string")
    status.loc[blank] = "blank"
    status.loc[invalid] = "invalid"
    status.loc[excluded] = "excluded"
    normalized.loc[blank | invalid | excluded] = pd.NA
    error = pd.Series(pd.NA, index=series.index, dtype="string")
    error.loc[invalid] = "unparseable_amount"
    error.loc[excluded] = "excluded_by_rule"
    return pd.DataFrame(
        {
            "amount_raw": raw,
            "amount_normalized": normalized.astype("Float64"),
            "amount_parse_status": status,
            "amount_parse_error": error,
        },
        index=series.index,
    )


def add_amount_metadata(
    df: pd.DataFrame,
    source_column: str,
    *,
    prefix: str = "amount",
    excluded_mask: pd.Series | None = None,
) -> pd.DataFrame:
    """Return a copy with raw/normalized/status/error fields for one amount column."""
    if source_column not in df.columns:
        raise ValueError(f"Amount source column '{source_column}' is unavailable.")
    out = df.copy()
    parsed = parse_amount_series(out[source_column], excluded_mask=excluded_mask)
    for suffix in ("raw", "normalized", "parse_status", "parse_error"):
        out[f"{prefix}_{suffix}"] = parsed[f"amount_{suffix}"]
    return out


def _aggregate_status(row: pd.Series) -> AggregateStatus:
    """Return deterministic aggregate status from parse counts."""
    total = int(row["total_source_row_count"])
    valid = int(row["valid_amount_row_count"])
    blank = int(row["blank_amount_row_count"])
    invalid = int(row["invalid_amount_row_count"])
    excluded = int(row["excluded_amount_row_count"])
    if total == 0:
        return "not_evaluated"
    if valid == total:
        return "complete"
    if valid > 0:
        return "partial"
    if invalid > 0:
        return "invalid"
    if blank + excluded == total:
        return "unavailable"
    return "not_evaluated"


def aggregate_financial(
    df: pd.DataFrame,
    group_by: Sequence[str] = (),
    *,
    amount_column: str = "amount_normalized",
    status_column: str = "amount_parse_status",
) -> pd.DataFrame:
    """Aggregate amounts with ``min_count=1`` and full parse-completeness counts."""
    if amount_column not in df.columns or status_column not in df.columns:
        source_column = next(
            (
                candidate
                for candidate in (amount_column, "formulated_measure", "amount")
                if candidate in df.columns
            ),
            None,
        )
        if source_column is not None:
            parsed = parse_amount_series(df[source_column])
            df = df.copy()
            df[amount_column] = parsed["amount_normalized"]
            df[status_column] = parsed["amount_parse_status"]
    missing = [name for name in [*group_by, amount_column, status_column] if name not in df.columns]
    if missing:
        raise ValueError(f"Cannot aggregate financial values; missing columns: {missing}")
    working = df.loc[:, [*group_by, amount_column, status_column]].copy()
    working[amount_column] = pd.to_numeric(working[amount_column], errors="coerce")
    for status in ("valid", "blank", "invalid", "excluded"):
        working[f"_{status}"] = (working[status_column] == status).astype("int64")
    if group_by:
        grouped = working.groupby(list(group_by), dropna=False, sort=False)
        result = grouped.agg(
            amount=(amount_column, lambda values: values.sum(min_count=1)),
            valid_amount_row_count=("_valid", "sum"),
            blank_amount_row_count=("_blank", "sum"),
            invalid_amount_row_count=("_invalid", "sum"),
            excluded_amount_row_count=("_excluded", "sum"),
            total_source_row_count=(status_column, "size"),
        ).reset_index()
    else:
        result = pd.DataFrame(
            [
                {
                    "amount": working[amount_column].sum(min_count=1),
                    "valid_amount_row_count": int(working["_valid"].sum()),
                    "blank_amount_row_count": int(working["_blank"].sum()),
                    "invalid_amount_row_count": int(working["_invalid"].sum()),
                    "excluded_amount_row_count": int(working["_excluded"].sum()),
                    "total_source_row_count": len(working),
                }
            ]
        )
    denominator = result["total_source_row_count"].replace(0, pd.NA)
    result["completeness_percentage"] = (
        result["valid_amount_row_count"] / denominator * 100
    ).round(2)
    result["aggregate_status"] = result.apply(_aggregate_status, axis=1)
    return result


def financial_completeness(df: pd.DataFrame) -> dict[str, object]:
    """Return one JSON-safe completeness summary for a prepared dataframe."""
    row = aggregate_financial(df).iloc[0]
    amount = row["amount"]
    return {
        "amount": None if pd.isna(amount) else float(amount),
        "valid_amount_row_count": int(row["valid_amount_row_count"]),
        "blank_amount_row_count": int(row["blank_amount_row_count"]),
        "invalid_amount_row_count": int(row["invalid_amount_row_count"]),
        "excluded_amount_row_count": int(row["excluded_amount_row_count"]),
        "total_source_row_count": int(row["total_source_row_count"]),
        "completeness_percentage": (
            None
            if pd.isna(row["completeness_percentage"])
            else float(row["completeness_percentage"])
        ),
        "aggregate_status": str(row["aggregate_status"]),
    }
