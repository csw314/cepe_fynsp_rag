"""Synthetic scalable-ingestion coverage for FORMEX, PLANEX, and COSTEX."""

from __future__ import annotations

import hashlib
from pathlib import Path

import duckdb
import pandas as pd

from cepe_fynsp.etl.contracts import load_contract
from cepe_fynsp.etl.pipeline import ingest_all_sources
from scripts.build_synthetic_ci import prepare_project


def _write_large_source_fixture(root: Path, dataset: str, rows: int = 2) -> Path:
    contract = load_contract(dataset, root)
    frame = pd.DataFrame(
        {
            column: [f"synthetic-{index}" for index in range(rows)]
            for column in contract.required_columns_raw
        }
    )
    frame["gl_period_year"] = 2026
    frame["gl_period_number"] = list(range(1, rows + 1))
    frame[contract.canonical_amount_column] = ["1,000", ""]
    for column in contract.additional_numeric_columns:
        frame[column] = ["2.5", ""]
    output = root / contract.raw_file
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    return output


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def test_all_source_ingestion_is_columnar_contract_validated_and_immutable(tmp_path: Path) -> None:
    prepare_project(tmp_path)
    planex = _write_large_source_fixture(tmp_path, "planex")
    costex = _write_large_source_fixture(tmp_path, "costex")
    original_hashes = {path: _sha256(path) for path in (planex, costex)}

    manifest = ingest_all_sources(tmp_path)

    assert manifest["overall_status"] == "AMBER"
    assert [source["dataset"] for source in manifest["sources"]] == [
        "FORMEX",
        "PLANEX",
        "COSTEX",
    ]
    assert all(
        source["contract_validation"]["status"] == "passed" for source in manifest["sources"]
    )
    assert {path: _sha256(path) for path in original_hashes} == original_hashes
    connection = duckdb.connect()
    try:
        for dataset in ("planex", "costex"):
            parquet = tmp_path / "data" / "interim" / f"{dataset}_normalized.parquet"
            row = connection.execute(
                "select count(*), count_if(amount_parse_status = 'valid'), "
                "count_if(amount_parse_status = 'blank'), sum(amount_normalized) "
                "from read_parquet(?)",
                [str(parquet)],
            ).fetchone()
            assert row == (2, 1, 1, 1000.0)
    finally:
        connection.close()
    assert (tmp_path / "data" / "curated" / "formex_federal_crosscuts.parquet").is_file()
    assert (tmp_path / "data" / "curated" / "formex_site_splits.parquet").is_file()
