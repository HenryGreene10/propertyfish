# Deploy (dev)
- Run `docker compose up -d` from `infra/`.
- Open API at http://localhost:8000 and frontend at http://localhost:3000 (once wired).

# Notes
- Load `backend/app/db/schema.sql` into Postgres.

## Sprint A dev bootstrap
- Start DB: `docker compose up -d` (from `infra/`).
- Load schema: `psql "$DATABASE_URL" -f backend/app/db/schema.sql`.
- Ingest PLUTO seed: `PLUTO_CSV_PATH=backend/app/db/seeds/pluto_sample.csv python backend/etl/pluto_ingest.py`.
- Start API: `uvicorn app.main:app --app-dir backend/app --reload`.
- Run tests: `pytest -q`.

## Sprint B dev bootstrap
- If fresh DB: `psql "$DATABASE_URL" -f backend/app/db/schema.sql`.
- Ingest ACRIS seed: `ACRIS_CSV_PATH=backend/app/db/seeds/acris_sample.csv python backend/etl/acris_ingest.py`.
- Start API: `uvicorn app.main:app --app-dir backend/app --reload`.
- Verify: GET `/property/1012700008/deeds` returns seeded rows.
