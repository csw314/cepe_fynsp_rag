# CEPE FYNSP 2028 Program Review Dashboard Suite

This project builds one static executive landing page and five question-oriented dashboards for CEPE review of FY2028–FY2032 programming. Python performs typed ingestion, normalization, contract and quality validation, lineage, ontology/RAG export, findings synthesis, and deterministic report generation. The browser receives aggregate-only JSON and local HTML/CSS/JavaScript; it does not receive raw rows, credentials, or an internet dependency.

The default exemplar integration area is Pit Production.

## Current source files

Place immutable exports at the configured paths:

- FORMEX: `data/raw/formex/CSV Download.csv` — UTF-16, tab-delimited, overlapping submission views.
- PLANEX: `data/raw/planex/idw_planex_202607171050.csv` — comma-delimited FY2026 execution-plan context.
- COSTEX: `data/raw/costex/idw_costex_202607171052.csv` — comma-delimited FY2023–FY2026 cost context.

The names are configurable in `config/settings.yaml`. Source contracts are executable YAML under `config/data_contracts/`. Raw files are ignored by Git and are never overwritten.

FORMEX layers are not additive. Federal Crosscuts support portfolio totals, Federal Site Splits support site analysis, GPRA Constraints support GPRA checks, and Federal STAT Table supports hierarchy review. PLANEX and COSTEX are not presented as a direct reconciliation to FY2028–FY2032 FORMEX without an approved crosswalk.

## Install

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Runtime dependencies are bounded in `pyproject.toml` and mirrored in `requirements.txt`; development dependencies are in the `dev` extra and notebook tooling is isolated in the `notebook` extra. No private editable Git dependency is required.

## Build

Run the scalable source-ingestion path and the complete product build:

```powershell
.\.venv\Scripts\python.exe scripts\run_etl.py --ingest-sources --dashboard all
```

The large PLANEX and COSTEX files are read through DuckDB and written as normalized Parquet instead of being loaded wholesale into pandas. The command also creates:

- versioned dashboard payloads and manifests under `data/curated/dashboard_payloads/`;
- source-health and normalized source artifacts under `data/curated/source_profiles/` and `data/interim/`;
- validated RAG JSONL under `data/curated/rag_chunks/`;
- graph JSON and JSON-LD under `data/ontology/`;
- a generated landing summary;
- a deterministic DOCX, HTML companion, seven PNG exhibits, and citation manifest under `data/reports/`.

Use `--dashboard 01` through `--dashboard 05` for a bounded dashboard build. The landing summary and management report are generated after Dashboard 5 or a complete build.

Serve the repository root so both `web/` and generated `data/` paths are available:

```powershell
.\.venv\Scripts\python.exe -m http.server 8000
```

Then open `http://localhost:8000/web/`. The static UI works offline and provides deterministic data health, accessible visualizations, aggregate-only filters, cross-filters, traceability, full searchable/sortable/paginated evidence tables, and filtered aggregate CSV export.

## Validate

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe src
.\.venv\Scripts\python.exe -m compileall -q src scripts
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\build_synthetic_ci.py
.\.venv\Scripts\python.exe scripts\validate_static.py
```

The synthetic CI build creates all five dashboards and the report in a temporary directory; it does not require controlled source data. The static validator checks the mandatory question inventory, local-only assets, navigation/accessibility scaffolding, renderer acceptance behaviors, credential markers, and raw-data Git policy.

## AskSage

AskSage is optional and never blocks ETL, dashboards, or reporting. If enabled, copy `.env.example` to a local `.env`, configure the approved organizational instance, and keep all calls behind `src/cepe_fynsp/asksage/client.py`. Never put credentials in browser JavaScript or committed configuration. Generated RAG records remain evidence-bounded and cite payload, source, lineage, and ontology identifiers.

## Dashboard inventory

1. Pit Production Accuracy and Thoroughness Overview
2. Acquisition and Schedule Executability Monitor
3. Site Capacity and Integration Burden Dashboard
4. Priority, Tier, and Program Request Challenge Board
5. CEPE Findings, Evidence, and Report Generator

Each dashboard preserves the six natural-language questions defined in `docs/agents/AGENT_03_DASHBOARD_OBJECTIVES.md`.
