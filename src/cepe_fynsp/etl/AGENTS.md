# AGENTS.md - ETL scope

ETL code must be deterministic and independent of LLM calls.

Required behavior:

- Load FORMEX as UTF-16 tab-delimited unless auto-detected otherwise.
- Drop fully empty trailing columns such as unnamed export columns.
- Normalize column names to snake_case.
- Add stable `source_row_id` or `source_row_hash`.
- Parse amounts and fiscal years.
- Save normalized outputs to Parquet.
- Never mutate files under `data/raw/`.
