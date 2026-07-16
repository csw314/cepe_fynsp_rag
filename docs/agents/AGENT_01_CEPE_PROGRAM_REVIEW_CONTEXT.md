# AGENT 01 - CEPE program review context

## Purpose for coding agents

Use this file to ground all coding, dashboard, ontology, and RAG decisions in CEPE's program review mission for FYNSP 2028.

## CEPE mission context

The Office of Cost Estimating and Program Evaluation supports independent review of NNSA cost estimates, program performance, and program evaluation. For this project, the central review standard is whether FYNSP programming data is accurate and thorough.

The dashboard suite must help a CEPE analyst prepare a budget accuracy and thoroughness report for an integration area. The initial exemplar integration area is Pit Production.

## Program review frame

CEPE-style review should assess whether submitted programming data is:

- Accurate: internally consistent, arithmetically reconciled, aligned to the correct submission layer, coded to valid fiscal years, mapped to the correct integration area, and supported by source-row lineage.
- Thorough: sufficiently complete to understand scope, organization, site, funding level, WBS, BNR/program value, acquisition, priority, schedule, and decision status.
- Executable: credible against acquisition schedule, site burden, current execution context, and funding cliffs or surges.
- Defensible: prioritization and above-baseline requests should be explainable and traceable to guidance, mission need, and program request narrative.

## FY2028-FY2032 programming concepts to preserve

- FYNSP cycle covers FY2028 through FY2032.
- FormEX is the central programming submission data source.
- Funding levels include Baseline, ROT, and UFR in the provided extract.
- Programming guidance also discusses Decrement, Baseline, and Full Requirement/Above Baseline constructs.
- Submission types are overlapping views, not additive totals.
- Account Integrators and NA-1/Administrator review are part of the review and adjudication path.
- Programmatic integration areas support cross-program review.
- Process improvement areas such as Digital Transformation, Quantum, Fusion, and AI Genesis may cut across program structure.

## Guidance concepts that must affect dashboard logic

- Do not treat raw FORMEX total as the total FYNSP value.
- Use explicit submission-layer filters.
- Programmatic integration-area analysis should be tested for reconciliation between Federal Crosscuts and Federal Site Splits.
- Tier 1 above-baseline requests should be flagged for analyst review because Tier 1 mandated activities are expected to be included in baseline.
- Acquisition rows should be checked for ID, name, type, start date, and end date.
- Account Integrator Decision and Account Integrator Priority fields may not be populated in the uploaded extract; the dashboard should surface that limitation.
- Carryover, FEP, and executability concerns are program-review issues, but may require supplemental data beyond the uploaded CSV files.

## Analyst output

The dashboard should culminate in a 5-7 page report draft with:

1. Executive summary.
2. Scope and data sources.
3. Dashboard question answers.
4. Exhibits/images supporting each question.
5. Accuracy findings.
6. Thoroughness findings.
7. Uncertainty, risk, and opportunity findings.
8. Limitations and recommended follow-up data requests.
9. Traceable citations to guidance chunks, source rows, and chart payloads.
