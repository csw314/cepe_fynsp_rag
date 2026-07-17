# Raw source directory

Raw source files are immutable inputs and are intentionally ignored by Git. Pipeline code must never overwrite them.

Configured locations:

- `formex/CSV Download.csv` — UTF-16, tab-delimited FORMEX.
- `planex/idw_planex_202607171050.csv` — comma-delimited PLANEX.
- `costex/idw_costex_202607171052.csv` — comma-delimited COSTEX.
- `docs/` — approved guidance documents, when available.

Update `config/settings.yaml` and the corresponding executable contract under `config/data_contracts/` when an authorized export name or structure changes. Do not commit raw exports, credentials, classified material, controlled rows, generated reports, or copied source samples.
