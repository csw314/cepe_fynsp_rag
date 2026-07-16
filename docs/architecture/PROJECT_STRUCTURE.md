# Recommended project structure

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
