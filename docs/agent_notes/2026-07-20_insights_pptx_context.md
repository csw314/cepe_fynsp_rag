# PPTX guidance-context support handoff

## Task objective

Support locally added PowerPoint guidance as bounded, approval-gated Get Insights context and clarify the runtime configuration required to launch the dashboard securely.

## Files inspected

- `config/settings.yaml`
- `config/approved_guidance_docs.yaml`
- `.env.example`
- `.gitignore`
- `src/cepe_fynsp/insights/documents.py`
- `src/cepe_fynsp/insights/context.py`
- `scripts/index_guidance_docs.py`
- `tests/unit/test_insight_documents_ontology.py`
- `README.md`
- `pyproject.toml` and `requirements.txt`
- Extension/count/size metadata only for files under `data/raw/docs/`; document contents were not inspected.

## Files created or modified

- Created `docs/agent_notes/2026-07-20_insights_pptx_context.md`.
- Modified `src/cepe_fynsp/insights/documents.py`.
- Modified `tests/unit/test_insight_documents_ontology.py`.
- Modified `config/approved_guidance_docs.yaml`.
- Modified `.env.example`.
- Modified `README.md`.
- Modified `docs/dependency_inventory.md`.

## Data inputs found or missing

- Found four DOCX and two PPTX source documents plus `.gitkeep` under `data/raw/docs/`.
- PPTX was not in the supported parser suffix list.
- The approval manifest was empty, so none of the local documents were eligible for indexing.
- Document classification and organizational approval metadata were not provided; no document will be automatically approved.

## Implementation summary

- Added `.pptx` to the supported guidance suffixes and advanced the parser identifier to `guidance_parser_v2`.
- Added standard-library ZIP/Open XML extraction for ordered visible slide text. Chunks retain the slide number in both page-number and `Slide N` section metadata so existing citation rendering identifies the location.
- Added bounded presentation limits: 500 slides, 5 MB uncompressed slide XML per slide, and 50 MB total slide XML. XML with document-type/entity declarations is rejected.
- Added synthetic PPTX parsing and indexing tests, including numeric slide ordering and slide-level citation metadata.
- Added all six discovered files to the approval manifest with `approved_for_asksage: false` and `pending_data_owner_review`. No local source document was automatically approved or indexed.
- Clarified that runtime AskSage values are process environment variables, not `config/settings.yaml` values, and that `.env` is not automatically loaded.
- Documented PPTX support and its exclusions. No parser dependency was added; `zipfile` and `xml.etree.ElementTree` are from the Python standard library.

## Important assumptions

- The request to reference documents authorizes adding parsing/index scaffolding, but does not establish their classification or approval for external AskSage processing.
- AskSage secrets and dataset identifiers remain environment values; they do not belong in `config/settings.yaml`.

## Commands run

- Read-only extension/count/size inventory under `data/raw/docs/`.
- Read-only inspection of configuration, parser, indexer, dependency, test, and documentation files.
- `python -m pytest tests/unit/test_insight_documents_ontology.py`
- `ruff check src scripts tests`
- `ruff format --check src scripts tests`
- `ruff format src/cepe_fynsp/insights/documents.py`
- `mypy src`
- `python -m compileall src scripts`
- `python -m pytest`
- `python scripts/build_synthetic_ci.py`
- `python scripts/validate_static.py`
- `python scripts/index_guidance_docs.py --project-root .`
- `ruff check .`
- `ruff format --check .`
- `git diff --check`
- Local parsing smoke check of both real PPTX files that printed only filenames, extracted slide counts, and aggregate character counts; it did not print or persist document text.

## Test results, including failures

- Initial targeted test run: 7 passed in 0.53 seconds.
- Initial scoped Ruff lint passed but emitted a nonfatal cache write warning; format check requested formatting for `documents.py`. The file was formatted.
- Final full test run: 87 passed in 4.44 seconds.
- Final scoped Ruff lint passed; all 64 scoped files were formatted.
- Mypy passed with no issues in 40 source files.
- Compileall passed.
- Synthetic build passed with 5 dashboards, 30 payloads, 30 RAG records, and 218 graph nodes.
- Static validation passed for the landing page and five dashboards.
- Real approval-manifest indexing produced 0 chunks, as expected because all entries remain disabled.
- Both real PPTX files parsed locally within bounds: 47 and 16 text-bearing slides. No extracted text was displayed or persisted.
- Full Ruff still reports only the pre-existing E402/format issue in `notebooks/test_asksage_api.ipynb`; all 64 scoped files are formatted. The notebook was not changed.
- `git diff --check` passed with line-ending conversion warnings only.

## Validation steps performed

- Confirmed current supported formats and empty approval allowlist.
- Confirmed raw DOCX/PPTX files are ignored by Git policy.
- Confirmed deterministic numeric slide ordering and slide-level citations with synthetic content.
- Confirmed both real PPTX archives are structurally parseable without disclosing their contents.
- Confirmed disabled approval entries do not create derived document chunks.
- Re-ran complete Python, synthetic dashboard/RAG/report, and static regression validation.

## What worked

- Existing DOCX, PDF, TXT, and Markdown parsing/indexing paths are available.
- The configured derived index path already matches the insights runtime.
- PPTX visible slide text and citations now use the same approval-gated indexing/retrieval pipeline.
- No new dependency was required.

## What did not work

- The first format check found the new parser file needed Ruff formatting; formatting resolved it.
- No local guidance file can yet be included because classification/approval decisions are still missing; zero indexed chunks is the deliberate safe result.

## Known limitations

- PPTX extraction includes text represented in slide XML but excludes speaker notes, embedded file contents, linked SmartArt-only text, audio/video, and image OCR.
- DOCX behavior remains the existing paragraph extraction path; tables, headers, footers, images, and OCR are not newly added by this task.
- No document content/classification was substantively reviewed, and no real document was sent to AskSage.
- The dashboard still requires the approved AskSage environment configuration and secure server process described in `README.md`; no credential or dataset value was added to source control.

## Suggested next steps

1. Have the data owner/security reviewer decide the classification and AskSage eligibility of each scaffolded manifest entry.
2. Replace `pending_data_owner_review` and set `approved_for_asksage: true` only for authorized documents.
3. Re-run `python scripts/index_guidance_docs.py --project-root .` and review only aggregate index metadata before starting the secure insights service.
4. Export the AskSage environment values into the same shell that starts `scripts/run_insights_server.py`; do not place secrets in `config/settings.yaml`.
