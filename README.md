# CEPE FYNSP 2028 Program Review Dashboard Suite

This project builds one static executive landing page and five question-oriented dashboards for CEPE review of FY2028–FY2032 programming. Python performs typed ingestion, normalization, contract and quality validation, lineage, ontology/RAG export, findings synthesis, and deterministic report generation. The browser receives aggregate-only JSON and local HTML/CSS/JavaScript; it does not receive raw rows, credentials, or an internet dependency.

The default exemplar integration area is Pit Production.

## Current source files

Place immutable exports at the configured paths:

- FORMEX: `data/raw/formex/CSV Download.csv` — UTF-16, tab-delimited, overlapping submission views.
- PLANEX: `data/raw/planex/idw_planex_202607171050.csv` — comma-delimited FY2026 execution-plan context.
- COSTEX: `data/raw/costex/idw_costex_202607171052.csv` — comma-delimited FY2023–FY2026 cost context.

The names are configurable in `config/settings.yaml`. Source contracts are executable YAML under `config/data_contracts/`. Raw files are ignored by Git and are never overwritten.

FORMEX layers are not additive. Federal Crosscuts support portfolio totals, Federal Site Splits support site analysis, GPRA Constraints support GPRA checks, and Federal STAT Table supports hierarchy review. PLANEX and COSTEX are not presented as a direct reconciliation to FY2028–FY2032 FORMEX without an approved crosswalk.

## Install

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Runtime dependencies are bounded in `pyproject.toml` and mirrored in `requirements.txt`; development dependencies are in the `dev` extra and notebook tooling is isolated in the `notebook` extra. No private editable Git dependency is required.

`pip-system-certs` is included so a newly created virtual environment uses the operating
system certificate store for Requests/urllib3. This is required in environments where the
approved AskSage connection is issued or inspected by an organization-managed CA. Restart
Python after installation so its certificate startup hook takes effect. Certificate
verification is never disabled; an explicitly approved PEM override can instead be supplied
through `REQUESTS_CA_BUNDLE` when required by organizational PKI guidance.

## Build

Run the scalable source-ingestion path and the complete product build:

```powershell
.\.venv\Scripts\python.exe scripts\run_etl.py --ingest-sources --dashboard all
```

The large PLANEX and COSTEX files are read through DuckDB and written as normalized Parquet instead of being loaded wholesale into pandas. The command also creates:

- versioned dashboard payloads and manifests under `data/curated/dashboard_payloads/`;
- source-health and normalized source artifacts under `data/curated/source_profiles/` and `data/interim/`;
- validated RAG JSONL under `data/curated/rag_chunks/`;
- graph JSON and JSON-LD under `data/ontology/`;
- a generated landing summary;
- a deterministic DOCX, HTML companion, seven PNG exhibits, and citation manifest under `data/reports/`.

Use `--dashboard 01` through `--dashboard 05` for a bounded dashboard build. The landing summary and management report are generated after Dashboard 5 or a complete build.

Serve the repository root so both `web/` and generated `data/` paths are available:

```powershell
.\.venv\Scripts\python.exe -m http.server 8000
```

Then open `http://localhost:8000/web/`. The static UI works offline and provides deterministic data health, accessible visualizations, aggregate-only filters, cross-filters, traceability, full searchable/sortable/paginated evidence tables, and filtered aggregate CSV export.

## Validate

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe src
.\.venv\Scripts\python.exe -m compileall -q src scripts
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\build_synthetic_ci.py
.\.venv\Scripts\python.exe scripts\validate_static.py
```

The synthetic CI build creates all five dashboards and the report in a temporary directory; it does not require controlled source data. The static validator checks the mandatory question inventory, local-only assets, navigation/accessibility scaffolding, renderer acceptance behaviors, credential markers, and raw-data Git policy.

## AskSage

AskSage is optional and never blocks ETL, dashboards, or reporting. If enabled, use
`.env.example` as a names-only template and provide values through the organization's approved
environment/secret-injection method. Direct Python entry points do not automatically load a
local `.env` file; the Windows launcher described below explicitly loads only approved runtime
names. Keep all calls behind
`src/cepe_fynsp/asksage/client.py`; never put credentials in browser JavaScript or committed
configuration. Generated RAG records remain evidence-bounded and cite payload, source,
lineage, and ontology identifiers.

### Get Insights operating modes

Static-only operation is unchanged:

```powershell
.\.venv\Scripts\python.exe -m http.server 8000 --bind 127.0.0.1
```

All dashboard charts, filters, evidence tables, deterministic observations, exports, reports, and traceability remain usable offline. Every visualization still displays **Get Insights**; opening it reports that live insights are unavailable when the same-origin service is absent. Browser code never calls AskSage directly.

The generic Python server exposes its working directory by design. Use it only as a loopback
development/static preview, do not keep populated credential files in the served tree, and use
an approved sanitized static export for shared hosting. The restricted secure-insights server
below is the local option when the process has AskSage credentials.

Secure-insights operation serves only `web/`, generated aggregate JSON below
`data/curated/dashboard_payloads/`, and the narrowly scoped API from one origin. Other
repository files, including local environment/configuration files, are not static routes:

```powershell
.\scripts\start_insights.ps1
```

That single command safely parses the local `.env` without executing it, loads only approved
AskSage/certificate names, enables approved PNG input for the server run, validates all five
dashboard artifact sets, prints boolean readiness status without values, and starts the
loopback server. It restores the shell's earlier environment after the server stops. Use
`.\scripts\start_insights.ps1 -ValidateOnly` for a non-network startup check, or add
`-Port 8010` when the default port is already occupied. The direct Python server command
remains available for managed deployments where an approved secret injector has already
configured the process environment.

Open `http://127.0.0.1:8000/web/`. The default bind is loopback-only. Production use must sit behind the organization's approved authentication, TLS, host validation, reverse proxy, audit, and access-control boundary. Add a proxy hostname only with the repeatable `--allowed-host` argument. The service does not enable cross-origin access.

Required/optional environment variable names are listed in `.env.example`:

- `ASKSAGE_INSTANCE`, `ASKSAGE_APPROVED_HOSTS`, `ASKSAGE_EMAIL`, `ASKSAGE_API_KEY`, `ASKSAGE_ACCESS_TOKEN`, and `ASKSAGE_MODEL`.
- `ASKSAGE_DATASET_GUIDANCE_ID`, `ASKSAGE_DATASET_DASHBOARD_PAYLOAD_ID`, and `ASKSAGE_DATASET_ONTOLOGY_ID` for approved existing datasets.
- `ASKSAGE_IMAGE_INPUT_SUPPORTED`, which must remain `false` until the selected tenant model is approved and verified for PNG interpretation.
- AskSage connection/read timeout and bounded retry settings shown in `.env.example`.

The request flow is:

```text
Browser visualization
  -> strict same-origin insight request
  -> authoritative payload reload and filter reproduction
  -> bounded ontology-subgraph retrieval
  -> bounded approved-document retrieval
  -> secure PNG validation/re-encoding
  -> AskSage client (optional image interpretation, then grounded synthesis)
  -> strict model/output/citation validation
  -> safe plain-text browser rendering
```

The numeric aggregate payload is authoritative. A chart image is supporting context only. The server rejects unknown identities, filter names/values, submission-layer overrides, extra schema fields, oversized queries/requests, malformed images, and model citations outside the supplied evidence inventory. It logs request IDs and statuses, not custom queries, prompts, document passages, source rows, credentials, or raw request bodies. The browser receives neither raw documents nor raw source rows.

AskSage must return one strict JSON response. The service accepts exact JSON and the common case
of exactly one JSON Markdown fence, while rejecting prose wrappers or partially recoverable text.
If JSON or field validation fails, the service logs only content-free metadata such as the failing
field path and validation type, then makes one bounded regeneration request using the same
evidence and stricter formatting instructions. The regenerated response must still pass the full
schema and citation allowlist. Operators can reproduce this check without printing model content:

```powershell
.\.venv\Scripts\python.exe scripts\diagnose_insights_response.py --project-root . --dashboard-id dashboard_01_pit_production --question-id q1
```

### Approved guidance indexing

Documents under `data/raw/docs/` are not automatically approved or uploaded. A data owner/security reviewer must add an explicit entry to `config/approved_guidance_docs.yaml`, set `approved_for_asksage: true`, and supply classification metadata. Build the local derived index separately from dashboard runtime:

```powershell
.\.venv\Scripts\python.exe scripts\index_guidance_docs.py --project-root .
```

The indexer supports PDF, DOCX, PPTX, UTF-8 TXT, and Markdown, with stable
hashes/chunk IDs, page/slide/section citations where available, and immutable raw inputs.
PPTX extraction reads visible slide text, including text boxes and table text represented in
the slide XML; speaker notes and embedded image OCR are not extracted. Normal insight
requests retrieve only a bounded relevant subset and never create datasets or upload the
document directory. An empty or fully disabled approval manifest is valid and produces no
document context.

Newly discovered documents may be scaffolded in the manifest with
`approved_for_asksage: false` and `classification: pending_data_owner_review`. Before
indexing them, a data owner/security reviewer must replace that placeholder with the approved
classification marking and explicitly set `approved_for_asksage: true` for each authorized
file. Files left disabled are skipped.

### Insights limitations and review requirement

- AskSage availability, tenant authorization, dataset access, and selected-model image capability are deployment dependencies and were not assumed from model names.
- The verified AskSage multipart contract does not establish multi-dataset semantics for `query_with_file`; image-enabled requests therefore use a two-stage server-side path, then apply configured datasets to final grounded synthesis.
- Aggregate rows, ontology nodes/edges/paths, document chunks, lineage IDs, prompt size, request size, concurrency, and request rate are bounded. Truncation is disclosed.
- Ontology retrieval returns a relevant validated subgraph, not the entire graph. Local document retrieval is deterministic lexical matching, not a guarantee of semantic completeness.
- AI output is fallible, marked **AI-generated—review required**, has no write-back/autonomous action path, and must not be treated as an adjudication or management decision.
- Funding evidence alone cannot establish site or acquisition executability. Insufficient or invalidly cited model output is not accepted as an answer.

## Dashboard inventory

1. Pit Production Accuracy and Thoroughness Overview
2. Acquisition and Schedule Executability Monitor
3. Site Capacity and Integration Burden Dashboard
4. Priority, Tier, and Program Request Challenge Board
5. CEPE Findings, Evidence, and Report Generator

Each dashboard preserves the six natural-language questions defined in `docs/agents/AGENT_03_DASHBOARD_OBJECTIVES.md`.
