"""Immutable raw-data loaders with explicit format and chunking controls."""

from __future__ import annotations

import csv
from collections.abc import Iterator, Sequence
from pathlib import Path

import pandas as pd


def _drop_empty_unnamed_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Drop fully empty trailing export artifacts without mutating the input."""
    keep_columns = [
        column
        for column in df.columns
        if not (
            (str(column).lower().startswith("unnamed") or str(column).strip() == "")
            and df[column].isna().all()
        )
    ]
    return df.loc[:, keep_columns].copy()


def detect_delimited_format(path: str | Path) -> tuple[str, str]:
    """Detect the supported source encoding and delimiter from BOM/sample bytes."""
    source = Path(path)
    with source.open("rb") as handle:
        prefix = handle.read(65536)
    encoding = "utf-16" if prefix.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    sample = prefix.decode(encoding, errors="replace")
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters="\t,").delimiter
    except csv.Error:
        delimiter = "\t" if "\t" in sample.splitlines()[0] else ","
    return encoding, delimiter


def read_source_headers(path: str | Path) -> list[str]:
    """Read only a source header for contract checks."""
    encoding, delimiter = detect_delimited_format(path)
    with Path(path).open("r", encoding=encoding, newline="") as handle:
        return next(csv.reader(handle, delimiter=delimiter))


def discover_single_csv(directory: Path, configured_path: Path | None = None) -> Path:
    """Resolve a configured CSV or require an unambiguous directory fallback."""
    if configured_path is not None and configured_path.exists():
        return configured_path.resolve()
    candidates = sorted(path for path in directory.glob("*.csv") if path.is_file())
    if not candidates:
        raise FileNotFoundError(f"No CSV source was found under '{directory}'.")
    if len(candidates) > 1:
        names = ", ".join(path.name for path in candidates)
        raise ValueError(f"Multiple CSV sources were found under '{directory}': {names}")
    return candidates[0].resolve()


def load_formex(path: str | Path) -> pd.DataFrame:
    """Load FORMEX with detected UTF-16/tab support and preserved source strings."""
    encoding, delimiter = detect_delimited_format(path)
    frame = pd.read_csv(path, encoding=encoding, sep=delimiter, low_memory=False)
    return _drop_empty_unnamed_columns(frame)


def iter_csv_chunks(
    path: str | Path,
    *,
    chunksize: int = 100_000,
    usecols: Sequence[str] | None = None,
) -> Iterator[pd.DataFrame]:
    """Yield bounded raw CSV chunks for large PLANEX/COSTEX inputs."""
    encoding, delimiter = detect_delimited_format(path)
    yield from pd.read_csv(
        path,
        encoding=encoding,
        sep=delimiter,
        dtype="string",
        chunksize=chunksize,
        usecols=usecols,
        keep_default_na=False,
        na_values=[],
    )


def load_planex(path: str | Path, *, usecols: Sequence[str] | None = None) -> pd.DataFrame:
    """Load PLANEX for bounded use; scalable pipelines should use ``iter_csv_chunks``."""
    return pd.concat(iter_csv_chunks(path, usecols=usecols), ignore_index=True)


def load_costex(path: str | Path, *, usecols: Sequence[str] | None = None) -> pd.DataFrame:
    """Load COSTEX for bounded use; scalable pipelines should use ``iter_csv_chunks``."""
    return pd.concat(iter_csv_chunks(path, usecols=usecols), ignore_index=True)
