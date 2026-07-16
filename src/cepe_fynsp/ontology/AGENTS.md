# AGENTS.md - ontology scope

Ontology code should build graph context used by dashboards and RAG.

- Use stable node IDs.
- Avoid duplicating raw table rows unnecessarily.
- Keep relationships explicit and typed.
- Export JSON-LD and a lightweight dashboard-friendly graph JSON.
- Every chart payload should include relevant ontology node IDs.
