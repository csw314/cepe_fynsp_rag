# AGENT 03 - dashboard objectives and question inventory

## Purpose

This file defines the five dashboards and their required natural-language questions. Coding agents should not replace these questions unless the user asks for a revised analytic design.

## Shared requirements

- Each dashboard must ask and answer 4-7 natural-language questions.
- Each question must have a corresponding visualization or evidence component.
- The default filter is Integration Area = Pit Production.
- Every visual must expose source, filters, metric definition, and lineage ID.
- Each visual must be summarizable by the RAG agent.

## Dashboard 1 - Pit Production Accuracy and Thoroughness Overview

Purpose: Fast portfolio-level assessment of what is programmed, where it goes, who owns it, what is above baseline, and which data issues matter.

Questions:

1. How much funding is programmed for Pit Production by fiscal year and funding level?
   - Visualization: stacked bar by fiscal year and funding level.
2. Which organizations own the largest Pit Production funding shares?
   - Visualization: ranked horizontal bar by sub-office and funding level.
3. Which sites receive Pit Production funding, and how concentrated is the portfolio?
   - Visualization: treemap or ranked site bar using Federal Site Splits.
4. Which program requests drive above-baseline Pit Production growth?
   - Visualization: Pareto chart of ROT/UFR dollars by program request.
5. Are there rows that appear incomplete, contradictory, or hard to trace?
   - Visualization: data-quality scorecard and exception table.
6. Do Crosscuts and Site Splits reconcile for Pit Production?
   - Visualization: reconciliation waterfall or variance table.

## Dashboard 2 - Acquisition and Schedule Executability Monitor

Purpose: Determine whether acquisition-associated funding has enough schedule and metadata support for review.

Questions:

1. How much Pit Production funding is tied to construction, MIEs, major modernization, or no acquisition tag?
   - Visualization: stacked bar by acquisition type and funding level.
2. Which acquisition lines have the largest programmed values?
   - Visualization: ranked table by acquisition ID/name/type.
3. Do acquisition start and end dates support the funding profile?
   - Visualization: Gantt-style timeline with annual funding overlay.
4. Which acquisition rows have missing, classified, or suspicious dates?
   - Visualization: exception table and quality gauge.
5. Where are LI TEC and LI OPC dollars concentrated by year and site?
   - Visualization: fiscal-year by site heatmap.
6. Which above-baseline acquisition requests are high-dollar and high-priority?
   - Visualization: bubble chart with dollars, tier/priority, acquisition type.

## Dashboard 3 - Site Capacity and Integration Burden Dashboard

Purpose: Show site-level concentration, above-baseline dependence, organization-to-site dependencies, and funding surges.

Questions:

1. Which sites receive the most Pit Production funding over FY2028-FY2032?
   - Visualization: ranked site bar or treemap.
2. How does Pit Production funding change by site and year?
   - Visualization: site-by-year heatmap.
3. Which sites depend most on above-baseline funding?
   - Visualization: 100 percent stacked bar of Baseline/ROT/UFR by site.
4. Which organizations are funding the same site, creating integration dependencies?
   - Visualization: Sankey diagram from sub-office to site to funding level.
5. Are there site-level funding cliffs or surges that should trigger executability review?
   - Visualization: year-over-year change chart by site.
6. Which site rows lack enough descriptive detail to support a thorough review?
   - Visualization: drill-through table, optionally LLM-classified for generic scope text.

## Dashboard 4 - Priority, Tier, and Program Request Challenge Board

Purpose: Challenge above-baseline requests and prioritization quality.

Questions:

1. What are the largest Pit Production ROT and UFR requests?
   - Visualization: Pareto chart.
2. Which above-baseline requests are marked Tier 1, and why is that a review issue?
   - Visualization: DOE Priority Tier by Funding Level heatmap with flags.
3. Do program priorities form a clear 1-N ranking, or are priorities reused across requests?
   - Visualization: priority uniqueness matrix and duplicate-priority table.
4. Which requests appear to be offsets, restorations, or delays?
   - Visualization: waterfall linking negative and positive program requests.
5. Which requests have strong traceability from title to scope, site, WBS, and acquisition?
   - Visualization: traceability scorecard.
6. Which rows lack Account Integrator decision traceability?
   - Visualization: completeness gauge and exception table.

## Dashboard 5 - CEPE Findings, Evidence, and Report Generator

Purpose: Convert dashboard evidence into a report-ready set of findings and draft narrative.

Questions:

1. What are the top accuracy findings for the Pit Production FYNSP?
   - Visualization: finding cards with severity, affected dollars, and row count.
2. What are the top thoroughness findings?
   - Visualization: coverage matrix.
3. What are the most material uncertainties, risks, and opportunities?
   - Visualization: risk/opportunity heatmap.
4. Which exhibits best support the findings?
   - Visualization: exhibit gallery with chart thumbnails and captions.
5. Which source rows and guidance passages support each statement?
   - Visualization: citation lineage graph.
6. What should be included in the 5-7 page CEPE report?
   - Visualization: generated report outline and export controls.
