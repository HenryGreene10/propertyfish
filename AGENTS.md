Environment: WSL Ubuntu

Shell: bash (use Unix commands and paths)

Backend:
  - Start DB: docker compose -f infra/docker-compose.yml up -d
  - Run API: source .venv/bin/activate && export $(grep -v '^#' backend/.env | xargs) || true && uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000
  - Health check: curl http://localhost:8000/health (expect 200)

Notes:
  - Use PostGIS image via compose (do not switch to plain postgres).
  - Avoid Windows paths (C:\...) and CRLF endings.
  - Assume DATABASE_URL is in backend/.env.

DB Snapshot Guidance:
  - Never connect to Postgres. Use the snapshot files in this repo:
    - docs/db/schema.sql
    - docs/db/core_objects.sql
    - docs/db/property_search_desc.txt
    - docs/db/property_search_columns.csv
    - docs/api/openapi.json
    - fixtures/property_search_sample.csv and fixtures/api.search.*.json
  - When you need column names or types, read property_search_columns.csv and property_search_desc.txt. Treat those as ground truth.
  - If backend fields differ from frontend expectations, alias in SQL (SELECT … AS <frontend_field>) rather than guessing names.
  - Keep changes minimal; prefer surgical diffs and temporary debug logs tagged: PF-FE-SEARCH (frontend) and PF-BE-SEARCH (backend).
