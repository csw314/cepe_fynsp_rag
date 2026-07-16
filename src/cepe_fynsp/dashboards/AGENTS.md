# AGENTS.md - dashboard payload scope

Dashboard code should calculate metrics and export JSON payloads for static HTML.

- Each payload must include dashboard ID, question ID, metric definition, filters, source dataset, chart data, and lineage.
- Do not hardcode numbers in HTML.
- Use one payload file per dashboard plus optional per-chart files.
- Include a natural-language question with every chart.
