"""Normalization helpers for raw FYNSP datasets."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

import pandas as pd


def snake_case(value: str) -> str:
    """Convert a source column name to snake_case."""
    text = value.replace("\u2013", "-").replace("\u2014", "-")
    text = re.sub(r"[^0-9A-Za-z]+", "_", text).strip("_").lower()
    text = re.sub(r"_+", "_", text)
    replacements = {
        "stat_l3_programming": "stat_l3_programming",
        "stat_l4_programming": "stat_l4_programming",
        "stat_l5_programming": "stat_l5_programming",
        "site_planex": "site_planex",
        "program_int_area": "program_int_area",
        "process_imp_area": "process_imp_area",
        "ukr_obbba_tmf_funds": "ukr_obbba_tmf_funds",
    }
    return replacements.get(text, text)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize DataFrame column names."""
    out = df.copy()
    out.columns = [snake_case(str(c)) for c in out.columns]
    return out


def parse_dollar_amounts(series: pd.Series | list[str]) -> pd.Series:
    """Parse dollar strings that may contain commas, blanks, or parentheses."""
    s = pd.Series(series)
    cleaned = (
        s.astype("string")
        .str.strip()
        .str.replace(",", "", regex=False)
        .str.replace("$", "", regex=False)
    )
    cleaned = cleaned.str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    return pd.to_numeric(cleaned, errors="coerce")


def add_source_row_id(df: pd.DataFrame, dataset_name: str) -> pd.DataFrame:
    """Add stable source row IDs and content hashes."""
    out = df.copy()
    out.insert(0, "source_row_number", range(1, len(out) + 1))
    out.insert(0, "source_dataset", dataset_name)
    hashes: list[str] = []
    for _, row in out.astype("string").iterrows():
        joined = "|".join(row.fillna("<NA>").tolist())
        hashes.append(hashlib.sha256(joined.encode("utf-8")).hexdigest()[:24])
    out.insert(0, "source_row_hash", hashes)
    out.insert(0, "source_row_id", [f"{dataset_name}:{i}" for i in range(1, len(out) + 1)])
    return out


def require_columns(df: pd.DataFrame, required: Iterable[str]) -> None:
    """Raise a ValueError if required columns are missing."""
    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
