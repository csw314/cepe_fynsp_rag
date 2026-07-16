# AGENTS.md - AskSage scope

This directory is the only place where low-level AskSage API calls should live.

- No secrets in code.
- Read base URL, token, model, and dataset IDs from config/environment.
- Implement retries, timeouts, and structured errors.
- Keep prompt construction outside the low-level HTTP client when practical.
- Log request IDs and prompt versions, not sensitive source-row text.
