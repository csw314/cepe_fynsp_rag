# AGENTS.md - web scope

The web app is static HTML with local CSS and JavaScript.

- One landing page at `web/index.html`.
- Five dashboards under `web/dashboards/`.
- No hardcoded analytic totals in HTML.
- Load chart data from generated JSON payloads.
- Each dashboard page must include natural-language questions, chart containers, source notes, and RAG summary panels.
- Avoid internet dependencies in production. Vendor approved JS assets locally or use an approved internal mirror.

## Web dashboard handoff requirements

When changing files under `web/`, update the active task note under `docs/agent_notes/`.

The note must identify:

- Dashboard pages changed.
- Static assets changed.
- JSON payloads expected by the page.
- Chart containers added.
- Manual validation performed in a browser or by static inspection.
- Known front-end limitations.

HTML dashboard pages must not contain hard-coded FYNSP metric values unless explicitly labeled as placeholder content. Production metric values must come from generated JSON payloads under `data/curated/dashboard_payloads/`.

Do not expose AskSage credentials, API keys, tokens, or sensitive URLs in browser-side JavaScript. Browser-side AskSage interactions must call a safe backend or use pre-generated RAG summaries.