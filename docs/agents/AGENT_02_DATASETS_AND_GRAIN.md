# AGENT 02 - datasets, grain, and analytical use

## Purpose

This file tells coding agents how to interpret FORMEX, PLANEX, and COSTEX in this project. It prevents erroneous aggregation and false joins.

## Raw input locations

- FORMEX: `data/raw/formex/CSV Download (5).csv`
- PLANEX: `data/raw/planex/staging_idw_planex_202607151621.csv`
- COSTEX: `data/raw/costex/staging_idw_costex_202607151618.csv`
- Guidance documents: `data/raw/docs/`

## Uploaded file facts from initial EDA

- FORMEX has 15,591 rows and 34 source columns.
- PLANEX has 6,297 rows and 52 source columns.
- COSTEX has 49,102 rows and 56 source columns.
- FORMEX is UTF-16 tab-delimited. The raw header includes an extra trailing unnamed field in the uploaded export.
- PLANEX and COSTEX are comma-delimited.

## Canonical FORMEX columns after normalization

Normalize to snake_case. Important columns include:

- `nnsa_appropriation`
- `stat_l3_programming`
- `stat_l4_programming`
- `stat_l5_programming`
- `construction_or_operating`
- `sub_office_number`
- `site_grouping`
- `site_planex`
- `site_name`
- `bnr_code`
- `program_value`
- `fiscal_year`
- `scenario`
- `submission_type`
- `funding_levels`
- `scope_description`
- `program_request`
- `program_int_area`
- `ukr_obbba_tmf_funds`
- `process_imp_area`
- `acquisition_type`
- `acquisition_id`
- `acquisition_name`
- `acquisition_start_date`
- `acquisition_end_date`
- `program_priority`
- `doe_priority_tier`
- `account_integrator_priority`
- `account_integrator_decision`
- `wbs`
- `wbs_name`
- `wbs_level`
- `formulated_measure`

## Analytic layer rules

FORMEX contains multiple submission types that represent overlapping views of the same scenario. Do not add across submission types.

Recommended defaults:

- Portfolio and integration-area totals: `submission_type == "Federal Crosscuts"`
- Site distribution: `submission_type == "Federal Site Splits"`
- GPRA constraint checks: `submission_type == "GPRA Constraints"`
- STAT hierarchy checks: `submission_type == "Federal STAT Table"`

## Known FORMEX EDA anchors

For Federal Crosscuts:

- Baseline total is about $174.1B.
- ROT total is about $33.8B.
- UFR total is about $22.0B.
- Total is about $229.9B.
- Pit Production total is about $50.3B.
- Pit Production Baseline is about $28.8B.
- Pit Production ROT is about $15.0B.
- Pit Production UFR is about $6.5B.
- All UFR dollars in the uploaded Federal Crosscuts extract are in NNSA-WA.

Pit Production concentration findings:

- Major sub-offices include NA-19 and NA-90.
- Major sites include LANL and SRS-SRNS.
- Major acquisition category is LI TEC, followed by a large untagged or non-acquisition portion.

## PLANEX and COSTEX use

PLANEX and COSTEX are FY2026 context data. They can support:

- Current cost plan versus actual/costed amounts.
- Costed, uncosted, encumbrance, hours, and labor category analysis.
- Execution-risk context by site, WBS, BNR, or program value where a mapping exists.

They cannot be directly reconciled to FY2028-FY2032 FORMEX at detailed grain without a crosswalk. If an agent creates a join, it must document the join keys and show unmatched percentages.

## Required outputs from ETL

The ETL should create:

- `data/interim/formex_normalized.parquet`
- `data/interim/planex_normalized.parquet`
- `data/interim/costex_normalized.parquet`
- `data/curated/formex_federal_crosscuts.parquet`
- `data/curated/formex_site_splits.parquet`
- `data/curated/integration_area_pit_production.parquet`
- `data/curated/dashboard_payloads/*.json`
- `data/curated/source_lineage/*.jsonl` if implemented
