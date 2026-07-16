# AGENT 06 - report generator requirements

## Purpose

This file defines the report agent that drafts the CEPE analyst report from dashboard evidence.

## Required output

The report agent must generate a 5-7 page Word-compatible report draft. The preferred implementation path is:

1. Use dashboard payloads and chart images as evidence.
2. Use RAG to retrieve applicable guidance snippets and ontology context.
3. Draft report sections as structured markdown with citation metadata.
4. Convert structured markdown to `.docx` using Python.
5. Save report outputs under `data/reports/docx/` and `data/reports/html/`.

## Required sections

1. Executive Summary
2. Review Scope and Data Sources
3. Dashboard Question Answers
4. Accuracy Findings
5. Thoroughness Findings
6. Uncertainty, Risk, and Opportunity Findings
7. Data Limitations and Recommended Follow-Up
8. Appendix: Source Lineage and Guidance Citations

## Citation requirements

Every material claim must trace to at least one of:

- Source-row lineage ID.
- Dashboard chart ID.
- Metric definition ID.
- Guidance chunk ID.
- Ontology node/edge path.
- Quality rule ID.

The report generator should store a `citation_manifest.json` with:

- report_id
- paragraph_id
- claim_text
- citation_type
- citation_id
- source_file
- source_filter
- chart_id
- dashboard_id
- retrieval_chunk_id
- ontology_path

## Report writing rules

- Do not overstate findings.
- Distinguish findings, review triggers, and limitations.
- Use dollar amounts rounded consistently.
- Use exact fiscal years, not relative date phrases.
- Avoid unsupported claims about executability; use language such as "review trigger" unless external evidence supports a conclusion.
- Include a table of dashboard questions and answers.
- Include images or chart snapshots for each question.

## Recommended report exhibits

- Pit Production funding by fiscal year and funding level.
- Pit Production site concentration.
- Top above-baseline program requests.
- Tier 1 above-baseline flags.
- Acquisition schedule completeness.
- Data-quality and traceability scorecard.
- Crosscuts versus Site Splits reconciliation.
