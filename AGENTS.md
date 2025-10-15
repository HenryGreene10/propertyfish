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
