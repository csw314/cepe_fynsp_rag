# Dashboards 02-05 Pit Production Handoff

## Task objective

Implement the remaining deterministic Pit Production dashboards: acquisition and schedule executability, site capacity and integration burden, priority/tier/program-request challenge, and findings/report preparation. Preserve Dashboard 1's FORMEX layer discipline, aggregate-only traceability, static HTML pattern, RAG-prep outputs, and lightweight ontology exports.

## Files inspected

- Supplied task brief, root/scoped `AGENTS.md` instructions, all required project context documents, and the Dashboard 1 handoff note.
- Dashboard 1 generator, quality rules, payload helper, loader/normalizer, graph helper, reporting outline, CLI, config, README, static assets/pages, and existing unit tests.
- FORMEX header only (no source records were copied to notes). The expected UTF-16/tab-delimited source remains under `data/raw/formex/`.

## Files created or modified

- Created `src/cepe_fynsp/dashboards/dashboard_support.py` for shared Dashboard 2-5 loading, payload schema, RAG JSONL, graph, lineage, and manifest-writing helpers.
- Created Dashboard 2-5 generators: `dashboard_02_acquisition_schedule.py`, `dashboard_03_site_capacity.py`, `dashboard_04_priority_challenge.py`, and `dashboard_05_findings_report_generator.py`.
- Updated `scripts/run_etl.py` for `--dashboard 02`, `03`, `04`, `05`, and ordered `all` support.
- Updated `README.md` command documentation.
- Created `tests/unit/test_dashboard_02.py`, `test_dashboard_03.py`, `test_dashboard_04.py`, and `test_dashboard_05.py`.
- Created shared `web/assets/js/dashboard_renderer.js` and page-specific `dashboard_02.js` through `dashboard_05.js`.
- Replaced the four placeholder static pages under `web/dashboards/02_acquisition/`, `03_site_capacity/`, `04_priority_challenge/`, and `05_findings_report_generator/`; updated `web/index.html` implementation statuses.
- Generated ignored artifacts beneath `data/curated/dashboard_payloads/`, `data/curated/rag_chunks/`, `data/ontology/`, and `data/reports/html/`.

## Data inputs found or missing

- Found exactly one FORMEX CSV with the expected acquisition, priority, site, traceability, fiscal-year, and funding fields.
- Dashboard 2/4 use only Federal Crosscuts. Dashboard 3 uses only Federal Site Splits. Dashboard 5 derives from generated Dashboard 1-4 aggregate artifacts.
- PLANEX and COSTEX were deliberately excluded because no FY2026-to-FY2028-FY2032 crosswalk is in scope.
- Guidance chunks were not found as a required artifact input. Dashboard 5 therefore emits `pending guidance chunk ingestion` rather than fabricating citations.

## Implementation summary

- `dashboard_support.py` reuses Dashboard 1's FORMEX normalization, scenario selection, and Pit Production filter. Its new payload schema includes every requested top-level field, bounded lineage, source hash, generated timestamp, RAG traceability references, and graph output.
- Dashboard 2 produces six Crosscuts/Site Splits artifacts for acquisition-type funding, ranked lines, schedule/funding alignment, column-tolerant schedule exceptions, LI TEC/LI OPC site-year concentration, and material ROT/UFR acquisition priority signals. The fallback materiality threshold is $100M.
- Dashboard 3 produces site rankings, site-year values, above-baseline shares, sub-office/site matrices, year-over-year surge/cliff flags (25% default; zero prior-year becomes `new_funding`), and deterministic scope-quality findings.
- Dashboard 4 produces Pareto ROT/UFR requests, Tier 1 above-baseline review triggers, duplicate-priority evidence retaining blank/zero/non-numeric categories, deterministic request-intent labels, per-request traceability component scores, and Account Integrator completeness findings.
- Dashboard 5 reads Dashboard 1-4 manifests/payloads and writes evidence-linked accuracy findings, coverage matrix, risk/opportunity review table, exhibit gallery, citation-lineage table, and `data/reports/html/dashboard_05_report_manifest.json`. Missing upstream artifacts are built automatically if Dashboard 5 is run alone.
- Each static page has six natural-language question sections, generated metric/table container, precomputed AI Summary, traceability/limitations disclosure, and disabled AskSage affordance. There are no browser-side credentials, secrets, URLs, or live AskSage calls.

## Important assumptions

- FORMEX submission layers are overlapping and must never be summed together.
- Acquisition schedule exceptions, priority/tier flags, deterministic text labels, site surges, and findings are review triggers, not confirmed data errors or executability conclusions.
- Program-priority numeric values at or below 3 are only displayed as transparent priority signals for Dashboard 2; they do not establish request merit.
- The $100M materiality and 25% site year-over-year thresholds are defaults because no configured thresholds were present.
- The static site must be served from the repository root or an equivalent static host exposing both `web/` and `data/`.

## Commands run

- Read the task brief, all required instructions/context, Dashboard 1 reference files, and FORMEX header.
- `./.venv/Scripts/python.exe -m compileall -q src scripts`
- `./.venv/Scripts/python.exe scripts/run_etl.py --dashboard 02`
- `./.venv/Scripts/python.exe scripts/run_etl.py --dashboard 03`
- `./.venv/Scripts/python.exe scripts/run_etl.py --dashboard 04`
- `./.venv/Scripts/python.exe scripts/run_etl.py --dashboard 05`
- `./.venv/Scripts/python.exe -m pytest tests/unit -q`
- `./.venv/Scripts/python.exe -m ruff check` on all changed Python modules, CLI, and tests.
- `./.venv/Scripts/python.exe scripts/run_etl.py --dashboard all`
- PowerShell JSON, RAG-record-count, graph-edge, required-field, required-page-section, AskSage-affordance, report-manifest, and landing-page-link integrity checks.

## Test results, including failures

- Final `pytest tests/unit -q`: **24 passed**. This includes existing `test_dashboard_01.py` and `test_normalize.py` plus new Dashboard 2-5 coverage.
- Final Ruff check: **all checks passed**.
- Final Python bytecode compilation: **passed**.
- First Dashboard 3 real-data generation exposed a pandas extension-array failure while unstacking the Site Splits aggregate; the calculation was changed to explicit grouped dictionaries and then built successfully.
- First new-test run had four failures: synthetic rows did not make an acquisition row eligible for the missing-date rule, the test fixture had duplicate normalized amount columns, priority duplicates were separated by funding level, and the delay regex did not match `Delayed`. The fixture and deterministic rule were corrected; the final suite passed.
- One exploratory PowerShell graph-type command had an invalid interpolated variable/colon expression. It was corrected; graph types were then printed and dangling-edge validation completed.

## Validation steps performed

- Ran the complete ordered build successfully: Dashboard 1, 2, 3, 4, then 5.
- Confirmed each Dashboard 2-5 manifest has exactly six payload entries; all six required payload paths, one RAG JSONL with six records, and one ontology graph exist.
- Confirmed every new payload contains requested metadata, data, summary, limitations, and traceability fields.
- Confirmed all graph edges target existing nodes; generated graph node types reflect the dimensions applicable to each dashboard.
- Confirmed Dashboard 5 report manifest exists.
- Confirmed each new HTML page has six question sections, six disabled AskSage affordances, shared renderer references, and generated-data status text; confirmed landing page links to all five dashboards.
- Static markup/path inspection was performed. No browser visual test was run in this environment.

## What worked

- Dashboard 1's loader/normalizer/filter conventions could be reused directly, preventing inconsistent Pit Production filtering and layer mixing.
- FORMEX generated artifacts successfully for all five dashboards from the available source.
- The generic static renderer minimizes duplicated chart/table, summary, and traceability JavaScript while keeping all production values in JSON payloads.
- Dashboard 5 can run after `--dashboard all` and can also build absent upstream artifacts safely when invoked directly.

## What did not work

- The initial pandas unstack approach for Dashboard 3 was not compatible with the local pandas extension-array behavior; it was replaced with a deterministic grouped-dictionary calculation.
- A visual browser/accessibility review could not be performed here; static structural checks are not a substitute for interactive review.
- Live AskSage Q&A was intentionally not implemented because no approved backend endpoint and configured credentials were in scope.

## Known limitations

- Dashboard pages use accessible generated tables for the required evidence components rather than rich client-side chart libraries; this keeps the static stack dependency-light.
- Guidance passage citation slots are explicit but remain pending approved guidance chunk ingestion.
- The report output is a structured manifest, not a DOCX. It does not create analyst narrative or make unsupported conclusions.
- Data quality, schedule, priority, and executability results are deterministic review prompts. They require analyst investigation of payload lineage and additional execution evidence before a CEPE conclusion.
- No PLANEX/COSTEX reconciliation, scenario selector, or live data filters were added.

## Suggested next steps

1. Serve the repository root through an approved local/internal HTTP host and conduct a browser, accessibility, and analyst-usability review of all five pages.
2. Ingest approved guidance chunks and connect their IDs to Dashboard 5 citation-lineage records.
3. Add a protected backend AskSage endpoint only if approved, retaining the aggregate evidence boundary and no browser-side credentials.
4. Use the Dashboard 5 manifest to implement an analyst-reviewed DOCX export with chart snapshots and citation manifest.
5. Confirm or configure organization-approved materiality/surge thresholds before operational use.
