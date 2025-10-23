# Code Tombstones

The following paths are intentionally retired to avoid drift. They remain in the repo only as stubs so historical references do not break.

- `scripts/load_pluto.sh` — Legacy PLUTO loader superseded by `backend/app/ingestion/pluto.py` and `scripts/join_pipeline.py`. Previous flow conflicted with canonical schema and is now disabled.
- `scripts/pluto_load.sql` — Former `psql` loader that populated `dim_*` tables no longer present in the application schema. Use the ingestion module + join views instead.
- `scripts/schema.sql` — Out-of-date schema snapshot that diverged from `backend/app/db/schema.sql`. Retained as a stub to prevent accidental usage.
