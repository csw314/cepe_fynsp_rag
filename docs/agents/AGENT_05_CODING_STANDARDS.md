# AGENT 05 - coding standards

## Purpose

This file provides coding instructions for agents working in the repository.

## Architecture rules

- Keep the pipeline modular.
- Do not put dashboard logic inside raw loaders.
- Do not put AskSage calls inside ETL functions.
- Do not put secrets in source code.
- Prefer deterministic transformations before LLM enrichment.
- LLM outputs must be persisted with metadata and should be reviewable.

## Package layout

- `src/cepe_fynsp/config.py`: configuration loading.
- `src/cepe_fynsp/etl/`: raw data ingestion and normalization.
- `src/cepe_fynsp/quality/`: deterministic quality and reconciliation checks.
- `src/cepe_fynsp/ontology/`: graph construction and export.
- `src/cepe_fynsp/asksage/`: AskSage client wrappers.
- `src/cepe_fynsp/agents/`: prompt templates and agent orchestration.
- `src/cepe_fynsp/dashboards/`: dashboard metric calculation and JSON payload export.
- `src/cepe_fynsp/reporting/`: report drafting and Word-compatible export.
- `web/`: static HTML, CSS, and JS.

## Data engineering rules

- Load FORMEX with `encoding="utf-16"` and `sep="\t"` unless auto-detection proves otherwise.
- Drop trailing unnamed export columns when fully null.
- Normalize column names with a deterministic mapping.
- Preserve original row numbers or create stable row hashes for lineage.
- Parse amounts by removing commas and converting to numeric.
- Parse fiscal years from strings like `FY2028` into integers where needed.
- Preserve original strings alongside normalized fields when material.
- Store normalized/interim outputs as Parquet.
- Store dashboard payloads as JSON.

## Aggregation rules

- Require explicit `submission_type` filters for every FORMEX aggregation.
- Require explicit `scenario` filters when multiple scenarios exist.
- Use `program_int_area` filters for programmatic integration area dashboards.
- Use `process_imp_area` filters only for process-improvement questions.
- Do not use Federal Site Splits to replace Crosscuts totals without noting the analytic purpose.
- Reconciliation outputs should state the left source, right source, keys, and variance.

## Testing rules

Unit tests should cover:

- FORMEX loader detects/handles UTF-16 tab-delimited export.
- Amount parsing works for comma-formatted dollars and negatives.
- Submission-layer filter is required for FORMEX totals.
- Pit Production Federal Crosscuts totals are within expected tolerance for the uploaded data.
- Account Integrator blank/zero fields are detected.
- Tier 1 above-baseline flags are detected.
- Dashboard payloads include required metadata.
- Ontology export includes required node and edge types.

## HTML rules

- One landing page: `web/index.html`.
- Five dashboard pages under `web/dashboards/`.
- Shared CSS in `web/assets/css/`.
- Shared JS in `web/assets/js/`.
- Dashboard pages should render from JSON payloads, not hardcoded table values.
- Each chart container must include a data source note and a button/control for RAG summary.

## Accessibility and usability rules

- Use readable chart titles.
- Include text summaries for visual findings.
- Include tabular drill-throughs for flagged rows.
- Support filters for fiscal year, funding level, sub-office, site, acquisition type, and program request where relevant.
- Avoid color-only encodings for risk or category.

## Required continuation notes

For each coding task, maintain a task-specific note in `docs/agent_notes/`.

The note should be updated during the work, not reconstructed from memory only at the end. It should be specific enough that another agent can continue without re-discovering the same issues.

The final response from the agent should summarize:

- Main files changed.
- Main capability added.
- Tests run.
- Location of the handoff note.
- Any unresolved blockers.