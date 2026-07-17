"""Normalization and stable source-lineage helpers for raw FYNSP datasets."""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from numbers import Integral, Real

import pandas as pd


def snake_case(value: str) -> str:
    """Convert a source column name to deterministic snake_case."""
    text = value.replace("\u2013", "-").replace("\u2014", "-").replace("\ufffd", "-")
    text = re.sub(r"[^0-9A-Za-z]+", "_", text).strip("_").lower()
    return re.sub(r"_+", "_", text)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize columns and fail explicitly when names collide."""
    out = df.copy()
    normalized = [snake_case(str(column)) for column in out.columns]
    duplicates = sorted({name for name in normalized if name and normalized.count(name) > 1})
    if duplicates:
        raise ValueError(f"Duplicate normalized column names: {duplicates}")
    out.columns = normalized
    return out


def parse_dollar_amounts(series: pd.Series | list[str]) -> pd.Series:
    """Parse dollar strings while preserving blanks and invalid values as null."""
    from cepe_fynsp.etl.financial import parse_amount_series

    return parse_amount_series(pd.Series(series))["amount_normalized"]


def _canonical_value(value: object) -> str:
    """Canonicalize one source value for stable content hashing."""
    if value is None or value is pd.NA:
        return "<NULL>"
    try:
        if bool(pd.isna(value)):
            return "<NULL>"
    except (TypeError, ValueError):
        pass
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Integral):
        return str(int(value))
    if isinstance(value, Real):
        number = float(value)
        if math.isnan(number):
            return "<NULL>"
        return format(number, ".15g")
    text = unicodedata.normalize("NFKC", str(value)).strip()
    if not text:
        return "<NULL>"
    try:
        decimal_number = Decimal(text.replace(",", ""))
    except InvalidOperation:
        return re.sub(r"\s+", " ", text)
    return format(decimal_number.normalize(), "f")


def canonical_row_content(row: pd.Series, columns: Sequence[str]) -> str:
    """Serialize selected source fields consistently for hashing."""
    return json.dumps(
        [[column, _canonical_value(row[column])] for column in columns],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def add_source_lineage(
    df: pd.DataFrame,
    dataset_name: str,
    *,
    source_file_identity: str | None = None,
    business_key_columns: Sequence[str] = (),
) -> pd.DataFrame:
    """Add location, content, and deterministic record identifiers.

    Content hashes exclude all generated lineage fields and row position. Exact duplicate rows
    receive occurrence suffixes whose resulting identifier set is stable under reordering.
    """
    out = df.copy()
    generated = {
        "source_dataset",
        "source_original_row_number",
        "source_row_number",
        "source_location_id",
        "source_content_hash",
        "source_record_id",
        "source_duplicate_count",
        "source_duplicate_occurrence",
        "source_row_id",
        "source_row_hash",
    }
    content_columns = sorted(column for column in out.columns if column not in generated)
    file_identity = source_file_identity or dataset_name
    file_token = hashlib.sha256(file_identity.encode("utf-8")).hexdigest()[:12]
    content_hashes = [
        hashlib.sha256(canonical_row_content(row, content_columns).encode("utf-8")).hexdigest()
        for _, row in out.iterrows()
    ]
    duplicate_counts = Counter(content_hashes)
    seen: Counter[str] = Counter()
    occurrences: list[int] = []
    for content_hash in content_hashes:
        seen[content_hash] += 1
        occurrences.append(seen[content_hash])

    use_business_key = bool(business_key_columns) and all(
        column in out.columns for column in business_key_columns
    )
    business_ids: list[str] = []
    if use_business_key:
        business_ids = [
            "|".join(_canonical_value(row[column]) for column in business_key_columns)
            for _, row in out.iterrows()
        ]
        use_business_key = all("<NULL>" not in key for key in business_ids) and len(
            set(business_ids)
        ) == len(business_ids)

    record_ids: list[str] = []
    for index, (content_hash, occurrence) in enumerate(
        zip(content_hashes, occurrences, strict=True)
    ):
        if use_business_key:
            key_hash = hashlib.sha256(business_ids[index].encode("utf-8")).hexdigest()[:20]
            record_ids.append(f"{dataset_name}:key:{key_hash}")
        else:
            record_ids.append(f"{dataset_name}:{file_token}:{content_hash[:20]}:{occurrence:04d}")
    row_numbers = list(range(1, len(out) + 1))
    locations = [f"{dataset_name}:{file_token}:row:{number}" for number in row_numbers]
    lineage_columns: list[tuple[str, object]] = [
        ("source_dataset", dataset_name),
        ("source_original_row_number", row_numbers),
        ("source_row_number", row_numbers),
        ("source_location_id", locations),
        ("source_content_hash", content_hashes),
        ("source_record_id", record_ids),
        ("source_duplicate_count", [duplicate_counts[value] for value in content_hashes]),
        ("source_duplicate_occurrence", occurrences),
        ("source_row_id", record_ids),
        ("source_row_hash", content_hashes),
    ]
    for position, (column, values) in enumerate(lineage_columns):
        out.insert(position, column, values)
    return out


def add_source_row_id(df: pd.DataFrame, dataset_name: str) -> pd.DataFrame:
    """Backward-compatible alias for :func:`add_source_lineage`."""
    return add_source_lineage(df, dataset_name)


def require_columns(df: pd.DataFrame, required: Iterable[str]) -> None:
    """Raise a ValueError if required columns are missing."""
    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
