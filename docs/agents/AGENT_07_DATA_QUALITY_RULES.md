# AGENT 07 - data quality and review rules

## Purpose

This file defines deterministic quality checks that should run before any LLM/RAG interpretation.

## FORMEX quality rules

### Rule FQ001 - Submission layer required

Every FORMEX aggregation must specify `submission_type`.

Severity: critical for dashboard totals.

### Rule FQ002 - Scenario required

Every FORMEX aggregation should specify `scenario` if more than one scenario is present.

Severity: high.

### Rule FQ003 - Amount parse completeness

`formulated_measure` must parse to a numeric amount. Rows that fail parsing should be quarantined.

Severity: high.

### Rule FQ004 - Federal Crosscuts versus Federal Site Splits reconciliation

For a given integration area and funding level, compare Federal Crosscuts and Federal Site Splits totals. Flag material variances.

Severity: high if variance is material.

### Rule FQ005 - Missing program request

Flag non-baseline or above-baseline rows with missing `program_request`.

Severity: medium to high depending on dollars.

### Rule FQ006 - Missing scope description

Flag rows with missing or generic `scope_description`, especially above-baseline rows.

Severity: medium.

### Rule FQ007 - Account Integrator Decision missing

Flag missing `account_integrator_decision`, but report the field may be structurally unpopulated in the uploaded extract.

Severity: limitation unless the review phase requires this field.

### Rule FQ008 - Account Integrator Priority unusable

If all values are 0 or blank, mark the field as not analytically useful.

Severity: limitation.

### Rule FQ009 - Tier 1 above baseline

Flag rows where `doe_priority_tier == 1` and `funding_levels` is ROT or UFR.

Severity: high review trigger.

### Rule FQ010 - Acquisition metadata completeness

For rows with an acquisition type, require acquisition ID, acquisition name, start date, and end date unless explicitly not applicable.

Severity: high for high-dollar rows.

### Rule FQ011 - Acquisition date validity

Flag acquisition end dates before start dates. Flag date gaps or invalid dates.

Severity: high.

### Rule FQ012 - Negative amount review

Flag negative amounts and classify them as offset, decrement, restoration counterpart, correction, or unknown.

Severity: review trigger.

### Rule FQ013 - Duplicate priority review

For above-baseline program requests, identify duplicated program priorities where a unique 1-N ranking is expected.

Severity: medium.

### Rule FQ014 - Site split completeness

For site analyses, flag rows missing `site_planex` or with generic site values when specificity is expected.

Severity: medium.

### Rule FQ015 - WBS traceability

Flag missing WBS, WBS name, or WBS level.

Severity: medium to high depending on dollars.

## PLANEX/COSTEX quality rules

### Rule CX001 - Cost plan versus costed aggregate check

Compare PLANEX `cost_plan` and COSTEX `dollars` at compatible rollups. Record variance and unmatched rows.

### Rule CX002 - Join confidence

Any join from FY2026 PLANEX/COSTEX to FY2028-FY2032 FORMEX must report keys, match rates, unmatched dollars, and limitations.

### Rule CX003 - Uncosted and encumbrance exposure

Flag WBS/site/program combinations with material uncosted or encumbrance exposure where relevant.

## Materiality scoring

Default score inputs:

- Dollar exposure.
- Row count.
- Funding level, with ROT/UFR weighted higher for challenge review.
- Whether rule affects accuracy or thoroughness.
- Whether finding blocks traceability or reportability.
- Whether finding is isolated or systemic.

Severity labels:

- Low: informational.
- Medium: analyst review recommended.
- High: material review trigger.
- Critical: dashboard total or report conclusion may be invalid without resolution.
