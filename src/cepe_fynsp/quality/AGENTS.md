# AGENTS.md - quality scope

Quality checks must be explainable and reproducible.

- Implement each rule as a separate function or rule object.
- Include rule ID, severity, affected dollars, affected rows, and drill-through row IDs.
- Do not use LLMs for deterministic checks.
- LLM classification may enrich quality results only after deterministic checks run.
- Reconciliation checks must state left source, right source, join keys, filters, and variance.
