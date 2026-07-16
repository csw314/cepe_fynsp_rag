# AGENT 08 - security, governance, and operational guardrails

## Purpose

This file sets project-level security and governance instructions.

## Data handling

- Treat raw FYNSP programming data and guidance documents as controlled internal material unless explicitly cleared.
- Do not commit raw data to public repositories.
- Do not upload raw data to external systems unless approved by the data owner and security authority.
- Use only the approved AskSage instance for the operating environment.
- Avoid writing source rows into logs.
- Avoid storing prompt transcripts that include sensitive row-level data unless logging is approved.

## Secrets

- No API keys in source code.
- No `.env` files in git.
- Use environment variables or approved secret storage.
- Rotate keys according to organizational policy.

## LLM governance

- Treat LLM classifications as analytic aids, not authoritative facts.
- Persist prompt version, model, timestamp, and input lineage for LLM outputs.
- Include human-review status for material LLM-derived findings.
- RAG responses must cite retrieved evidence.
- Report generation must include citation manifests.

## Deployment

- Prefer internal static hosting for `web/` artifacts.
- Prefer local vendored JavaScript libraries or approved internal package/CDN mirrors.
- Do not rely on internet access from production dashboards.
- Disable write actions from the dashboard unless specifically approved.

## Auditability

Each generated dashboard payload should include:

- build timestamp
- git commit if available
- pipeline version
- source file names and hashes
- filters applied
- metric definitions
- row lineage references
- quality-rule versions
