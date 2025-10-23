# PropertyFish (NYC Commercial)
Plain-English chat that returns a complete, **source-cited** NYC commercial property dossier (Manhattan, Brooklyn, Queens) on one page.

## Quick start
- Backend: FastAPI + Postgres + PostGIS
- Frontend: Next.js/React (single page: chat + property cards + map)
- ETL: Python (ACRIS, PLUTO/MapPLUTO, DOB, ZoLa)
- Cache: Redis (optional)

See `docs/` for product+tech source of truth. All work must be logged to `logs/ACTIVITY_LOG.md`.

## Runbook
- **Terminal A (app)**
  - `docker compose -f infra/docker-compose.yml up -d`
  - `source .venv/bin/activate`
  - `export $(grep -v '^#' backend/.env | xargs) || true`
  - `uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000`
- **Terminal B (data)**
  - `source .venv/bin/activate`
  - `export $(grep -v '^#' backend/.env | xargs) || true`
  - `python scripts/ingest_dob_permits.py --since 2024-01-01 --until 2024-01-31`
    - Defaults: `--date-field issuance_date`, `--recent 50000`, ISO timestamps; override with `--days N` if no explicit window.
  - `python scripts/join_pipeline.py --parcels-table pluto --enforce-stage1 0.8`
    - If `parcels` view is missing or not a view, run `psql "$DATABASE_URL" -c "DROP VIEW IF EXISTS parcels; CREATE VIEW parcels AS SELECT * FROM pluto;"`.
