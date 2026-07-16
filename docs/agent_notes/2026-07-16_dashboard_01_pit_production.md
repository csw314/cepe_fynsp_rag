# Dashboard 01 Pit Production Handoff

## Task objective

Implement Dashboard 1, **Pit Production Accuracy and Thoroughness Overview**. The dashboard must generate aggregate FORMEX chart payloads, retrieval context, an ontology export, a safe AskSage request-preparation path, a static web page, and unit tests.

## Files inspected

- Repository and scoped instructions: `AGENTS.md`, `src/cepe_fynsp/AGENTS.md`, `src/cepe_fynsp/dashboards/AGENTS.md`, `src/cepe_fynsp/etl/AGENTS.md`, `src/cepe_fynsp/quality/AGENTS.md`, `src/cepe_fynsp/ontology/AGENTS.md`, `src/cepe_fynsp/asksage/AGENTS.md`, `web/AGENTS.md`, and `tests/AGENTS.md`.
- Required project context: `docs/agents/AGENT_01_CEPE_PROGRAM_REVIEW_CONTEXT.md`, `AGENT_02_DATASETS_AND_GRAIN.md`, `AGENT_03_DASHBOARD_OBJECTIVES.md`, `AGENT_04_ONTOLOGY_AND_RAG.md`, `AGENT_05_CODING_STANDARDS.md`, `AGENT_07_DATA_QUALITY_RULES.md`, `AGENT_08_SECURITY_AND_GOVERNANCE.md`, and `AGENT_09_ASKSAGE_INTEGRATION.md`.
- Existing scaffold: project configuration and FORMEX contract, ETL loader/normalizer, quality rules, ontology helper, dashboard payload helper, AskSage client, dashboard entry script, web assets/page, and existing normalization test.

## Files created or modified

- Created `src/cepe_fynsp/dashboards/dashboard_01_pit_production.py`.
- Updated `src/cepe_fynsp/quality/rules.py` with column-tolerant deterministic Dashboard 1 checks and lineage-aware findings.
- Updated `scripts/run_etl.py` with `--dashboard 01`.
- Updated `README.md` with the Dashboard 1 generation command and root-serving requirement.
- Created `tests/unit/test_dashboard_01.py`.
- Updated `web/dashboards/01_overview/index.html`, `web/assets/css/site.css`, and `web/assets/js/dashboard.js`.
- Created `web/assets/js/dashboard_01.js`.
- Created this handoff note.
- Generated (ignored) artifacts under `data/curated/dashboard_payloads/dashboard_01_pit_production/`, `data/curated/rag_chunks/dashboard_01_pit_production/`, and `data/ontology/`.

## Data inputs found or missing

- Found one FORMEX source CSV in `data/raw/formex/`; it is UTF-16 little-endian and tab-delimited. Its header matches the configured FORMEX contract, including `Program Int. Area`, `Submission Type`, `Funding Levels`, and `Formulated Measure`.
- PLANEX and COSTEX were not used because they are FY2026 execution context and no crosswalk is in scope for Dashboard 1.
- The local FORMEX build produced the expected aggregate Pit Production funding scale (about $50.27B) and the expected Baseline/ROT/UFR distribution. No row-level values are recorded here.

## Implementation summary

- `build_dashboard_01_payloads(project_root: Path | None = None)` locates exactly one FORMEX CSV, loads it as UTF-16/tab-delimited through the existing loader, normalizes columns/text/amounts/fiscal years/funding levels, and adds stable row lineage IDs.
- The build selects an explicit scenario, uses Federal Crosscuts for Q1/Q2/Q4, Federal Site Splits for Q3, and both non-additively for Q5/Q6.
- It writes six chart-ready JSON payloads and a manifest. Every payload includes chart/question metadata, source file/hash, submission layer, row filters, metric/grouping/value definitions, generation time, record count, limitations, bounded source-row lineage IDs, and ontology node IDs.
- It writes six compact aggregate-only RAG context records and an aggregate-focused ontology graph with the requested dashboard, chart, metric, source, dimension, and finding node/edge types.
- Q5 implements deterministic missing program request/scope/WBS/BNR/site/tier checks, Tier 1 ROT/UFR review triggers, acquisition metadata checks, negative-dollar review triggers, Account Integrator availability limitations, and the Q6 reconciliation result. Missing optional columns become `not_evaluated` findings.
- AskSage preparation is safe and backend-only: the module prepares an evidence-bounded summary request and can send it only through the existing `AskSageClient`; no browser credentials or live calls were added.
- The static page loads generated JSON only, renders accessible CSS charts/tables and metric cards, includes static no-JavaScript fallbacks, AI-summary panels, disabled AskSage affordances, traceability disclosures, and data-limitations disclosures.

## Important assumptions

- Dashboard totals will use only Federal Crosscuts; site analysis will use only Federal Site Splits; the selected scenario will be explicit when the source contains multiple scenarios.
- Generated assets will contain aggregate values and lineage identifiers only, not source rows.
- Live AskSage calls are out of scope unless an approved backend and credentials are configured.
- The static page is intended to be served from the repository root (or an equivalent host that exposes `data/` alongside `web/`) so its relative payload paths resolve.

## Commands run

- Read the supplied task brief and all applicable instructions/context files.
- Inspected repository file inventory, configuration, code scaffold, raw input file metadata, and FORMEX header.
- `./.venv/Scripts/python.exe -m pip install -e '.[dev]' --upgrade` (installed declared local development dependencies after discovering the virtual environment initially contained only `pip`).
- `./.venv/Scripts/python.exe -m pytest tests/unit -q`.
- `./.venv/Scripts/python.exe -m ruff check src/cepe_fynsp/quality/rules.py src/cepe_fynsp/dashboards/dashboard_01_pit_production.py scripts/run_etl.py tests/unit/test_dashboard_01.py`.
- `./.venv/Scripts/python.exe scripts/run_etl.py --dashboard 01`.
- PowerShell JSON/static integrity checks for payload count, required traceability fields, RAG record count, graph node/edge validity, required page fallback content, and absence of external CDN references.

## Test results, including failures

- `pytest tests/unit -q`: **9 passed**.
- Ruff on changed Python implementation/test files: **all checks passed**.
- Python bytecode compilation of changed Python files: **passed**.
- The initial test/lint invocation failed because the bare `python` command resolves to the Microsoft Store alias and the local virtual environment had no dependencies. Re-running through `.venv/Scripts/python.exe` after installing the declared project dependencies succeeded.

## Validation steps performed

- Confirmed the supplied FORMEX file has a UTF-16 BOM and expected tab-separated header.
- Generated Dashboard 1 from the local source through the CLI.
- Confirmed six payload files, six RAG JSONL records, and the ontology export were created.
- Confirmed every required traceability field exists in Q1; the same payload builder is used for all six questions.
- Confirmed the graph has no dangling edges and contains all requested node types.
- Confirmed the page has six question sections, six disabled AskSage controls, local JavaScript references, fallback AI/traceability content, and no external CDN reference.

## What worked

- The existing FORMEX contract, loader, normalizer, and static-dashboard scaffold provide a compatible base.
- Actual FORMEX aggregation matched the documented portfolio-scale anchors.
- Crosscuts-to-Site-Splits overall variance in the local build was $0, while the payload still retains per-funding-level reconciliation evidence.
- Generated files remain ignored by Git as configured, preventing accidental source or generated-artifact commits.

## What did not work

- PowerShell's `Format-Hex` in this environment does not support the `-Count` parameter; byte inspection was completed with `Get-Content -Encoding Byte` instead.
- `node` is not installed, so JavaScript syntax was validated by static inspection rather than `node --check`.
- An attempted temporary local HTTP-server validation was rejected by the execution policy before starting the process. Static page/payload path and markup validation were completed instead.

## Known limitations

- Live AskSage Q&A is intentionally not enabled; it requires an approved backend endpoint and configured AskSage credentials.
- The page has not been visually exercised in a browser in this environment. Serve the repository root locally or through the approved static host and inspect the six rendered sections before release.
- Quality findings are deterministic review triggers, not confirmed data errors. They do not replace analyst examination of the referenced source-row identifiers.
- Reconciliation assesses the two required FORMEX submission layers only; it does not reconcile FY2028-FY2032 FORMEX with FY2026 PLANEX/COSTEX.

## Suggested next steps

1. Open the static dashboard through a local/approved HTTP host and conduct a visual/accessibility review of all six sections.
2. Configure a protected backend AskSage endpoint if live Q&A is approved; retain the existing payload/ontology/RAG evidence boundary.
3. Add scenario selection and analyst filters only through regenerated payloads or a safe server-side API, not browser-side secrets or raw source data.
4. Reuse the Dashboard 1 payload/traceability and static-rendering patterns for Dashboards 2-5.
