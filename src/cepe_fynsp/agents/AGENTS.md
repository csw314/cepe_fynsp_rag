# AGENTS.md - agent orchestration scope

Agent orchestration should bind dashboard context, ontology context, and retrieved evidence.

- Define prompt templates in versioned files or constants.
- Require structured outputs for classification and summaries.
- Store LLM outputs with prompt version, model, timestamp, input IDs, and review status.
- Do not let the agent invent chart data; pass chart payloads explicitly.
