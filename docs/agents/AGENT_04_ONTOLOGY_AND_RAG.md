# AGENT 04 - ontology and RAG architecture

## Purpose

This file defines how the graph ontology and RAG agent should ground dashboard explanations, chart summaries, user questions, and report generation.

## Core principle

The RAG agent must not answer from free memory. It must retrieve from:

1. Dashboard payloads and chart metadata.
2. Source-row lineage tables.
3. Guidance/document chunks.
4. Ontology graph context.
5. Data-quality rule outputs.

## Recommended ontology nodes

- `Scenario`: FY28/32 Rev3 TargetFRS.
- `SubmissionType`: Federal Crosscuts, Federal Site Splits, GPRA Constraints, Federal STAT Table.
- `FundingLine`: normalized source row or canonical aggregated line.
- `FiscalYear`: FY2028-FY2032.
- `FundingLevel`: Baseline, ROT, UFR.
- `Appropriation`: NNSA-WA, NNSA-DNN, NNSA-NR, NNSA-FSE.
- `Organization`: sub-office such as NA-19, NA-90, NA-70, NA-12, NA-ESH.
- `Site`: LANL, SRS-SRNS, LLNL, NNSS, and other site values.
- `WBS`: WBS code/name/level.
- `BNR`: BNR code.
- `ProgramValue`: program value code.
- `IntegrationArea`: Pit Production and other programmatic integration areas.
- `ProcessImprovementArea`: Digital Transformation, DOE Quantum Computing, DOE Fusion Energy, AI Genesis areas where present.
- `ProgramRequest`: program request text.
- `Acquisition`: acquisition ID/name/type/start/end.
- `Priority`: DOE Priority Tier, Program Priority, Account Integrator Priority.
- `Finding`: quality, reconciliation, tier, schedule, traceability, and materiality findings.
- `Chart`: dashboard visualization payload.
- `ReportParagraph`: generated narrative paragraph.
- `Citation`: guidance chunk, source-row ID, chart ID, or metric definition.

## Recommended edges

- `FundingLine -> belongs_to -> Scenario`
- `FundingLine -> represented_by -> SubmissionType`
- `FundingLine -> has_fiscal_year -> FiscalYear`
- `FundingLine -> has_funding_level -> FundingLevel`
- `FundingLine -> funded_by -> Appropriation`
- `FundingLine -> owned_by -> Organization`
- `FundingLine -> split_to_site -> Site`
- `FundingLine -> coded_to -> WBS`
- `FundingLine -> coded_to -> BNR`
- `FundingLine -> coded_to -> ProgramValue`
- `FundingLine -> tagged_to -> IntegrationArea`
- `FundingLine -> tagged_to -> ProcessImprovementArea`
- `FundingLine -> describes -> ProgramRequest`
- `FundingLine -> supports_acquisition -> Acquisition`
- `FundingLine -> has_priority -> Priority`
- `Metric -> derived_from -> FundingLine`
- `Chart -> visualizes -> Metric`
- `Finding -> triggered_by -> Rule`
- `Finding -> supported_by -> Chart`
- `Finding -> supported_by -> Citation`
- `ReportParagraph -> cites -> Citation`

## RAG retrieval packets

For each chart, export a retrieval packet with:

- `chart_id`
- `dashboard_id`
- `question_id`
- `natural_language_question`
- `metric_definition`
- `filters`
- `source_dataset`
- `source_submission_type`
- `source_row_ids_or_hashes`
- `aggregation_sql_or_pandas_expression`
- `chart_summary_stats`
- `known_limitations`
- `ontology_context`
- `recommended_talking_points`

## Agent response rules

- Always answer the user's direct question first.
- Use exact dashboard filters and metrics where possible.
- Distinguish observed data from interpretation.
- Include traceability IDs in structured responses intended for report generation.
- State when additional data is required, for example for carryover, FEP, or cross-year execution reconciliation.
- Do not invent guidance citations.
- Do not infer site executability solely from dollar totals; call it a review trigger unless external execution/capacity data is supplied.

## LLM classification tasks

The AskSage-backed classification layer may classify:

- Scope description quality: specific, generic, missing, classified, or not applicable.
- Program request intent: baseline activity, offset, restoration, acceleration, delay, risk mitigation, schedule recovery, construction, operations, staffing, unknown.
- Finding category: accuracy, thoroughness, executability, traceability, prioritization, acquisition, site burden, data limitation.
- Severity: low, medium, high, critical using dollar exposure, row count, and rule type.

All classifications must include model name, prompt version, input fields, output label, confidence if available, and review status.
