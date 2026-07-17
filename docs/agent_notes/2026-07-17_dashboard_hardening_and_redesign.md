# Dashboard hardening and redesign handoff

## 1. Task objective

Examine the entire repository and the newly supplied FORMEX, PLANEX, and COSTEX extracts; adapt ingestion, contracts, analytics, and dashboards for changed schemas and much larger PLANEX/COSTEX volumes; then implement the applicable data-integrity, architecture, dashboard, findings, RAG, AskSage, reporting, dependency, CI, test, accessibility, and security requirements in the attached hardening brief.

The implementation must preserve the five dashboards and all 30 mandatory questions, keep raw data immutable, keep browser artifacts aggregate-only, and avoid a false FY2028–FY2032 FORMEX reconciliation to FY2026/historical execution data without an approved crosswalk.

## 2. Files inspected

- Inventoried all 93 repository files present at task start, excluding `.git` internals; the three ignored source CSVs accounted for nearly all repository-workspace volume.
- Read the complete 1,642-line attached task brief. It contains a repeated copy of the requirements.
- Read root `AGENTS.md` and every scoped instruction file: all nine `docs/agents/AGENT_*.md` files; `src/cepe_fynsp/AGENTS.md`; the `agents`, `asksage`, `dashboards`, `etl`, `ontology`, `quality`, and `reporting` scoped files; `tests/AGENTS.md`; and `web/AGENTS.md`.
- Read every Python module/script, every test, every HTML/CSS/JavaScript file, all configuration and contract YAML, README/architecture/security notes, prior handoffs, `.env.example`, `.gitignore`, packaging files, and all other non-empty text files. Empty `.gitkeep` files were inventoried.
- Inspected Git branch/status/history. Work began on clean `main` at `c6d4b46`.
- Consulted the current official AskSage API, endpoint, and OpenAI-compatibility documentation to verify instance-specific User/Server endpoints, token exchange, authentication headers, and chat-completions routing.

Instruction interpretation used during implementation:

- Questions in `AGENT_03_DASHBOARD_OBJECTIVES.md` are immutable and must appear once each.
- Federal Crosscuts and Federal Site Splits are overlapping, non-additive views. Crosscuts remain the default portfolio layer and Site Splits the site-distribution layer.
- Real-data diagnostics in this note are aggregate only; no source rows, credentials, or controlled text were copied.

## 3. Files created or modified

Created:

- `.github/workflows/ci.yml`
- `docs/agent_notes/2026-07-17_dashboard_hardening_and_redesign.md`
- `docs/finding_dispositions.md`
- `scripts/build_synthetic_ci.py`
- `scripts/validate_browser.py`
- `scripts/validate_static.py`
- `src/cepe_fynsp/agents/rag_agent.py`
- `src/cepe_fynsp/dashboards/landing.py`
- `src/cepe_fynsp/etl/contracts.py`
- `src/cepe_fynsp/etl/financial.py`
- `src/cepe_fynsp/etl/pipeline.py`
- `src/cepe_fynsp/reporting/generator.py`
- `src/cepe_fynsp/schemas.py`
- `tests/integration/test_source_ingestion.py`
- `tests/integration/test_synthetic_end_to_end.py`
- `tests/unit/test_asksage_client.py`
- `tests/unit/test_contracts_lineage_ontology.py`
- `tests/unit/test_financial_integrity.py`
- `tests/unit/test_schemas.py`
- `web/assets/js/landing.js`

Materially modified:

- `.env.example`, `README.md`, `requirements.txt`, `pyproject.toml`, `data/raw/README.md`, and `docs/architecture/PROJECT_STRUCTURE.md`
- `config/settings.yaml` and all three `config/data_contracts/*.yaml`
- `scripts/run_etl.py`
- `src/cepe_fynsp/asksage/client.py`, `config.py`, `etl/loaders.py`, `etl/normalize.py`, `ontology/build_graph.py`, and `quality/rules.py`
- All five dashboard calculation/composition modules and `dashboards/dashboard_support.py`
- Existing Dashboard 1, 2, and 5 tests; Dashboard 3/4 tests received Ruff formatting only
- `web/index.html`, all five dashboard HTML pages, `web/assets/css/site.css`, `dashboard_01.js`, and `dashboard_renderer.js`

Generated validation outputs remain ignored and were not added to Git: normalized/curated Parquet, source profiles, 30 dashboard payloads, five manifests, five RAG JSONL files, graph JSON/JSON-LD, landing summary, DOCX/HTML report, seven PNG exhibits, and citation manifest.

## 4. Data inputs found or missing

Found one ignored CSV in each configured raw source directory:

- FORMEX `data/raw/formex/CSV Download.csv`: UTF-16/tab, 15,607 rows, 34 source headers including one blank trailing export header; 33 meaningful normalized source columns. One scenario; FY2028–FY2032; four overlapping submission views. All 15,607 canonical amounts are valid and 249 are negative. The profile-only sum across all overlapping views is approximately $898.0B and must not be used as a portfolio total.
- PLANEX `data/raw/planex/idw_planex_202607171050.csv`: UTF-8/comma, 78,298 FY2026 rows and 53 columns, versus the stale 6,297-row/52-column anchor. Twelve WBS hierarchy level/name pairs are present. All 78,298 `cost_plan` values parse, 4,083 are negative, and the aggregate is approximately $27.888B.
- COSTEX `data/raw/costex/idw_costex_202607171052.csv`: UTF-8/comma, 818,934 rows and 58 columns, versus the stale 49,102-row/56-column anchor. Fiscal scope is FY2023–FY2026 and twelve WBS hierarchy level/name pairs are present. `dollars` has 814,902 valid values, 4,032 blanks, zero invalid values, and 70,858 negatives. Its valid-value aggregate is approximately $30.039B. The blank canonical values make source health AMBER and the COSTEX aggregate status partial, not complete and not zero-filled.

All sources have consistent row widths and no duplicate normalized headers. Guidance inputs under `data/raw/docs/` are missing. No approved FORMEX/PLANEX/COSTEX crosswalk or controlled finding disposition file was found.

Updated FORMEX Crosscuts aggregates used as real-data regression anchors:

- Federal Crosscuts: Baseline $173.692B, ROT $34.413B, UFR $21.989B; total $230.094B.
- Pit Production Federal Crosscuts: Baseline $28.531B, ROT $15.283B, UFR $6.453B; total $50.268B.
- Pit Production above-baseline total: $21.736B.
- Pit Production Crosscuts and Site Splits reconcile at total level in the current extract. Site distribution remains concentrated at LANL and SRS-SRNS.

## 5. Implementation summary

### Source ingestion and financial integrity

- Replaced stale raw filenames in typed settings/contracts and retained safe single-CSV discovery for authorized filename changes.
- Added strict Pydantic settings for project paths, FORMEX behavior, dashboards, AskSage, reports, and quality thresholds. Unknown settings fail instead of drifting silently.
- Made all three YAML contracts executable. Header normalization collisions, missing required columns, fiscal-year domains, FORMEX scenario/submission/funding domains, and source shapes fail clearly.
- Added format detection for UTF-16/tab FORMEX and UTF-8/comma inputs. Large PLANEX/COSTEX ingestion uses DuckDB and atomic Parquet writes, avoiding an eager 681 MB pandas load.
- Centralized monetary parsing. Every value retains raw, normalized, parse-status, and parse-error fields. Blank, invalid, excluded, explicit zero, and negative values are distinct.
- Financial aggregates use `min_count=1` semantics and carry valid/blank/invalid/excluded/total counts, completeness percentage, and complete/partial/unavailable/invalid/not-evaluated status. Invalid values are excluded and reported by deterministic FQ003.
- Added source-health manifest and explicit curated FORMEX Crosscuts/Site Splits/Pit layers. Raw inputs are never overwritten.

### Stable lineage, schemas, ontology, and RAG

- Split lineage into location ID, canonical content hash, stable record ID, duplicate count/occurrence, and original row number. Content hashes and record-ID sets are stable under row reordering; duplicate occurrences remain auditable.
- Added strict schema-v2 models for columns, visualization specifications, metrics, narratives, payloads, manifests, RAG packets/answers, findings/dispositions, and citations. Unsupported versions and ungrounded narrative/RAG records fail validation.
- Every emitted dashboard payload and manifest is validated before atomic write. Column schemas include all aggregate fields and no arbitrary first-ten-property inference.
- Ontology identifiers now use readable slug plus a short SHA-256 suffix. Graph creation detects collisions and dangling references and emits graph JSON plus JSON-LD.
- RAG packets include all required evidence fields and are generated only from aggregate payloads, quality results, lineage hashes/IDs, and graph IDs. `agents/rag_agent.py` validates payload/ontology/lineage references, ranks local evidence, returns deterministic insufficient-evidence behavior, and can request an optional bounded AskSage narrative marked pending human review.

### Dashboard and landing interface

- Preserved all 30 mandatory questions exactly once and consolidated every dashboard onto one dependency-free renderer.
- Added a generated executive landing page with programmed funding, above-baseline pressure, finding severity, reconciliation, completeness, leading-site concentration, source health, and priority actions. No analytical total is hard-coded in HTML.
- Added persistent suite navigation, question anchors, skip links, deterministic data-health banners, visible warnings, build and interactive filter states, removable filter chips, reset, keyboard-operable cross-filters, and ARIA announcements.
- Added stacked bars, ranked bars/Pareto views, heatmaps/matrices, diverging change views, a schedule timeline, priority bubble plot, reconciliation variance view, finding cards, and accessible evidence tables. Every panel shows title, question, units, source, metric definition, filters, completeness, limitations, narrative origin, and traceability.
- Tables use explicit schemas and support search, sortable/sticky headers, pagination, row counts, column visibility, conditional text status, and CSV export of the complete filtered aggregate view. No first-100-row or first-ten-column truncation remains.
- Payload loading uses schema checks and `Promise.allSettled`; one failed payload produces a precise panel error without disabling other questions.
- CSS adds restrained executive styling, visible focus, high-contrast status labels, reduced motion, responsive layouts, and print rules. There are no CDN, remote font, or runtime internet references and no third-party frontend library/license to record.

Expected page payloads are the six files declared by each dashboard's generated `manifest.json` under `data/curated/dashboard_payloads/<dashboard_id>/`. Every question section contains one metric container, one visualization/evidence container, one origin-labelled narrative container, and one traceability container.

### Findings, AskSage, and reporting

- Dashboard 5 findings now carry operational read-only fields for severity, consequence, evidence, owner, workflow status, due date, management response, and analyst disposition. Optional controlled JSON dispositions are strictly validated; duplicate/unknown IDs and non-ISO due dates fail. The browser has no write-back path.
- Replaced ambiguous “AI Summary” labels with calculated observation, deterministic conclusion, source evidence, limitation, analyst interpretation, or AI-generated narrative origins.
- Hardened the sole AskSage client boundary with explicit host allowlisting, instance-path rejection, retry/backoff/jitter, connect/read timeouts, structured redacted errors, response content/schema validation, token exchange/caching, correlation IDs, and an unavailable-safe fallback. ETL/dashboard/report generation does not depend on AskSage.
- Added deterministic management-report generation from validated payloads. It writes a valid DOCX, HTML companion, 30-question answer table, seven locally rendered exhibits, report manifest, and citation manifest. The report includes both required report-agent sections and supporting programmed-funding/acquisition/site/priority/data-quality/action/evidence subsections. Citations retain chart/payload IDs, finding/rule IDs, metric definitions, filters, source files, RAG IDs, and ontology paths. Optional AI text is false by default.

### Dependencies and CI

- Removed the private editable self-reference and reduced runtime dependencies to imports/documented runtime needs. Runtime, development, and notebook dependencies are separated and compatibly bounded.
- Added push/PR CI for Ruff lint/format, mypy, compileall, pytest, a full synthetic five-dashboard/report build, offline/static/raw-data checks, secret-pattern scanning, and `pip-audit` against runtime requirements.
- Added isolated synthetic source/build scripts so CI never requires controlled files.

## 6. Important assumptions

- The configured current source filenames are the authorized extracts for this task. Single-file discovery remains a migration fallback, not permission to combine exports.
- PLANEX is FY2026 execution-plan context. COSTEX is FY2023–FY2026 historical/execution context. Only appropriately scoped FY2026 comparisons are supportable, and no detailed FORMEX reconciliation is asserted without a crosswalk.
- A blank or invalid monetary value is unknown/unusable, never a valid zero. Negative values remain included and are review triggers rather than automatic errors.
- Generated static payloads may contain aggregate values and bounded opaque lineage identifiers/hashes, but never raw controlled rows.
- The deterministic status rule is RED for invalid canonical monetary values, AMBER for blanks/exclusions without invalids, GREEN when all included canonical values are valid, and NOT EVALUATED where evidence is unavailable.
- The exact Word page count depends on the local renderer; automated tests validate structure rather than pagination.

## 7. Commands run

Environment/baseline and profiling:

- `git status --short`, `git branch --show-current`, and `git log -5 --oneline`
- Repository inventories using `rg --files`, `Get-ChildItem`, and byte/line counts
- `py -3.12 -m compileall src scripts`
- Initial `py -3.12 -m pytest`, Ruff, mypy, and build commands (blocked before `.venv` installation as documented below)
- Full streaming structural/domain/financial profiles of every row in all three sources; only aggregate diagnostics were printed
- `py -3.12 -m venv .venv`
- `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"` (run initially and again after dependency rationalization)
- `.\.venv\Scripts\python.exe -m pip install pip-audit`

Final quality/security checks:

- `.\.venv\Scripts\ruff.exe check .`
- `.\.venv\Scripts\ruff.exe format --check .`
- `.\.venv\Scripts\mypy.exe src`
- `.\.venv\Scripts\python.exe -m compileall -q src scripts`
- `.\.venv\Scripts\python.exe -m pytest -q`
- `.\.venv\Scripts\python.exe scripts\build_synthetic_ci.py`
- `.\.venv\Scripts\python.exe scripts\validate_static.py`
- `node --check` for every `web/assets/js/*.js`
- `.\.venv\Scripts\pip-audit.exe -r requirements.txt`
- Git secret-pattern scan for common OpenAI/AWS/GitHub token prefixes
- Generated-artifact validation through `validate_synthetic_outputs(Path('.'))` and `load_validated_rag_corpus(Path('.'))`
- Mojibake and stale product-label scans with `rg`

Real build and browser:

- `.\.venv\Scripts\python.exe scripts\run_etl.py --dashboard all`
- `.\.venv\Scripts\python.exe scripts\run_etl.py --ingest-sources --dashboard 01`
- `.\.venv\Scripts\python.exe scripts\run_etl.py --ingest-sources --dashboard all` (final command, rerun after the last source-manifest correction)
- `.\.venv\Scripts\python.exe scripts\validate_browser.py`

## 8. Test results, including failures

Final result: 60 tests passed in 4.59 seconds; zero failed and zero skipped.

Test files added:

- `tests/integration/test_source_ingestion.py`
- `tests/integration/test_synthetic_end_to_end.py`
- `tests/unit/test_asksage_client.py`
- `tests/unit/test_contracts_lineage_ontology.py`
- `tests/unit/test_financial_integrity.py`
- `tests/unit/test_schemas.py`

Test files modified:

- `tests/unit/test_dashboard_01.py`
- `tests/unit/test_dashboard_02.py`
- `tests/unit/test_dashboard_05.py`
- Dashboard 3 and 4 test files were Ruff-formatted without behavioral changes.

Coverage added includes explicit zero/blank/invalid/null-only/partial/negative/offset-heavy aggregates; mixed and unknown funding; missing reconciliation side; collisions/missing columns/invalid domains; invalid dates and end-before-start rules; reorder/duplicate/content-hash stability; six questions and visualization contracts; completeness/filters/non-overlap; offline/no-truncation/panel isolation scaffolding; schema versions; graph collisions/dangling references; RAG citations/invalid references/origins; AskSage timeout/retryable/non-retryable/invalid JSON/schema/host/redaction/fallback/token cache; finding dispositions; full DOCX/exhibits/citations; and deterministic no-AskSage operation.

Failures encountered and resolved:

- Before environment setup, pytest/Ruff/mypy/package imports were unavailable. An ignored Python 3.12 `.venv` resolved this.
- Unchanged baseline: 24 tests passed; Ruff lint passed; Ruff format found 12 unformatted files; mypy reported missing stubs plus one Dashboard 5 type error.
- First implementation run had four expected compatibility failures: new completeness fields, strict fixture contracts, legacy reconciliation input, and updated report status. Product code and synthetic fixtures were corrected.
- The first Dashboard 5 graph build found a real duplicate-finding label collision across detail/roll-up records. Finding identity was made stable across payloads.
- One acceptance run found three test/check defects: a valid two-layer quality control was treated as prohibited addition, `data/raw/README.md` was treated as raw data, and MultiDiGraph edge unpacking was incorrect. All three were fixed.
- Installing broad pandas stubs produced 67 mostly false-positive pandas typing errors. Unused dependencies/stubs were removed, eight remaining real annotations were corrected, and final mypy passes.
- One RAG citation validator was initially attached to the answer model instead of the packet model. The test caught it; the validator was moved.
- One optional PowerShell scan used the unsupported `||` separator under Windows PowerShell 5.1. It was rerun with explicit exit-code handling.
- A long one-line background-server command was rejected by command policy. It was replaced by the repository-local `validate_browser.py`, which uses an in-process loopback server and headless browser without persistent background processes.

## 9. Validation steps performed

- Final Ruff lint: passed.
- Final Ruff formatting check: 46 files already formatted.
- Final mypy: success across 30 source files.
- Final compileall: passed for `src` and `scripts`.
- Final pytest: 60 passed, none skipped.
- Synthetic build: five dashboards, 30 payloads, 30 RAG records, and 218 graph nodes; valid DOCX/report outputs.
- Real artifact validation: five manifests, 30 schema-v2 payloads, 30 schema-v2 RAG records, and 400 graph nodes; no dangling or invalid payload/ontology/lineage references.
- Final real-data ingestion/build: passed for all 912,839 source rows and all five dashboards; source health AMBER only because of the 4,032 blank COSTEX `dollars` values.
- Dependency audit: no known vulnerabilities in `requirements.txt`; pip-audit emitted only a Windows temporary-path case/short-name warning.
- Static/offline validation: passed mandatory questions, local assets, accessible scaffolding, renderer behaviors, secret markers, and raw-data Git policy.
- JavaScript syntax: all local JS files passed Node syntax checks.
- Secret scan: no common committed secret token pattern found.
- Headless Chrome validation executed the landing page and all five dashboards over loopback HTTP. Landing rendered six generated metrics. Every dashboard rendered six ready panels, six analytical visuals, six complete evidence tables, supported filter controls, and zero panel errors.
- Report validation: valid Open XML DOCX; eight required top-level sections, supporting subsections, one 30-question table, seven embedded images, 48 citations, metric definitions on all citations, and finding IDs on applicable citations.
- Verified current generated outputs remain ignored; Git does not track raw CSV, normalized Parquet, dashboard JSON, RAG, graph, or report artifacts.

## 10. What worked

- DuckDB normalized the 681 MB COSTEX and 65 MB PLANEX sources to compressed Parquet without eager pandas loading. Final normalized sizes were approximately 140 MB COSTEX, 12.5 MB PLANEX, and 3.6 MB FORMEX.
- Strict source contracts accepted the current 34/53/58-header exports and correctly separated the blank trailing FORMEX artifact from 33 meaningful source fields.
- Status-aware aggregation preserved negative/zero semantics and exposed partial COSTEX completeness rather than hiding 4,032 blanks.
- Shared schema/payload/graph/RAG infrastructure removed version drift across Dashboard 1 and Dashboards 2–5.
- The complete product remains useful without AskSage and without internet access.
- Headless browser execution confirmed the renderer resolves real generated data across all six pages with no all-or-nothing load failure.

## 11. What did not work

- No approved guidance documents exist, so real guidance-passage retrieval/citations and guidance-aware recommendations could not be implemented or validated. Outputs say evidence is pending rather than inventing it.
- No approved crosswalk exists, so PLANEX/COSTEX cannot be used for detailed FY2028–FY2032 FORMEX reconciliation. They are ingested, validated, profiled, and exposed as execution/source-health context only.
- No approved AskSage credentials or organizational host were provided. Live calls were intentionally not made; all client behavior was tested with mocks.
- Pixel-level/manual browser review, screen-reader testing, and interactive click automation were not available in the tool setup. Headless Chrome executed all pages and local JavaScript; static tests cover filter/search/sort/error/print/responsive implementation, but a human accessibility review remains appropriate.

## 12. Known limitations

- The report is a deterministic draft and requires analyst review. Word pagination varies, so automated tests do not assert an exact 5–7 page count.
- The source-health summary currently reports canonical amount completeness. Additional COSTEX numeric columns retain their own parse metadata in Parquet, but their completeness is not yet promoted to separate landing-page cards.
- Client-side filters operate only on browser-safe aggregate dimensions already present in each payload. A global filter is ignored by panels that do not contain that dimension, and the UI labels original metric cards as build-scope when an applicable interactive filter is active.
- The current dashboards continue to use FORMEX as the programming evidence source. PLANEX/COSTEX detail is intentionally not sent to static browser payloads without an approved analytical use/crosswalk.
- Finding disposition input is JSON only. It is read-only and controlled outside the browser.
- CI was executed locally command-for-command; the new GitHub Actions workflow has not yet run on the remote service.

## 13. Suggested next steps

1. Obtain and govern an approved FORMEX/PLANEX/COSTEX crosswalk before adding execution reconciliation or detailed PLANEX/COSTEX dashboard measures.
2. Ingest approved guidance documents and add guidance-chunk IDs/quotes within governance limits; then validate guidance-aware RAG/report citations.
3. Provide the approved organizational AskSage hostname and credentials through the deployment secret store, set `ASKSAGE_APPROVED_HOSTS`, and perform a protected non-production connectivity test.
4. Have a CEPE analyst review the deterministic findings/report and create the controlled disposition JSON described in `docs/finding_dispositions.md`.
5. Run the new CI workflow on the remote repository and add the project’s approved enterprise secret/SBOM scanners if they are required beyond pip-audit and the included scan.
6. Perform human keyboard, screen-reader, responsive visual, and printed-report review in the approved deployment browser/Word environment.
