# Implemented project structure

```text
cepe-fynsp-dashboard/
  AGENTS.md
  README.md
  pyproject.toml
  .env.example
  config/
    settings.yaml
    dashboards.yaml
    data_contracts/
      formex.yaml
      planex.yaml
      costex.yaml
  data/
    raw/
      formex/
      planex/
      costex/
      docs/
    interim/
    curated/
      dashboard_payloads/
      rag_chunks/
    ontology/
    reports/
      html/
      docx/
  docs/
    agents/
    architecture/
    data_dictionary/
  notebooks/
  scripts/
  src/cepe_fynsp/
    etl/
    quality/
    ontology/
    asksage/
    agents/
    insights/
    dashboards/
    reporting/
    utils/
  tests/
  web/
    index.html
    assets/
      css/
      js/
      img/
    dashboards/
      01_overview/
      02_acquisition/
      03_site_capacity/
      04_priority_challenge/
      05_findings_report_generator/
```

## Intent by layer

- `data/raw`: immutable source files.
- `data/interim`: normalized datasets such as Parquet outputs.
- `data/curated`: analytics-ready datasets, dashboard JSON, RAG chunks, and lineage manifests.
- `data/ontology`: graph exports in JSON-LD, Turtle, or graph JSON.
- `web`: static HTML dashboard interface.
- `src/cepe_fynsp`: reusable Python package.
- `docs/agents`: agent guidance for Codex or other coding assistants.

## Runtime flow

1. `etl/contracts.py` validates raw headers and domains against versioned YAML contracts.
2. `etl/pipeline.py` writes stable-lineage normalized Parquet. FORMEX uses its encoding-aware loader; large PLANEX/COSTEX exports use DuckDB streaming/columnar processing.
3. Dashboard modules calculate question-specific aggregate evidence. `dashboard_support.py` validates schema-v2.1 payloads, including one typed prepared insight question per visualization, and atomically writes manifests, RAG packets, graph JSON, and JSON-LD.
4. `web/assets/js/dashboard_renderer.js` renders only aggregate payloads with local dependency-free components. One failed question is isolated from the remaining panels. The shared renderer also mounts one same-origin Get Insights card per question; static rendering does not depend on the service.
5. `insights/` reloads authoritative payloads, reproduces allowed filters, resolves bounded graph/document context, validates chart captures, constructs versioned prompts, validates AskSage output/citations, and exposes browser-safe response models. Strict model parsing emits content-free structural diagnostics and permits one bounded schema-regeneration attempt without relaxing the citation allowlist. `scripts/run_insights_server.py` combines the API with allowlisted static serving for `web/` and generated aggregate dashboard payloads on one origin; `scripts/diagnose_insights_response.py` provides a content-free live structure check; neither exposes the repository root.
6. Dashboard 5 creates the read-only finding register/evidence manifest. `reporting/generator.py` validates all inputs and writes the deterministic DOCX/HTML/exhibit/citation set.

All generated data, ontology, and report outputs remain ignored. CI uses `scripts/build_synthetic_ci.py` so validation does not depend on controlled raw files.
