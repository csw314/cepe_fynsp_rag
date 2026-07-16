# AGENT 09 - AskSage integration notes

## Purpose

This file provides implementation guidance for integrating the project with AskSage for classification, RAG retrieval, chart summarization, and report drafting.

## Configuration

Keep the following values outside source code:

- `ASKSAGE_INSTANCE`
- `ASKSAGE_EMAIL`
- `ASKSAGE_API_KEY`
- `ASKSAGE_ACCESS_TOKEN`
- `ASKSAGE_MODEL`
- `ASKSAGE_DATASET_GUIDANCE_ID`
- `ASKSAGE_DATASET_DASHBOARD_PAYLOAD_ID`
- `ASKSAGE_DATASET_ONTOLOGY_ID`

## Recommended integration pattern

Implement one wrapper module:

- `src/cepe_fynsp/asksage/client.py`

The wrapper should provide:

- `get_access_token()`
- `query()`
- `query_with_file()` if needed
- `execute_agent()` if using AskSage agents
- `chat_completion()` if using OpenAI-compatible endpoints
- `classify_records()` for batch classification with retry and caching
- `summarize_chart()` for chart payload summaries
- `draft_report_section()` for report generation

## Dataset strategy

Create or configure separate RAG knowledge stores for:

1. Guidance/document chunks.
2. Dashboard payload summaries and metric definitions.
3. Ontology context exports.
4. Quality rules and finding definitions.

Keep source-row data minimized. For sensitive row-level retrieval, retrieve by lineage ID from the local curated data store when possible, not by uploading entire raw tables.

## Prompting rules

Agent prompts must include:

- role: CEPE program review analyst assistant
- objective: support accuracy and thoroughness review
- active dashboard ID
- active question ID
- active filters
- chart payload summary
- source lineage references
- retrieved guidance context
- ontology context
- output schema

## Response schema for chart summaries

Recommended JSON schema:

```json
{
  "answer": "string",
  "key_observations": ["string"],
  "review_triggers": ["string"],
  "limitations": ["string"],
  "citations": [
    {
      "type": "chart|metric|source_row|guidance_chunk|ontology_path",
      "id": "string"
    }
  ]
}
```

## Failure behavior

If AskSage is unavailable:

- Dashboards must still load deterministic metrics and charts.
- RAG summary panels should display a clear unavailable state.
- Pipeline should cache successful LLM outputs when allowed.
- Report generation should fall back to a deterministic outline with placeholders for analyst-written narrative.

## Official documentation references to verify during implementation

- AskSage API documentation: https://docs.asksage.ai/docs/v2/api-documentation/api-documentation.html
- AskSage REST endpoints: https://docs.asksage.ai/docs/v2/api-documentation/api-endpoints.html
- AskSage Python client: https://docs.asksage.ai/docs/v2/api-documentation/ask-sage-python-client.html
- AskSage OpenAI-compatible endpoints: https://docs.asksage.ai/docs/v2/api-documentation/OpenAI-Compatibility-Guide.html
