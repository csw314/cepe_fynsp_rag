"""Scalable source ingestion and aggregate-only source health manifests."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
from cepe_fynsp.config import Settings, load_settings
from cepe_fynsp.etl.contracts import (
    ContractError,
    ContractValidationResult,
    DataContract,
    load_contract,
    validate_dataframe,
    validate_headers,
)
from cepe_fynsp.etl.financial import add_amount_metadata, financial_completeness
from cepe_fynsp.etl.loaders import discover_single_csv, load_formex, read_source_headers
from cepe_fynsp.etl.normalize import add_source_lineage, normalize_columns


def sha256_file(path: Path) -> str:
    """Return a streaming SHA-256 without loading a source file into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _quote_identifier(value: str) -> str:
    """Quote a validated SQL identifier for DuckDB."""
    return '"' + value.replace('"', '""') + '"'


def _quote_literal(value: str) -> str:
    """Quote a SQL string literal for DuckDB."""
    return "'" + value.replace("'", "''") + "'"


def _amount_sql(column: str, prefix: str) -> list[str]:
    """Return DuckDB expressions equivalent to the central amount parser."""
    source = _quote_identifier(column)
    raw = f"trim(coalesce(cast({source} as varchar), ''))"
    cleaned = f"replace(replace({raw}, ',', ''), '$', '')"
    normalized = (
        f"case when starts_with({cleaned}, '(') and ends_with({cleaned}, ')') "
        f"then '-' || substring({cleaned}, 2, length({cleaned}) - 2) else {cleaned} end"
    )
    blank = f"lower({raw}) in ('', '<na>', 'n/a', 'na', 'nan', 'none', 'null')"
    parsed = f"try_cast({normalized} as double)"
    return [
        f"{source} as {_quote_identifier(prefix + '_raw')}",
        f"case when {blank} then null else {parsed} end as {_quote_identifier(prefix + '_normalized')}",
        (
            f"case when {blank} then 'blank' when {parsed} is null then 'invalid' "
            f"else 'valid' end as {_quote_identifier(prefix + '_parse_status')}"
        ),
        (
            f"case when {blank} then null when {parsed} is null then 'unparseable_amount' "
            f"else null end as {_quote_identifier(prefix + '_parse_error')}"
        ),
    ]


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    """Validate serialization and atomically replace a JSON artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _atomic_duckdb_copy(connection: duckdb.DuckDBPyConnection, query: str, path: Path) -> None:
    """Write one Parquet artifact through a validated temporary path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    connection.execute(
        f"COPY ({query}) TO {_quote_literal(temporary.as_posix())} "
        "(FORMAT PARQUET, COMPRESSION ZSTD)"
    )
    os.replace(temporary, path)


def _source_path(settings: Settings, dataset: str) -> Path:
    """Resolve configured source with one-file fallback for changed extract names."""
    configured = settings.resolve_path(getattr(settings.paths, f"raw_{dataset}"))
    directory = settings.project_root / "data" / "raw" / dataset
    return discover_single_csv(directory, configured)


def _ingest_formex(
    source: Path,
    output: Path,
    contract: DataContract,
    root: Path,
) -> tuple[ContractValidationResult, dict[str, Any]]:
    """Normalize the bounded FORMEX source with full lineage and parse metadata."""
    raw = load_formex(source)
    frame = normalize_columns(raw)
    source_column_count = len(frame.columns)
    source_identity = source.relative_to(root).as_posix()
    frame = add_source_lineage(frame, "formex", source_file_identity=source_identity)
    frame = add_amount_metadata(frame, contract.canonical_amount_column)
    frame[contract.canonical_amount_column] = frame["amount_normalized"]
    result = validate_dataframe(frame, contract).model_copy(
        update={"column_count": source_column_count}
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    frame.to_parquet(temporary, index=False)
    os.replace(temporary, output)
    return result, financial_completeness(frame)


def _ingest_large_source(
    dataset: str,
    source: Path,
    output: Path,
    contract: DataContract,
    root: Path,
) -> tuple[ContractValidationResult, dict[str, Any]]:
    """Convert PLANEX/COSTEX to Parquet in DuckDB with stable lineage and parse states."""
    raw_headers = read_source_headers(source)
    headers = validate_headers(raw_headers, contract)
    if any(not name for name in headers):
        raise ContractError(f"{dataset} contains an unexpected blank source header.")
    source_identity = source.relative_to(root).as_posix()
    file_token = hashlib.sha256(source_identity.encode("utf-8")).hexdigest()[:12]
    columns = [_quote_identifier(name) for name in headers]
    canonical = ", ".join(
        f"coalesce(nullif(trim(cast({_quote_identifier(name)} as varchar)), ''), '<NULL>')"
        for name in sorted(headers)
    )
    content_hash = f"sha256(concat_ws(chr(31), {canonical}))"
    amount_columns = [contract.canonical_amount_column, *contract.additional_numeric_columns]
    parse_expressions: list[str] = []
    for amount_column in amount_columns:
        prefix = "amount" if amount_column == contract.canonical_amount_column else amount_column
        parse_expressions.extend(_amount_sql(amount_column, prefix))
    path_literal = _quote_literal(source.as_posix())
    source_query = (
        f"select {', '.join(columns)}, row_number() over () as _source_row_number "
        f"from read_csv({path_literal}, header=true, all_varchar=true, sample_size=-1, "
        "strict_mode=true, store_rejects=false)"
    )
    query = f"""
        with source as ({source_query}),
        hashed as (
            select *, {content_hash} as _content_hash
            from source
        ),
        identified as (
            select *,
                row_number() over (partition by _content_hash order by _content_hash) as _occurrence,
                count(*) over (partition by _content_hash) as _duplicate_count
            from hashed
        )
        select
            {_quote_literal(dataset)} as source_dataset,
            _source_row_number as source_original_row_number,
            _source_row_number as source_row_number,
            {_quote_literal(dataset + ":" + file_token + ":row:")} || cast(_source_row_number as varchar)
                as source_location_id,
            _content_hash as source_content_hash,
            {_quote_literal(dataset + ":" + file_token + ":")} || substr(_content_hash, 1, 20) || ':' ||
                lpad(cast(_occurrence as varchar), 4, '0') as source_record_id,
            _duplicate_count as source_duplicate_count,
            _occurrence as source_duplicate_occurrence,
            {_quote_literal(dataset + ":" + file_token + ":")} || substr(_content_hash, 1, 20) || ':' ||
                lpad(cast(_occurrence as varchar), 4, '0') as source_row_id,
            _content_hash as source_row_hash,
            {", ".join(columns)},
            {", ".join(parse_expressions)}
        from identified
    """
    connection = duckdb.connect()
    connection.execute("set preserve_insertion_order=true")
    _atomic_duckdb_copy(connection, query, output)
    year_rows = connection.execute(
        f"select distinct try_cast(gl_period_year as integer) from read_parquet({_quote_literal(output.as_posix())})"
    ).fetchall()
    years = {int(row[0]) for row in year_rows if row[0] is not None}
    allowed = {int(value) for value in contract.allowed_fiscal_years}
    if allowed and years - allowed:
        raise ContractError(f"Invalid gl_period_year values: {sorted(years - allowed)}")
    summary_row = connection.execute(
        f"""
        select
            count(*) as total,
            count_if(amount_parse_status = 'valid') as valid,
            count_if(amount_parse_status = 'blank') as blank,
            count_if(amount_parse_status = 'invalid') as invalid,
            count_if(amount_parse_status = 'excluded') as excluded,
            sum(amount_normalized) as amount
        from read_parquet({_quote_literal(output.as_posix())})
        """
    ).fetchone()
    connection.close()
    if summary_row is None:
        raise ContractError(f"No rows were ingested for {dataset}.")
    total, valid, blank, invalid, excluded, amount = summary_row
    if total == 0:
        aggregate_status = "not_evaluated"
    elif valid == total:
        aggregate_status = "complete"
    elif valid:
        aggregate_status = "partial"
    elif invalid:
        aggregate_status = "invalid"
    else:
        aggregate_status = "unavailable"
    summary = {
        "amount": float(amount) if amount is not None else None,
        "valid_amount_row_count": int(valid),
        "blank_amount_row_count": int(blank),
        "invalid_amount_row_count": int(invalid),
        "excluded_amount_row_count": int(excluded),
        "total_source_row_count": int(total),
        "completeness_percentage": round(valid / total * 100, 2) if total else None,
        "aggregate_status": aggregate_status,
        "fiscal_years": sorted(years),
    }
    result = ContractValidationResult(
        dataset=dataset,
        contract_version=contract.contract_version,
        status="passed",
        row_count=int(total),
        column_count=len(headers),
    )
    return result, summary


def _write_curated_formex(root: Path, interim_path: Path) -> None:
    """Write explicit non-additive curated FORMEX layers from normalized Parquet."""
    connection = duckdb.connect()
    source = _quote_literal(interim_path.as_posix())
    curated = root / "data" / "curated"
    _atomic_duckdb_copy(
        connection,
        f"select * from read_parquet({source}) where submission_type = 'Federal Crosscuts'",
        curated / "formex_federal_crosscuts.parquet",
    )
    _atomic_duckdb_copy(
        connection,
        f"select * from read_parquet({source}) where submission_type = 'Federal Site Splits'",
        curated / "formex_site_splits.parquet",
    )
    _atomic_duckdb_copy(
        connection,
        (
            f"select * from read_parquet({source}) where lower(trim(program_int_area)) = "
            "'pit production' and submission_type in ('Federal Crosscuts', 'Federal Site Splits')"
        ),
        curated / "integration_area_pit_production.parquet",
    )
    connection.close()


def ingest_all_sources(
    project_root: Path | None = None,
    settings_path: Path | None = None,
) -> dict[str, Any]:
    """Ingest all current sources and write a contract/versioned health manifest."""
    root = (project_root or Path(__file__).resolve().parents[3]).resolve()
    settings = load_settings(settings_path, project_root=root)
    interim = settings.resolve_path(settings.paths.interim_dir)
    records: list[dict[str, Any]] = []
    for dataset in ("formex", "planex", "costex"):
        source = _source_path(settings, dataset)
        contract = load_contract(dataset, root)
        validate_headers(read_source_headers(source), contract)
        output = interim / f"{dataset}_normalized.parquet"
        if dataset == "formex":
            validation, completeness = _ingest_formex(source, output, contract, root)
        else:
            validation, completeness = _ingest_large_source(dataset, source, output, contract, root)
        records.append(
            {
                "dataset": dataset.upper(),
                "source_file": source.relative_to(root).as_posix(),
                "source_header_column_count": len(read_source_headers(source)),
                "source_file_sha256": sha256_file(source),
                "source_file_modified_at": datetime.fromtimestamp(source.stat().st_mtime, tz=UTC)
                .replace(microsecond=0)
                .isoformat(),
                "output_file": output.relative_to(root).as_posix(),
                "contract_validation": validation.model_dump(mode="json"),
                "financial_completeness": completeness,
            }
        )
    _write_curated_formex(root, interim / "formex_normalized.parquet")
    status = (
        "RED"
        if any(record["financial_completeness"]["invalid_amount_row_count"] for record in records)
        else "AMBER"
        if any(record["financial_completeness"]["blank_amount_row_count"] for record in records)
        else "GREEN"
    )
    manifest = {
        "schema_version": "2.0",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "overall_status": status,
        "status_rule": (
            "RED when any canonical amount is invalid; AMBER when amounts are blank but none are "
            "invalid; GREEN when every canonical amount is valid."
        ),
        "sources": records,
        "crosswalk_status": "not_available",
        "crosswalk_limitation": (
            "PLANEX/COSTEX execution context is not directly reconciled to FY2028-FY2032 "
            "FORMEX without an approved crosswalk."
        ),
    }
    _atomic_json(root / "data" / "curated" / "source_profiles" / "source_manifest.json", manifest)
    return manifest
