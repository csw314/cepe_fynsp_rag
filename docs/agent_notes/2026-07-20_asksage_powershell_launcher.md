# AskSage PowerShell launcher handoff

## 1. Task objective

Provide one short PowerShell command that safely loads approved AskSage settings from the
local `.env`, enables approved PNG input, reports only non-secret readiness status, and starts
the restricted same-origin dashboard and Get Insights server.

## 2. Files inspected

- Root `AGENTS.md`, all nine `docs/agents/AGENT_*.md` guides, every scoped `AGENTS.md`,
  `.gitignore`, `.env.example`, `README.md`, `pyproject.toml`, and `requirements.txt`.
- `scripts/run_insights_server.py`, AskSage environment loading, insights health/configuration,
  generated dashboard artifact locations, and existing insights integration tests.

## 3. Files created or modified

- Created `scripts/start_insights.ps1`.
- Created `tests/integration/test_start_insights_launcher.py`.
- Modified `.env.example`, `README.md`, and `docs/architecture/PROJECT_STRUCTURE.md`.
- Created and maintained this handoff note throughout the task.

## 4. Data inputs found or missing

- The local `.env` exists but its values were not printed or copied into this note.
- All five generated dashboard payload directories, ontology artifacts, and the approved
  document index are present locally.
- No raw CSV rows or document text are required or inspected for this launcher task.

## 5. Implementation summary

- Added one loopback-only foreground launcher whose default invocation is
  `.\scripts\start_insights.ps1`.
- The launcher reads `.env` as data rather than evaluating it, imports only an explicit
  AskSage/certificate allowlist, accepts quoted values and optional `export`, clears inherited
  values when an approved local name is explicitly blank, and ignores unapproved names.
- It asserts `ASKSAGE_IMAGE_INPUT_SUPPORTED=true` for the launched server, carries forward an
  available `SSL_CERT_FILE` as `REQUESTS_CA_BUNDLE`, validates configured bundle existence,
  and never disables TLS verification.
- It accepts either a direct access token or the email/API-key pair, validates the venv/server,
  five dashboard pages, and five payload directories, then reports boolean readiness only.
- It starts the existing restricted `run_insights_server.py` on `127.0.0.1`, supports `-Port`
  and `-ValidateOnly`, and restores the calling PowerShell process's original approved
  environment values after validation or server shutdown.
- Added Windows-only integration coverage with a synthetic project and synthetic credentials;
  tests verify success, incomplete-auth failure, image override, allowlist behavior, literal
  handling of command-like `.env` content, and absence of credential values in output.

## 6. Important assumptions

- The user's request to enable image support confirms approval for the selected tenant/model;
  the launcher flag remains an operator assertion rather than automatic capability detection.
- Startup should serve existing generated artifacts and should not rebuild or mutate raw data.
- The service remains loopback-only and foregrounded so Ctrl+C stops it normally.

## 7. Commands run

- Inventoried every `AGENTS.md`, `AGENT.md`, and `docs/agents/AGENT_*.md` file with `rg`.
- Read every inventoried instruction file completely with PowerShell `Get-Content -Raw`.
- Searched launcher, `.env`, certificate, server, test, and documentation references with `rg`.
- Inspected generated dashboard and ontology artifact inventories with read-only PowerShell.
- Inspected the working tree with `git status --short` before editing; it was clean.
- Parsed `scripts/start_insights.ps1` with PowerShell's language parser.
- Ran `.\scripts\start_insights.ps1 -ValidateOnly` against the real local configuration; all
  startup readiness checks passed without printing values or contacting AskSage.
- Ran the launcher on temporary loopback port 8765, requested `/web/` and
  `/api/insights/health`, then stopped it with Ctrl+C.
- Ran validation-only startup in the same PowerShell process with a harmless sentinel to
  confirm the prior image environment value was restored.
- Ran focused and full pytest, scoped Ruff lint/format checks, mypy, compileall, the synthetic
  build, static and browser validators, `pip check`, PowerShell parser validation, and
  `git diff --check`.
- Ran repository-wide Ruff lint/format checks to identify pre-existing out-of-scope issues.

## 8. Test results, including failures

- Focused launcher integration tests passed: 3 tests.
- Full pytest passed: 92 tests in 6.51 seconds.
- Scoped Ruff lint and format checks passed for `scripts` and `tests`.
- Mypy passed with no issues in 40 source files; compileall passed.
- Synthetic build passed with 5 dashboards, 30 payloads, 30 RAG records, and 218 graph nodes.
- Static offline validation passed for the landing page and five dashboards.
- Insights browser validation passed 25 interaction checks; general browser validation loaded
  the landing page and all five six-panel dashboards with no reported rendering errors.
- `pip check` reported no broken requirements. PowerShell parser and `git diff --check` passed;
  the latter printed only Git's existing LF-to-CRLF working-copy warnings.
- Live landing page returned HTTP 200. Live health reported service, AskSage, image input,
  document context, and ontology context available.
- Stopping the PTY-hosted live test with Ctrl+C produced the expected external-interrupt exit
  code 1 and no error output; this was an intentional test shutdown, not a server failure.
- Repository-wide `ruff check .` still reports only the pre-existing E402 in cell 3 of
  `notebooks/test_asksage_api.ipynb`; repository-wide format check likewise reports only that
  notebook. The notebook was unchanged because it is unrelated user work.

## 9. Validation steps performed

- Confirmed direct `run_insights_server.py` does not load `.env` automatically.
- Confirmed AskSage configuration and image capability are read from process environment.
- Confirmed `.env` is ignored by Git and the secure server does not expose the repository root.
- Confirmed no credential values appeared in focused test, validation, or live-server output.
- Confirmed the caller's preexisting process environment is restored after validation.
- Confirmed an explicitly blank local access token clears an inherited token so the intended
  email/API-key authentication path is deterministic.

## 10. What worked

- One short command now loads the approved environment, enables images, validates all five
  dashboards, and starts the existing combined dashboard/API service.
- Both supported authentication shapes and certificate fallback behavior remain compatible
  with the existing Python client.

## 11. What did not work

- No implementation or assertion failure has occurred. The intentional Ctrl+C used to stop the
  temporary live server is reported in the test-results section.

## 12. Known limitations

- The launcher is Windows PowerShell-specific by user request.
- The launcher serves existing generated artifacts; it does not rebuild raw/curated data or
  re-index guidance at every startup.
- Image enablement is an operator assertion. The health endpoint confirms that the feature is
  enabled, not that every selected AskSage model will interpret every PNG correctly.
- Windows execution policy remains controlled by the host organization; the project does not
  weaken or bypass it in the documented operator command.

## 13. Suggested next steps

- Use `.\scripts\start_insights.ps1` for normal local operation and Ctrl+C for shutdown.
- Use `-ValidateOnly` after credential, certificate, model, or generated-artifact changes.
- If deployment moves beyond loopback, retain the direct Python entry point behind the approved
  authentication, TLS, reverse-proxy, host-validation, and secret-injection boundary.
