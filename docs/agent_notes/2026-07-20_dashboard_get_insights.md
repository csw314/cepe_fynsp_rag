# Dashboard Get Insights engineering handoff

## 1. Task objective

Design, implement, test, and document one reusable, evidence-grounded AskSage **Get Insights** control for each of the 30 mandatory dashboard visualizations. Preserve static/offline dashboard operation, deterministic analysis, submission-layer integrity, aggregate-only browser data, provenance, and human-review requirements.

## 2. Agent instruction files reviewed

- Root and scoped instructions: `AGENTS.md`, `web/AGENTS.md`, `tests/AGENTS.md`, and every `AGENTS.md` under `src/cepe_fynsp/`.
- All nine `docs/agents/AGENT_*.md` files governing program context, dataset grain, dashboard objectives, ontology/RAG, coding, reporting, quality, security, and AskSage.
- `README.md`, `.env.example`, `config/settings.yaml`, source schemas/configuration/contracts, `data/raw/README.md`, `docs/agent_notes/README.md`, and all earlier task notes under `docs/agent_notes/`.
- The complete attached Get Insights specification.

The closest scoped instruction was applied to each file. Where requirements overlapped, the stricter security, data-integrity, provenance, and auditability rule was used. The five-dashboard, six-mandatory-question inventory was preserved unchanged; the prepared questions are separate additive UI metadata.

## 3. Files inspected

- All applicable instruction and project documentation identified above.
- `src/cepe_fynsp/schemas.py`, `config.py`, `asksage/`, `agents/rag_agent.py`, `ontology/`, every dashboard builder/support module, ETL/quality/reporting code, and relevant utilities.
- Dashboard manifests/payloads/RAG records/ontology artifacts and the static landing/dashboard HTML structure.
- `web/assets/js/dashboard_renderer.js`, all local CSS/JS assets, and all five dashboard directories.
- `scripts/`, `tests/`, `config/`, dependency declarations, CI configuration, and `data/raw/docs/`.
- The existing raw data paths were inventoried only; raw source data was not modified.

## 4. Current architecture reviewed

The baseline had five manifests with six schema-2.0 aggregate payloads each, one shared dependency-free renderer, deterministic table/chart/observation rendering, generated RAG packets, a validated graph artifact, an environment-configured low-level AskSage client, and deterministic report generation. It had no browser-to-server insights path, chart capture, approved-document index, or server endpoint.

The resulting design retains those static artifacts and adds:

1. schema-2.1 payload metadata containing one typed prepared question;
2. one shared inline-card implementation in the existing renderer;
3. native PNG chart capture in the browser;
4. a narrow same-origin Python static/API service;
5. authoritative server-side context rebuilding, filter validation, bounded graph/document retrieval, image validation, and citation enforcement;
6. the existing AskSage client as the only external API boundary.

All three actions (`summarize`, `suggested_question`, and `custom_query`) call the same `build_insight_context` pipeline.

## 5. Baseline Git state

- Branch: `main`.
- Recent commits: `02e224f`, `3189152`, `7edfc36`, `6917af0`, and `c6d4b46`.
- Pre-existing working-tree change: `notebooks/test_asksage_api.ipynb`. It was not edited, formatted, reverted, or otherwise incorporated into this task.

## 6. Baseline test and validation results

- `ruff check .`: failed with one pre-existing E402 finding in notebook cell 3.
- `ruff format --check .`: reported the pre-existing notebook, `src/cepe_fynsp/asksage/client.py`, and `tests/unit/test_asksage_client.py`; 44 files were already formatted.
- `mypy src`: passed, 30 files.
- `python -m compileall src scripts`: passed.
- `pytest`: 61 passed in 2.52 seconds.
- `python scripts/build_synthetic_ci.py`: passed with 5 dashboards, 30 payloads, 30 RAG records, and 218 graph nodes.
- `python scripts/validate_static.py`: passed for the landing page and five dashboards.

The repository virtual-environment executables were used throughout.

## 7. Current AskSage capabilities

The existing client already provided approved-host validation, environment-only configuration, direct or exchanged access tokens, bounded timeouts/retries for JSON calls, structured/redacted failures, `/server/query`, and an OpenAI-compatible chat method. This task added a validated `/server/query_with_file` multipart method. File upload is deliberately non-retrying so one file is not silently submitted multiple times.

The insights service is unavailable-safe when configuration is absent. Health information exposes only capability booleans. It does not expose credentials, configured dataset values, or the AskSage service URL.

## 8. Current RAG, ontology, payload, and frontend behavior

- Each generated payload now validates as schema 2.1 and contains strict `insights` metadata. The existing mandatory analytical question, deterministic observation, visualization specification, aggregate records, filters, quality, warnings, lineage, and graph references remain intact.
- Existing RAG artifacts still generate independently of AskSage; the synthetic build still produces 30 records.
- Existing graph generation remains unchanged. Insights resolve a separate bounded, deterministic subgraph from the validated artifact.
- The browser receives only aggregate payload data and stable evidence identifiers. It never receives raw source documents, raw controlled source rows, AskSage secrets, dataset configuration, or AskSage URLs.
- Static pages still render and filter without the service. Every chart still shows `Get Insights`; opening it reports live insights unavailable while deterministic content remains usable.

## 9. Files created or modified

### Modified

- `.env.example`
- `README.md`
- `config/settings.yaml`
- `docs/architecture/PROJECT_STRUCTURE.md`
- `pyproject.toml`
- `requirements.txt`
- `scripts/build_synthetic_ci.py`
- `scripts/validate_browser.py`
- `scripts/validate_static.py`
- `src/cepe_fynsp/asksage/client.py`
- `src/cepe_fynsp/config.py`
- `src/cepe_fynsp/dashboards/dashboard_support.py`
- `src/cepe_fynsp/schemas.py`
- `tests/integration/test_synthetic_end_to_end.py`
- `tests/unit/test_asksage_client.py`
- `web/assets/css/site.css`
- `web/assets/js/dashboard_renderer.js`
- `web/assets/js/landing.js`

### Created

- `config/approved_guidance_docs.yaml`
- `docs/agent_notes/2026-07-20_dashboard_get_insights.md`
- `docs/dependency_inventory.md`
- `scripts/index_guidance_docs.py`
- `scripts/run_insights_server.py`
- `scripts/validate_insights_browser.py`
- `src/cepe_fynsp/dashboards/insight_questions.py`
- `src/cepe_fynsp/insights/__init__.py`
- `src/cepe_fynsp/insights/context.py`
- `src/cepe_fynsp/insights/documents.py`
- `src/cepe_fynsp/insights/http_server.py`
- `src/cepe_fynsp/insights/images.py`
- `src/cepe_fynsp/insights/ontology.py`
- `src/cepe_fynsp/insights/prompt.py`
- `src/cepe_fynsp/insights/schemas.py`
- `src/cepe_fynsp/insights/service.py`
- `tests/frontend/insights_harness.html`
- `tests/frontend/insights_harness.js`
- `tests/integration/test_insights_end_to_end.py`
- `tests/unit/test_insight_documents_ontology.py`
- `tests/unit/test_insight_questions.py`
- `tests/unit/test_insight_schemas_images.py`
- `tests/unit/test_insights_frontend_contract.py`

`notebooks/test_asksage_api.ipynb` remains a pre-existing user modification and is not part of this implementation.

## 10. Data inputs found or missing

- Existing FORMEX, PLANEX, and COSTEX inputs were available to the documented pipeline. The final all-dashboard build used those existing local inputs without modifying them.
- `data/raw/docs/` contained no approved source documents beyond its placeholder. `config/approved_guidance_docs.yaml` therefore remains an empty approval allowlist, and the real index contains zero chunks.
- Tests create only synthetic aggregate rows, graph context, a synthetic approved Markdown document, and a synthetic PNG in temporary directories.
- AskSage credentials and a live approved instance were not available/used. No credential contents were inspected or logged.

## 11. Implementation summary

### Payload and schema

- Bumped the dashboard payload version from 2.0 to 2.1.
- Added strict `InsightUiConfig(enabled, suggested_question, context_version)` and made it required on every dashboard-question payload.
- Added one authoritative Python map for all 30 prepared questions and import-time inventory validation for exactly five dashboards by six questions.
- Updated producers, consumers, synthetic validation, landing code, and tests for schema 2.1.

### Frontend

- Added exactly one reusable `Get Insights` toggle beside each rendered visualization; no 30-page hand edits or second JavaScript question inventory were introduced.
- The inline card contains `Summarize Data`, the complete payload-supplied prepared question, a persistent labeled 2,000-character multiline input, `Write Your Own Query`, cancel, and close controls.
- Added `aria-expanded`, `aria-controls`, chart-specific accessible labels, live/busy status, focus on open/response, focus restoration on close, Ctrl/Cmd+Enter submission, bare-Enter preservation, responsive wrapping, visible focus, contrast, and reduced-motion styles.
- Card state is isolated per chart. `AbortController`, request sequence checks, active-request deduplication, cancellation, timeout, stale-response protection, honest unavailable states, and safe `textContent` rendering are centralized in the shared renderer.

### Secure insights service

- Added dependency-free `ThreadingHTTPServer` serving only `web/` and generated aggregate dashboard payload JSON, plus `GET /api/insights/health` and `POST /api/insights`; default bind is `127.0.0.1`.
- Added strict extra-forbid Pydantic request, response, context, citation, graph, document, image, and model-output schemas.
- The server reloads and validates the authoritative manifest/payload/graph/index, verifies dashboard/question/chart/prepared-question identity, validates every filter name/value, applies the same row semantics server-side, and prohibits submission-layer overrides.
- Context contains the mandatory/prepared question, chart metadata/specification, filtered aggregates, deterministic statistics, completeness/quality/warnings/limitations, bounded lineage, source IDs/hashes, bounded ontology, bounded approved-document chunks, and image metadata.
- Model output is schema-validated. Every accepted citation must match the server-built allowlist; canonical labels replace model labels. Unsupported or uncited output becomes `insufficient_evidence` or `upstream_error`, never a plausible answer.

## 12. Important assumptions and architectural decisions

- One shared renderer was the authoritative placement mechanism because all 30 existing sections use it.
- The browser sends identity, allowed filter state, optional custom text, and the captured image only. It does not send claimed aggregates, metrics, lineage, graph contents, or document content.
- Aggregate payload values are authoritative; image interpretation is explicitly supporting evidence and cannot override validated values.
- Client filters absent from a particular aggregate row follow the existing renderer's inclusive semantics. Unknown filter names and values are rejected rather than ignored.
- Context transmits at most 50 representative aggregate records and 250 lineage IDs while retaining full filtered counts/statistics and disclosing truncation.
- The stdlib server avoids adding a web framework for two endpoints. It is an application component, not an enterprise authentication/TLS boundary.
- Image use is operator-gated by `ASKSAGE_IMAGE_INPUT_SUPPORTED`; unverified or failed image interpretation falls back honestly to validated non-image evidence.
- The only new runtime dependency is bounded `pypdf>=5.0,<7` (BSD-3-Clause) for approval-gated local PDF extraction. Browser capture and browser testing add no runtime dependency or CDN.

## 13. Security and data-handling decisions

- AskSage access is exclusively server-side through `src/cepe_fynsp/asksage/client.py`.
- Requests reject path-like IDs, unknown fields/actions/filters/values, mismatched identities, custom questions over 2,000 characters, malformed/oversized/non-PNG images, and submission-layer overrides.
- PNGs are Base64/dimension/hash checked, decoded with Pillow, pixel/byte bounded, metadata-stripped by re-encoding, and rehashed before external use. Limits are 4 MB decoded, 4 megapixels, and 2,400 pixels per dimension; the HTTP body is limited to 6.5 MB.
- Default service limits are 30 requests/minute per client, two concurrent insight requests, approved Host headers, no permissive CORS, same-origin credentials, narrow routes, generic client errors, and metadata-only logs.
- Static GET/HEAD resolution is restricted to `web/` and `data/curated/dashboard_payloads/`. Repository configuration, local environment files, source, raw data, reports, indexes, and encoded traversal paths are not served.
- Ordinary logs contain request/chart IDs and status, not raw custom queries, prompt bodies, source rows, document passages, images, credentials, dataset values, or tokens.
- Documents are not automatically approved or uploaded. Only explicit allowlist entries below `data/raw/docs/` with `approved_for_asksage: true` may be indexed.
- Prompt instructions treat custom queries, chart labels, and retrieved documents as untrusted evidence. Documents cannot alter system behavior, request secrets, or bypass submission/data rules.
- The service performs no write-back, autonomous decisions, document mutation, or raw-data mutation. AI output is marked `unreviewed_ai_output` and requires analyst review.
- Production deployment still requires the organization's approved authentication, TLS, authorization, reverse-proxy, logging, and network controls.

## 14. AskSage API assumptions verified

- Official AskSage endpoint and OpenAPI documentation were checked. `/server/query_with_file` is multipart, accepts binary `file` parts, a JSON-encoded `message`, optional `system_prompt`, optional single-string `dataset`, model controls, and returns generated text in `message`.
- `/server/query` accepts the normal JSON query fields and permits dataset selection as a string or array.
- Official documentation reviewed:
  - `https://docs.asksage.ai/docs/v2/api-documentation/api-endpoints.html`
  - `https://docs.asksage.ai/api-docs/swagger.html`
  - `https://docs.asksage.ai/docs/v2/api-documentation/OpenAI-Compatibility-Guide.html`
- Multipart multi-dataset semantics and the configured tenant/model's image modality were not verified. The implementation therefore uses a conservative two-stage flow: optional image interpretation through `query_with_file` without dataset claims, followed by the final evidence-grounded `/server/query` with the configured approved dataset list.
- No undocumented AskSage fields were invented. No live call was made.

## 15. Image-capture approach

- The capture target is a dedicated `.visualization-capture` subtree containing chart title, metric/source metadata, warning, and the currently filtered visual. The insights card and evidence table are appended outside it and cannot enter the capture.
- The final implementation uses browser-native Canvas APIs to walk computed CSS boxes/text and render nested HTML canvas, SVG, tables, and CSS-rendered charts. It scales to at most 1,600 by 1,200, encodes PNG, and computes SHA-256 with Web Crypto.
- An initial SVG `foreignObject` snapshot approach did not paint consistently in headless Chromium. It was replaced with the explicit native drawing walker; the harness now exercises CSS, SVG, canvas, and table components.
- Capture failure is nonfatal and is disclosed to the server. The request continues using authoritative aggregate, quality, provenance, document, and graph evidence.

## 16. Document-retrieval approach

- `config/approved_guidance_docs.yaml` is an explicit data-owner/security approval manifest. Paths are resolved below `data/raw/docs/`; traversal, missing files, unsupported types, and unapproved entries fail indexing.
- PDF, DOCX, TXT, and Markdown are parsed locally. Chunks use stable source hashes/IDs, deterministic roughly 1,600-character splitting with overlap, title/type/classification, page/section metadata, and JSONL validation.
- Runtime retrieval is deterministic bounded lexical matching: at most five chunks and 12,000 characters. Chunks are cited by stable chunk/source identifiers and are never sent to the browser.
- Indexing is a separate operator command; normal requests do not scan or upload raw directories. The real approval list currently yields zero chunks; temporary synthetic indexing/retrieval passed.

## 17. Ontology-subgraph approach

- Starts with authoritative payload ontology references plus exact labels from resolved filters and bounded aggregate records.
- Validates node/edge arrays, unique node IDs, all relationship endpoints, and stable derived edge/path IDs.
- Performs deterministic cycle-safe breadth-first traversal in both relationship directions, bounded to depth 2, 40 nodes, 80 edges, and 20 paths.
- Returns complete included node/edge/path objects, stable IDs, graph ID, unavailable reason, and truncation status. The full 218-node synthetic graph is never dumped indiscriminately.

## 18. Prepared-question inventory

All 30 supplied mappings were adopted exactly; there were no wording changes.

### Dashboard 1 — `dashboard_01_pit_production`

1. Which fiscal year and funding level drives the largest change in total funding, and which programs explain that change?
2. How concentrated is funding among the top organizations, and which organization creates the greatest portfolio dependency?
3. Which sites account for most funding, and where does site concentration create the greatest execution or integration risk?
4. Which above-baseline requests contribute most to the total ask, and are the largest requests aligned with the highest priorities?
5. Which data-quality issue affects the most dollars and should be resolved first?
6. Where are Crosscut and Site Split variances largest, and are they explainable by submission-layer structure or missing data?

### Dashboard 2 — `dashboard_02_acquisition_schedule`

1. Which acquisition categories have the largest untagged or above-baseline funding exposure?
2. Which high-dollar acquisition lines combine material funding with weak descriptive or schedule evidence?
3. Which funding profiles appear misaligned with acquisition start and end dates, and what drives the misalignment?
4. Which date anomalies create the greatest uncertainty in executability analysis?
5. Which site-year combinations have the greatest LI TEC or LI OPC concentration or imbalance?
6. Which above-baseline acquisition requests are both high-dollar and high-priority but have the weakest schedule or traceability support?

### Dashboard 3 — `dashboard_03_site_capacity`

1. How much of total site funding is concentrated in the top three sites, and what does that imply for portfolio resilience?
2. Which sites show the largest cumulative funding growth or decline across FY2028–FY2032?
3. Which sites would experience the largest funding shortfall if above-baseline requests were not approved?
4. Which organization-to-site relationships create the most significant cross-organizational integration burden?
5. Which site funding surge or cliff is most material, and which programs or funding levels drive it?
6. Which missing descriptive fields most often prevent a defensible site-level review?

### Dashboard 4 — `dashboard_04_priority_challenge`

1. What share of the total ROT and UFR request is concentrated in the largest requests, and which requests dominate?
2. Which Tier 1 above-baseline requests require the strongest challenge because of amount, evidence gaps, or prioritization ambiguity?
3. Where are priorities duplicated or nonsequential, and how much funding is affected?
4. Which negative and positive requests appear related, and what evidence supports treating them as offsets, restorations, or delays?
5. Which high-dollar requests have the weakest end-to-end traceability from title through acquisition and site?
6. How much funding lacks Account Integrator decision traceability, and which organizations contribute most to the gap?

### Dashboard 5 — `dashboard_05_findings_report_generator`

1. Which accuracy finding has the highest combination of severity, financial exposure, and evidence strength?
2. Which coverage gap most limits a complete CEPE review, and what additional evidence is needed?
3. Which risk or opportunity is most material after considering likelihood, dollar exposure, and affected sites?
4. Which exhibit provides the strongest support for the highest-priority finding, and what does it demonstrate?
5. Are the most material findings supported by complete and consistent source-row, document, and ontology citations?
6. What are the three most important management conclusions and actions that the final CEPE report should contain?

## 19. Commands run

### Inspection and setup

- Instruction/source inventories with `rg --files`, targeted `rg`, and read-only PowerShell reads.
- `git status --short`, `git branch --show-current`, `git log -5 --oneline`.
- `python -m pip install -e ".[dev]"` to install the newly declared parser in the project environment.
- `python -m pip install pip-audit` because CI installs this audit tool separately and it was absent locally.

### Validation/build commands

- `ruff check .`
- `ruff format --check .`
- `ruff check src scripts tests`
- `ruff format --check src scripts tests`
- `mypy src`
- `python -m compileall src scripts`
- `pytest`
- targeted insights unit/integration tests during development
- `python scripts/build_synthetic_ci.py`
- `python scripts/run_etl.py --dashboard all`
- `python scripts/validate_static.py`
- `python scripts/validate_browser.py`
- `python scripts/validate_insights_browser.py`
- `python scripts/index_guidance_docs.py --project-root .`
- `python scripts/run_insights_server.py --help`
- a loopback secure-server smoke run against all five dashboards, allowed aggregate JSON, forbidden repository paths, and encoded traversal
- `pip-audit -r requirements.txt`
- configured tracked and untracked secret-pattern scans, filename-only
- `rg -n "https?://|//[^ /]" web`
- `git diff --check`

## 20. Exact test results

- Full final `pytest`: **86 passed in 5.25 seconds**.
- Targeted frontend contract rerun after expanding the browser harness: **3 passed in 0.01 seconds**.
- Scoped Ruff: `All checks passed!`; formatting: `64 files already formatted`.
- Full Ruff: one E402 remains only in the pre-existing `notebooks/test_asksage_api.ipynb` cell 3. Full format check reports only that notebook; all other 64 files are formatted.
- `mypy src`: `Success: no issues found in 40 source files`.
- `python -m compileall src scripts`: passed.
- Synthetic build: `5 dashboards, 30 payloads, 30 RAG records, 218 graph nodes`.
- Static validator: passed for landing and five dashboards.
- Dependency audit: `No known vulnerabilities found`; it emitted only the Windows temporary-path short-name/location warning.
- Secret-pattern scans: no matches in tracked or task-created untracked files.
- External URL/CDN scan of `web/`: no matches.
- `git diff --check`: passed; Git emitted only line-ending conversion warnings.
- Server CLI help: passed.

## 21. Browser validation performed

`scripts/validate_browser.py` used headless Chrome against the generated landing page and all five real dashboard pages:

- landing: 6 metrics, 0 errors;
- Dashboard 1: 6 ready panels, 6 visuals, 6 tables, 6 insights controls, 6 filters, 0 errors;
- Dashboard 2: 6/6/6/6 with 7 filters, 0 errors;
- Dashboard 3: 6/6/6/6 with 6 filters, 0 errors;
- Dashboard 4: 6/6/6/6 with 4 filters, 0 errors;
- Dashboard 5: 6/6/6/6 with 2 filters, 0 errors.

The mobile-width insights harness passed **25 interaction checks**, covering open/close and ARIA, prepared-question display/action, keyboard focus, blank validation, bare Enter, Ctrl+Enter, multiline/filter transmission, image success and fallback, CSS/SVG/canvas/table capture, card/table exclusion, loading, cancel, timeout, insufficient evidence, safe untrusted text, citations, response focus, independent cards, failed-panel isolation, static unavailable mode, and responsive wrapping.

The actual secure server was also started on loopback. Headless Chrome loaded every dashboard with six insights controls and no panel error markers. The aggregate landing payload returned 200, while `/.env`, `/README.md`, `/config/settings.yaml`, and encoded `/web/../.env` requests returned 404.

## 22. Validation steps performed

- Built and loaded all 30 schema-2.1 payloads and asserted the exact central question map.
- Tested all three insight actions against a mocked AskSage client using one common authoritative context builder.
- Tested synthetic approved-document indexing/retrieval and prompt-injection treatment.
- Tested filtered deterministic statistics, identity/filter/submission-layer rejection, bounded context disclosure, graph cycles/truncation/dangling references, and citation allowlisting.
- Tested PNG MIME/Base64/hash/dimension/size validation and metadata-stripping re-encode.
- Exercised health, POST, static GET, approved Host, no-CORS, rate limiting, concurrency configuration, missing credentials, upstream failures, malformed/extra model output, and redacted logging.
- Exercised the static GET/HEAD allowlist and encoded-traversal rejection against synthetic integration fixtures and the actual loopback service.
- Regenerated the five real dashboards, landing summary, RAG/graph artifacts, and Word-compatible report without AskSage.
- Verified no frontend credential markers, AskSage URLs, raw source-row additions, CDN URLs, or duplicated prepared-question inventory.

## 23. What worked

- Static/offline behavior, deterministic visuals/tables/reports, and the existing five-by-six question inventory remained intact.
- The shared renderer produced exactly 30 controls without page-specific duplication.
- Authoritative context/filter reconstruction, bounded graph and document evidence, two-stage optional image processing, citation validation, safe rendering, and unavailable fallback all passed synthetic/mocked coverage.
- Native capture works in headless Chromium for repository CSS visuals plus SVG/canvas/table test components.
- The final real-data build and dependency/security/static/browser validation succeeded.

## 24. Failures and attempted remedies / What did not work

- Full-repository Ruff cannot be clean without editing the pre-existing user notebook. That notebook remains untouched and is the sole final lint/format exception.
- The initial `foreignObject`-based capture did not paint consistently in headless Chromium; the implementation was replaced with the explicit native Canvas drawing walker.
- An early secure-static-server integration test used a temporary synthetic root that intentionally lacked `web/`; the final test supplies a purpose-built temporary `web/` and aggregate-payload tree while injecting the synthetic service.
- A final review found that the first static handler configuration could serve non-dashboard repository paths. Before handoff it was replaced with a resolved-path allowlist for `web/` and aggregate dashboard payloads, including HEAD and encoded traversal checks; synthetic integration tests and an actual loopback smoke test now confirm forbidden paths return 404.
- `pip-audit` was initially unavailable in the venv and one first invocation failed. It was installed as CI already does, then the audit passed.
- One exploratory PowerShell secret-scan expression had a quoting error. The configured CI pattern was rerun filename-only against tracked and untracked task files and found no matches.

## 25. Known limitations

- No actual AskSage instance was called. Authentication, tenant policy, live latency, live structured-output reliability, dataset access, and production quota behavior remain unverified.
- Image interpretation was exercised only with a mocked multipart response. Actual model image capability must be approved and verified before setting `ASKSAGE_IMAGE_INPUT_SUPPORTED=true`.
- Dataset retrieval was verified only as server-side environment/configuration and request construction against mocks; no live AskSage dataset retrieval was performed.
- The real approved-document list is empty. Retrieval quality was tested only with a synthetic approved document; the local lexical ranker is intentionally small and is not semantic retrieval.
- Bounded aggregate, document, and ontology context can omit detail. Responses disclose context truncation, but analysts may need drill-through review.
- The browser-native capture is a computed visual approximation and should receive human cross-browser/visual review for every production visualization technology.
- Automated keyboard/focus/mobile checks passed, but no human screen-reader or formal accessibility audit was performed.
- Rate and concurrency controls are in-memory and process-local. Production distributed deployments need controls at the approved proxy/gateway and authenticated user identity.
- The stdlib server does not provide production authentication, TLS termination, authorization, session management, persistent audit storage, or distributed rate limiting.
- The preserved generic `python -m http.server` static-preview method exposes its working directory by design. It is documented as loopback-only with no populated credential files; shared static deployment requires a sanitized approved export. The insights server itself uses the restricted static allowlist.
- AI output remains fallible, is not a decision, and always requires human review. No write-back or autonomous action exists.

## 26. Deferred work

- Live AskSage tenant/model/dataset validation, organizational document approval, production identity-aware deployment, and human accessibility/cross-browser review are deferred because they require credentials, governance decisions, deployment infrastructure, or human review not available in this checkout.
- No implementation item was knowingly deferred when it could be completed safely with local or synthetic evidence.

## 27. Recommended / suggested next steps

1. Have data owners/security personnel approve specific guidance documents, classifications, and AskSage processing eligibility before populating the approval manifest and index.
2. Configure an approved non-production AskSage tenant, validate the three dataset IDs and selected model, then run a controlled live smoke test for text and image behavior without recording sensitive prompt content.
3. Put the service behind the organization's approved identity-aware TLS reverse proxy and replace/augment process-local throttling with gateway controls.
4. Perform human visual, keyboard, screen-reader, and cross-browser review of all 30 cards and captures using representative filtered states.
5. Add the organization-required SBOM, secret, DLP, and deployment scanning beyond the included dependency/pattern checks.
