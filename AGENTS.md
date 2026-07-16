# AGENTS.md - root instructions for coding agents

Every agent that changes code, configuration, documentation, tests, dashboard assets, or data-processing logic must create or update a task-specific Markdown note under:

`docs/agent_notes/`

Use this filename pattern:

`YYYY-MM-DD_<short_task_slug>.md`

Example:

`docs/agent_notes/2026-07-16_dashboard_01_pit_production.md`

The note must be written for the next agent that works on the project. It is not a marketing summary. It is an engineering handoff record.

Each note must include:

1. Task objective.
2. Files inspected.
3. Files created or modified.
4. Data inputs found or missing.
5. Implementation summary.
6. Important assumptions.
7. Commands run.
8. Test results, including failures.
9. Validation steps performed.
10. What worked.
11. What did not work.
12. Known limitations.
13. Suggested next steps.

If a task cannot be completed because data, dependencies, credentials, or environment configuration are missing, document the blocker in the task note and still commit any useful scaffolding, tests, or documentation that can be completed safely.

Do not store raw data, credentials, API keys, classified information, controlled information, or copied sensitive source rows in the notes. Summarize findings at the aggregate level unless row-level detail is explicitly safe and necessary.

## Project mission

Build a CEPE FYNSP 2028 program review dashboard suite that helps analysts test whether programming data is accurate and thorough. The project uses Python for data processing, ontology construction, AskSage integration, classification, RAG retrieval, and report generation. The user-facing interface is static HTML: one landing page and five dashboard pages.

## Required product behavior

- Every dashboard question must be written in natural language.
- Each dashboard question must be answered by a visualization, table, metric card, or drill-through component.
- Dashboards must support CEPE analyst review of accuracy, thoroughness, traceability, prioritization, acquisition executability, and site-level integration burden.
- The default exemplar integration area is Pit Production.
- The RAG agent must summarize dashboard visuals and answer user questions using chart payloads, source-row lineage, guidance context, and graph ontology context.
- The report agent must draft a 5-7 page Word-compatible report with executive summary, answers to dashboard questions, embedded exhibits, and traceable citations.

## Data rules

- Raw CSVs live in `data/raw/` and should never be overwritten by pipeline code.
- FORMEX is UTF-16 tab-delimited based on the uploaded file. The loader must auto-detect or explicitly support this.
- PLANEX and COSTEX are comma-delimited CSVs.
- Normalize column names to snake_case in curated/interim datasets.
- Never sum all FORMEX rows without filtering `submission_type`; FORMEX contains overlapping submission views.
- Use Federal Crosscuts for default portfolio/integration-area totals.
- Use Federal Site Splits for site-level analyses.
- Use GPRA Constraints only for GPRA constraint checks.
- Use Federal STAT Table only for STAT hierarchy review.
- Treat PLANEX and COSTEX as FY2026 execution context. Do not pretend they directly reconcile to FY2028-FY2032 FORMEX without a crosswalk.

## Known exploratory-analysis anchors from the uploaded files

- FORMEX: 15,591 rows and 34 source columns.
- PLANEX: 6,297 rows and 52 source columns.
- COSTEX: 49,102 rows and 56 source columns.
- Federal Crosscuts five-year totals: Baseline about $174.1B, ROT about $33.8B, UFR about $22.0B, total about $229.9B.
- Pit Production Federal Crosscuts total: about $50.3B, including about $28.8B Baseline, $15.0B ROT, and $6.5B UFR.
- Pit Production is concentrated at LANL and SRS-SRNS in Federal Site Splits.
- Account Integrator Decision is blank in the uploaded FORMEX extract.
- Account Integrator Priority is 0 in the uploaded FORMEX extract.
- DOE Priority Tier should be interpreted carefully because baseline rows may be tier 0 or blank, but Tier 1 above-baseline rows should be flagged for review.

## Coding standards

- Python code must be typed where practical.
- Use small, testable functions.
- Separate ingestion, transformation, validation, ontology, LLM/RAG, dashboard export, and reporting.
- Write tests for data contracts, quality rules, and major aggregation outputs.
- Never hardcode local absolute paths outside tests.
- Never commit secrets, API keys, tokens, or controlled data to source control.
- Configurable values belong in `config/` or environment variables.

## Front-end standards

- Use static HTML pages under `web/`.
- Dashboard pages should load JSON payloads from `data/curated/dashboard_payloads/` or from an approved static API path.
- Prefer local vendored JS/CSS assets in controlled environments. Do not assume internet access from deployed dashboards.
- Every chart needs title, source, metric definition, filters, and source-row lineage reference.

## AskSage standards

- Use `src/cepe_fynsp/asksage/client.py` as the only direct AskSage API wrapper.
- Keep AskSage instance URL, email, API key, access token, dataset IDs, and model in environment/config.
- Use the approved organizational AskSage instance. Do not hardcode one endpoint for all deployments.
- RAG answers must cite retrieved chunks and chart payload IDs. If evidence is insufficient, the agent must say so.

## See also

- `docs/agents/AGENT_01_CEPE_PROGRAM_REVIEW_CONTEXT.md`
- `docs/agents/AGENT_02_DATASETS_AND_GRAIN.md`
- `docs/agents/AGENT_03_DASHBOARD_OBJECTIVES.md`
- `docs/agents/AGENT_04_ONTOLOGY_AND_RAG.md`
- `docs/agents/AGENT_05_CODING_STANDARDS.md`
- `docs/agents/AGENT_06_REPORT_GENERATOR.md`
- `docs/agents/AGENT_07_DATA_QUALITY_RULES.md`
- `docs/agents/AGENT_08_SECURITY_AND_GOVERNANCE.md`
- `docs/agents/AGENT_09_ASKSAGE_INTEGRATION.md`
