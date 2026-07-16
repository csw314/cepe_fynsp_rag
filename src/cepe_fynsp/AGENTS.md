# AGENTS.md - Python package scope

Coding agents editing `src/cepe_fynsp/` must keep package code modular and testable.

- Do not put raw notebook logic in package files.
- Do not call AskSage directly outside `asksage/client.py` or orchestration modules.
- Every public function should have a clear docstring.
- All data transformations should return DataFrames or typed objects, not write files implicitly unless the function name says export/write.
- File paths should come from configuration or function arguments.
- Preserve row lineage throughout transformations.

## Python implementation handoff requirements

When changing Python modules under `src/cepe_fynsp/`, update the active task note under `docs/agent_notes/`.

The note must identify:

- New public functions, classes, or modules.
- Data contracts or schemas changed.
- Input files expected by the code.
- Output files produced by the code.
- Validation and test commands run.
- Any assumptions made about FORMEX, PLANEX, COSTEX, AskSage, or ontology behavior.

Prefer small, typed, testable functions. Separate data loading, normalization, metric calculation, ontology export, RAG context generation, and dashboard payload generation. Do not mix visualization rendering logic into ETL modules.
