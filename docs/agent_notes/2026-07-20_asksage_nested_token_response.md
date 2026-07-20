# AskSage nested token-response compatibility handoff

## Task objective

Allow the project AskSage client and the API connectivity notebook to work with the organization tenant's confirmed nested token envelope, then document the API behavior and validation state for future agents.

## Files inspected

- `AGENTS.md` and `src/cepe_fynsp/asksage/AGENTS.md`
- `src/cepe_fynsp/asksage/client.py`
- `tests/unit/test_asksage_client.py`
- `notebooks/test_asksage_api.ipynb`
- `config/settings.yaml`, `.env.example`, `requirements.txt`, and `pyproject.toml`
- Current AskSage API documentation for authentication, the Server API, and the OpenAI-compatible API surface.

## Files created or modified

- Modified `src/cepe_fynsp/asksage/client.py`.
- Modified `tests/unit/test_asksage_client.py`.
- Created `docs/agent_notes/2026-07-20_asksage_nested_token_response.md`.
- `notebooks/test_asksage_api.ipynb` was created in the preceding connectivity-test task and is the caller validated by this change.

## Data inputs found or missing

- The project `.env` supplies AskSage configuration. No credential values, tokens, email addresses, or raw response bodies are recorded here.
- The organization tenant returned a successful token response with the aggregate shape `{"response": {"access_token": "<redacted>"}, "status": "200"}`.
- The HTTP client process used for this handoff could not validate the organization's TLS interception/root certificate chain. A CA-bundle path or trusted corporate root was not available to that process.

## Implementation summary

`AskSageClient.get_access_token()` now accepts the following token locations, in precedence order:

1. Top-level `access_token`.
2. Top-level `token`.
3. Nested `response.access_token`.
4. Nested `response.token`.

The nested lookup is attempted only when `response` is a JSON object. This keeps the existing rejection of malformed responses and avoids treating an arbitrary response string as a credential. The existing caching, retry, timeout, host allowlist, and redacted-error behavior are unchanged.

An automated unit test verifies that the confirmed `response.access_token` envelope returns a usable token and is cached without a second token-exchange request.

## AskSage API details

- Keep all low-level HTTP calls in `src/cepe_fynsp/asksage/client.py`; notebooks and agents should use `AskSageClient` rather than creating independent `requests` clients.
- Configuration comes from environment variables: `ASKSAGE_INSTANCE`, `ASKSAGE_APPROVED_HOSTS`, `ASKSAGE_EMAIL`, `ASKSAGE_API_KEY`, optional `ASKSAGE_ACCESS_TOKEN`, `ASKSAGE_MODEL`, and timeout/retry settings. Never log or commit their values.
- The token-exchange call is `POST https://api.<approved-instance>/user/get-token-with-api-key` with email and API key. This tenant's success envelope nests the token under `response.access_token`; do not assume all AskSage tenants use the same envelope.
- The notebook uses `POST /server/get-models` with `x-access-tokens` to enumerate models. AskSage may return model names/metadata without modality fields; display `not reported by AskSage` instead of inferring image, audio, or other capability from the model name.
- The project OpenAI-compatible chat request is `POST /server/openai/v1/chat/completions` with `Authorization: Bearer <access-token>`. The notebook sends one short text-only prompt after the model-list request succeeds.
- Official documentation: https://docs.asksage.ai/docs/v2/api-documentation/api-endpoints.html and https://docs.asksage.ai/docs/v2/api-documentation/OpenAI-Compatibility-Guide.html.

## Important assumptions

- `response.access_token` is a bearer token because the confirmed response reported HTTP success and the account diagnostic identified that field as a string. No token value was examined or recorded.
- A nested `expires_in` field was not observed. The client retains its existing 900-second default cache lifetime when no top-level `expires_in` is supplied.
- Direct `ASKSAGE_ACCESS_TOKEN`, when approved and supplied, still takes precedence over exchanging the email/API-key pair.

## Commands run

- `& .\\.venv\\Scripts\\python.exe -m pytest tests/unit/test_asksage_client.py -q`
- `& .\\.venv\\Scripts\\python.exe -m pytest -q`
- `& .\\.venv\\Scripts\\python.exe -m ruff check src/cepe_fynsp/asksage/client.py tests/unit/test_asksage_client.py`
- Direct execution of all notebook code cells with the project virtual environment (Jupyter and nbformat are not installed in that virtual environment).
- Standard-library JSON and Python compilation validation for the notebook.

## Test results, including failures

- Passed: AskSage unit tests, 10 passed.
- Passed: full project test suite, 61 passed.
- Passed: Ruff checks for the modified client and unit test.
- Passed: unit coverage for the confirmed nested token envelope and its cache behavior.
- Passed: notebook JSON and Python code-cell compilation validation.
- Failed only in this handoff process: live notebook execution was stopped by `SSLCertVerificationError` before the token request could reach the service. The error reported a self-signed certificate in the TLS chain. Certificate verification was not disabled.

## Validation steps performed

- Confirmed the user-run diagnostic response had `status` `200`, a `response` object, and a string `response.access_token` field without printing the token.
- Verified top-level-token behavior remains covered by the existing token-exchange/chat test.
- Verified nested-token behavior returns the expected synthetic token and avoids a second exchange request.
- Confirmed the notebook calls `AskSageClient.get_access_token()`, so it automatically uses the new fallback with no notebook code change.

## What worked

- The organization tenant's token endpoint accepted the configured credentials and returned a nested access token in the user's interactive notebook environment.
- The bounded client change handles both the historical top-level shape and the confirmed organization-specific nested shape.
- Existing TLS, host allowlist, response validation, and secret-redaction safeguards were preserved.

## What did not work

- The project virtual environment used by the handoff agent does not trust the local TLS interception/root certificate, so it could not independently complete the live model-list and prompt calls.
- Jupyter/nbformat are not installed in that virtual environment, so the notebook was executed by compiling and running its cells directly rather than with `jupyter nbconvert`.

## Known limitations

- A successful token exchange in the user's notebook does not guarantee that `/server/get-models` and `/server/openai/v1/chat/completions` are authorized for the account; run the notebook through its final cell in the trusted user environment to confirm both.
- The AskSage model-list response does not reliably publish modality metadata. The notebook intentionally does not guess capabilities.
- The client does not read an expiry nested below `response`; it uses the existing default lifetime unless the top-level API response supplies `expires_in`.

## Suggested next steps

1. Run `test_asksage_api.ipynb` from the user's established Jupyter kernel and confirm the model list and short text response complete.
2. Configure the project runtime with the approved corporate CA bundle or root-certificate trust path so non-notebook Python executions validate TLS without bypassing verification.
3. If the tenant adds a nested expiry field, add a test and parse it deliberately rather than increasing the default cache duration.
4. If API payload shapes change again, capture only status codes, JSON key names, and value types; do not print tokens, credentials, headers, or raw error bodies.
