"""Raw data loaders for FORMEX, PLANEX, and COSTEX."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def _drop_empty_unnamed_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Drop export artifacts such as fully empty trailing unnamed columns."""
    keep_cols = []
    for col in df.columns:
        col_text = str(col).lower()
        if col_text.startswith("unnamed") and df[col].isna().all():
            continue
        keep_cols.append(col)
    return df.loc[:, keep_cols]


def load_formex(path: str | Path) -> pd.DataFrame:
    """Load the uploaded FORMEX export.

    The provided file is UTF-16 and tab-delimited.
    """
    df = pd.read_csv(path, encoding="utf-16", sep="\t")
    return _drop_empty_unnamed_columns(df)


def load_planex(path: str | Path) -> pd.DataFrame:
    """Load PLANEX CSV."""
    return pd.read_csv(path)


def load_costex(path: str | Path) -> pd.DataFrame:
    """Load COSTEX CSV."""
    return pd.read_csv(path)
