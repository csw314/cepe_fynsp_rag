# AskSage runtime trust and grounded-schema handoff

## Task objective

Make the working system-certificate integration reproducible through project dependencies, then diagnose and safely harden the grounded AskSage response boundary without logging model content, prompts, credentials, or document passages.

## Files inspected

- `pyproject.toml`, `requirements.txt`, `.env.example`, and `docs/dependency_inventory.md`
- `README.md`
- `src/cepe_fynsp/asksage/client.py`
- `src/cepe_fynsp/insights/service.py`, `prompt.py`, and `schemas.py`
- Existing AskSage and insights unit/integration tests
- Package metadata for the working notebook and project virtual environments; no credential values were read or printed.

## Files created or modified

- Created `docs/agent_notes/2026-07-20_asksage_runtime_schema_diagnosis.md`.
- Created `scripts/diagnose_insights_response.py`.
- Modified `pyproject.toml` and `requirements.txt`.
- Modified `.env.example`, `README.md`, `docs/dependency_inventory.md`, and `docs/architecture/PROJECT_STRUCTURE.md`.
- Modified `src/cepe_fynsp/insights/service.py` and `prompt.py`.
- Modified `tests/integration/test_insights_end_to_end.py`.

## Data inputs found or missing

- Local dashboard payload, ontology, and approved-document context are available according to the user's health response.
- A raw live AskSage completion was not supplied and will not be logged or copied into this note.

## Implementation summary

- Added bounded runtime dependency `pip-system-certs>=5.3,<6` to both dependency declarations. Version 5.3 is the working installed version and uses a startup hook plus pip's Truststore integration to use the OS certificate store.
- Documented its BSD-3-Clause license, startup behavior, trust boundary, and optional `REQUESTS_CA_BUNDLE` override. Certificate verification is never disabled.
- Advanced the grounded prompt version to `cepe_dashboard_insights_v2` and made the exact top-level/citation field requirements explicit.
- Added strict model-output parsing that accepts either exact JSON or exactly one JSON Markdown fence. Prose wrappers and partial JSON recovery remain rejected.
- Added content-free rejection diagnostics: attempt, stage, message length, fence presence, and bounded Pydantic field/type issues. Rejected answer text and inputs are never logged.
- Added one bounded schema-regeneration request using the same evidence and a stricter formatting instruction. The result must still pass the exact model schema and citation allowlist; no semantic or citation control is relaxed.
- Added a content-free live diagnostic command that prints only response status, request ID, and citation/limitation counts.

## Important assumptions

- `pip-system-certs` 5.3 is the approved working mechanism because it is already installed in the successful notebook environment and project venv, and the user confirmed token exchange succeeds.
- Model content is potentially sensitive and untrusted. Diagnosis will retain only response envelope types, lengths/hashes, and Pydantic error locations/types.

## Commands run

- Read-only inspection of dependency declarations, environment template, documentation, service/prompt/schema code, and existing tests.
- Read-only PyPI metadata verification for `pip-system-certs` 5.3.
- Targeted AskSage/insights tests during development.
- Three live image-free Dashboard 1 Question 1 structural diagnostics; only metadata/status was printed.
- `python -m pip install -e ".[dev]"`
- `python -m pytest`
- `ruff check src scripts tests`
- `ruff format --check src scripts tests`
- `mypy src`
- `python -m compileall src scripts`
- `python scripts/build_synthetic_ci.py`
- `python scripts/validate_static.py`
- `python scripts/validate_insights_browser.py`
- `python -m pip check`
- `pip-audit -r requirements.txt`
- `ruff check .` and `ruff format --check .`
- `git diff --check`

## Test results, including failures

- Initial targeted AskSage/insights set: 20 passed in 2.59 seconds.
- Initial format check requested formatting for the new diagnostic script; Ruff formatting resolved it.
- Schema-regeneration integration module: 10 passed in 2.47 seconds.
- Final full suite: 89 passed in 4.60 seconds.
- Scoped Ruff lint passed; all 65 scoped files are formatted.
- Mypy passed with no issues in 40 source files; compileall passed.
- Editable development installation succeeded and resolved `pip-system-certs` 5.3 from the declared project dependency.
- `pip check`: no broken requirements.
- Dependency audit: no known vulnerabilities; only the established Windows temporary-path warning.
- Synthetic build passed with 5 dashboards, 30 payloads, 30 RAG records, and 218 graph nodes.
- Static validation and all 25 insights browser interaction checks passed.
- Full Ruff still reports only the pre-existing notebook E402/format issue; the notebook was not changed. All other 65 scoped files are formatted.
- `git diff --check` passed with line-ending conversion warnings only.
- First post-parser live diagnostic returned `answered`; the original rejected response was already unavailable and could not be examined.
- Instrumented live diagnostic returned valid exact JSON with no Markdown fence.
- Final live diagnostic reproduced an initial schema rejection with the sole issue `citations.0.type:missing`. The bounded regeneration returned valid exact JSON, passed the citation allowlist, and produced `answered` with one citation.

## Validation steps performed

- Confirmed current final synthesis expects `payload["message"]` to be a nonblank string containing one strict JSON object.
- Confirmed multiple distinct failures currently collapse to the same browser-safe message.
- Confirmed exact fenced JSON is accepted while prose-prefixed JSON and extra fields are rejected.
- Confirmed diagnostics contain field/type metadata but not rejected field values.
- Confirmed one initial structural failure triggers exactly one regeneration and that valid regenerated output is accepted.
- Confirmed persistent malformed or uncited output remains rejected.
- Confirmed a live missing citation `type` is now diagnosed and safely regenerated without recording model content.

## What worked

- User-confirmed token exchange now succeeds with system certificate integration and the configured CA bundle.
- Local insights health reports payload, document, and ontology context available.
- The declared certificate dependency installs through the normal project command and matches the working environment.
- Live token exchange and final query both succeeded.
- Content-free diagnostics identified a concrete model defect, and bounded regeneration recovered while preserving strict citation validation.

## What did not work

- The original rejected completion was not retained, so its precise defect cannot be proven retroactively. This is an intentional privacy property.
- A later live request reproduced the same class of problem: the model omitted `type` from its first citation. The first response was correctly rejected.
- The initial new diagnostic script required Ruff formatting; formatting resolved it.

## Known limitations

- Model output remains nondeterministic and can still fail both the initial and single regeneration attempt.
- Regeneration adds one AskSage call, latency, and usage only when structural parsing fails.
- Structural diagnostics deliberately cannot reconstruct answer content or explain why the model omitted a field.
- `pip-system-certs` trusts CAs already governed by the operating system; it does not install organizational certificates. Its `.pth` startup hook requires a new Python process and does not apply to PyInstaller-style bundled applications.
- No live model output is persisted in source control or ordinary logs.

## Suggested next steps

1. Restart the secure insights server after installing/updating dependencies so the system-certificate startup hook and prompt v2 are active.
2. Monitor only the new `stage` and `issues` metadata when a response is rejected; do not add raw-response logging.
3. If a specific field omission recurs frequently after regeneration, evaluate a narrowly scoped canonicalization only when the server can resolve it uniquely from the citation allowlist.
