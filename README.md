# CEPE FYNSP 2028 Program Review Dashboard Suite

This project scaffold supports five HTML dashboards for CEPE-style FYNSP 2028 program review. Python handles data ingestion, normalization, exploratory analysis, quality checks, ontology construction, AskSage integration, dashboard payload export, and report generation. The front end uses static HTML pages backed by local JSON payloads.

## Objective

Support an analyst assessing whether FYNSP programming data is accurate and thorough for an integration area. The initial exemplar integration area is Pit Production.

## Suggested workflow

1. Place raw files under `data/raw/`:
   - `data/raw/formex/CSV Download (5).csv`
   - `data/raw/planex/staging_idw_planex_202607151621.csv`
   - `data/raw/costex/staging_idw_costex_202607151618.csv`
   - program guidance files under `data/raw/docs/`
2. Copy `.env.example` to `.env` and populate local AskSage configuration.
3. Install dependencies with your approved Python environment manager.
4. Run ETL, validation, ontology export, dashboard payload export, and report generation.
5. Serve the `web/` directory locally or deploy it to the approved internal static hosting environment.

## Generate dashboards

Each dashboard reads the single UTF-16, tab-delimited FORMEX CSV under `data/raw/formex/` and writes aggregate-only static artifacts. Dashboard 5 synthesizes the generated Dashboards 1-4 artifacts and produces a report manifest; it does not make live AskSage calls or generate a DOCX.

```powershell
.\.venv\Scripts\python.exe scripts\run_etl.py --dashboard 01
.\.venv\Scripts\python.exe scripts\run_etl.py --dashboard 02
.\.venv\Scripts\python.exe scripts\run_etl.py --dashboard 03
.\.venv\Scripts\python.exe scripts\run_etl.py --dashboard 04
.\.venv\Scripts\python.exe scripts\run_etl.py --dashboard 05
.\.venv\Scripts\python.exe scripts\run_etl.py --dashboard all
```

This creates JSON payloads under `data/curated/dashboard_payloads/`, RAG context under `data/curated/rag_chunks/`, and graph exports under `data/ontology/`. Dashboard 5 also writes `data/reports/html/dashboard_05_report_manifest.json`. To view a dashboard locally, serve the repository root so both `web/` and `data/` are available, then open the desired page under `/web/dashboards/`.

## Dashboards

1. Pit Production Accuracy and Thoroughness Overview
2. Acquisition and Schedule Executability Monitor
3. Site Capacity and Integration Burden Dashboard
4. Priority, Tier, and Program Request Challenge Board
5. CEPE Findings, Evidence, and Report Generator

## Key data principle

Do not aggregate all FORMEX rows at once. FORMEX contains overlapping submission layers. Use explicit filters for `submission_type`, usually Federal Crosscuts for portfolio totals and Federal Site Splits for site distribution.
