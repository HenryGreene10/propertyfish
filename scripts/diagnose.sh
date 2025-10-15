#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
cd "$ROOT"

mkdir -p _reports/logs

# Repo snapshot
find . -maxdepth 2 -print > _reports/logs/tree_top2.log
find backend -maxdepth 3 -print > _reports/logs/tree_backend.log || true
find frontend -maxdepth 3 -print > _reports/logs/tree_frontend.log || true
find scripts -maxdepth 2 -print > _reports/logs/tree_scripts.log || true

git rev-parse --is-inside-work-tree > _reports/logs/git_is_inside.log
git rev-parse --show-toplevel > _reports/logs/git_root.log

# Env scans
rg -n "os\\.getenv" --hidden --no-heading > _reports/logs/env_rg_os_getenv.log || true
rg -n "process\\.env" --hidden --no-heading > _reports/logs/env_rg_process_env.log || true
rg -n "SUPABASE" --hidden --no-heading > _reports/logs/env_rg_supabase.log || true

# Backend sweep
if [ -d backend ]; then
  pushd backend >/dev/null || exit 1
  python3 -V |& tee ../_reports/logs/backend_python_version.log
  python3 -m venv .venv >/dev/null 2>&1 || true
  source .venv/bin/activate
  pip install -U pip wheel |& tee ../_reports/logs/backend_pip_upgrade.log || true
  if [ -f requirements.txt ]; then
    pip install -r requirements.txt |& tee ../_reports/logs/backend_pip_install.log || true
  fi
  if [ -f pyproject.toml ]; then
    pip install -e . |& tee ../_reports/logs/backend_pip_editable.log || true
  fi
  pip check |& tee ../_reports/logs/backend_pip_check.log || true
  python -c "import sys; print('cwd ok')" |& tee ../_reports/logs/backend_sanity.log
  python -m pip install ruff mypy |& tee ../_reports/logs/backend_tools_install.log || true
  ruff check . |& tee ../_reports/logs/backend_ruff.log || true
  mypy . --install-types --non-interactive |& tee ../_reports/logs/backend_mypy.log || true
  python -m pip install pytest httpx |& tee ../_reports/logs/backend_pytest_install.log || true
  pytest -q |& tee ../_reports/logs/backend_pytest.log || true
  python -c "import os; print('SUPABASE_URL=', os.getenv('SUPABASE_URL'))" |& tee ../_reports/logs/backend_env_echo.log
  uvicorn app.main:app --host 127.0.0.1 --port 8000 --timeout-keep-alive 5 &
  BACK_PID=$!
  sleep 4
  curl -sSf http://127.0.0.1:8000/docs | head -n 20 |& tee ../_reports/logs/backend_boot_probe.log || true
  kill $BACK_PID >/dev/null 2>&1 || true
  deactivate
  popd >/dev/null || true
fi

# Frontend sweep
if [ -d frontend ]; then
  pushd frontend >/dev/null || exit 1
  node -v |& tee ../_reports/logs/frontend_node_version.log || true
  npm -v |& tee ../_reports/logs/frontend_npm_version.log || true
  npm ci |& tee ../_reports/logs/frontend_npm_ci.log || npm install |& tee ../_reports/logs/frontend_npm_install.log || true
  npx npm-check-updates -u |& tee ../_reports/logs/frontend_ncu.log || true
  ./node_modules/.bin/eslint . |& tee ../_reports/logs/frontend_eslint.log || true
  ./node_modules/.bin/tsc --noEmit |& tee ../_reports/logs/frontend_tsc.log || true
  npm run test --silent |& tee ../_reports/logs/frontend_test.log || true
  npm run build |& tee ../_reports/logs/frontend_build.log || true
  popd >/dev/null || true
fi

# Large files
git ls-files -z | xargs -0 -I{} bash -lc 'f="{}"; [ -f "$f" ] && sz=$(wc -c < "$f"); if [ "$sz" -gt 50000000 ]; then echo "$sz  $f"; fi' | sort -nr > _reports/logs/oversize_files.log || true
git ls-files -z | xargs -0 -I{} bash -lc 'f="{}"; [ -f "$f" ] && sz=$(wc -c < "$f"); if [ "$sz" -gt 10000000 ]; then echo "$sz  $f"; fi' | sort -nr > _reports/logs/oversize_10mb_files.log || true

# Secrets scan
rg -n --hidden --ignore-file=.gitignore -e 'apikey|api_key|secret|supabase|token|bearer|PRIVATE|PASSWORD' | tee _reports/logs/secrets_grep.log || true

# Env manifest (static snapshot)
cat <<'JSON' > _reports/env_required.json
{
  "DATABASE_URL": {
    "locations": [
      "backend/run_ingestion.py:15",
      "backend/app/db/connection.py:16",
      "backend/app/services/chat.py:34",
      "backend/app/ingestion/orchestrator.py:18"
    ],
    "notes": "Postgres DSN required for backend services and ingestion"
  },
  "ENV": {
    "locations": [
      "backend/app/main.py:29",
      "backend/app/routes.py:12"
    ],
    "notes": "Controls FastAPI environment-specific behavior"
  },
  "ACRIS_CSV_PATH": {
    "locations": ["backend/etl/acris_ingest.py:37"],
    "notes": "Optional override for local ACRIS seed ingest"
  },
  "DOB_PERMITS_CSV_PATH": {
    "locations": ["backend/etl/dob_ingest.py:20"],
    "notes": "Optional path for DOB permits seed ingest"
  },
  "DOB_VIOLATIONS_CSV_PATH": {
    "locations": ["backend/etl/dob_ingest.py:70"],
    "notes": "Optional path for DOB violations seed ingest"
  },
  "ZONING_CSV_PATH": {
    "locations": ["backend/etl/zola_ingest.py:26"],
    "notes": "Optional path for zoning seed ingest"
  },
  "PLUTO_CSV_PATH": {
    "locations": ["backend/etl/pluto_ingest.py:26"],
    "notes": "Legacy PLUTO ingest seed path"
  },
  "PLUTO_URL": {
    "locations": ["backend/app/ingestion/pluto.py:35"],
    "notes": "Download URL for citywide MapPLUTO ZIP"
  },
  "USE_BBL_AS_PK": {
    "locations": ["backend/app/ingestion/pluto.py:62"],
    "notes": "Toggle to treat BBL as primary key during PLUTO ingest"
  },
  "NYC_SOCRATA_BASE": {
    "locations": ["backend/app/ingestion/common.py:16"],
    "notes": "Base URL for Socrata API"
  },
  "NYC_SOCRATA_APP_TOKEN": {
    "locations": ["backend/app/ingestion/common.py:17"],
    "notes": "Socrata app token for rate-limited datasets"
  },
  "POLITE_MIN_SLEEP_MS": {
    "locations": ["backend/app/ingestion/framework.py:41"],
    "notes": "Lower bound for ingestion politeness delay"
  },
  "POLITE_MAX_SLEEP_MS": {
    "locations": ["backend/app/ingestion/framework.py:42"],
    "notes": "Upper bound for ingestion politeness delay"
  },
  "DOB_PERMITS_RESOURCE_ID": {
    "locations": ["backend/app/ingestion/catalog.yml"],
    "notes": "Socrata resource id for DOB permits datasets"
  },
  "PERMITS_DATE_FIELD": {
    "locations": ["backend/app/ingestion/catalog.yml"],
    "notes": "Override date field for permits ingest"
  },
  "DOB_VIOL_RESOURCE_ID": {
    "locations": ["backend/app/ingestion/catalog.yml"],
    "notes": "Socrata resource id for DOB violations"
  },
  "DOB_VIOL_DATE_FIELD": {
    "locations": ["backend/app/ingestion/catalog.yml"],
    "notes": "Date field override for DOB violations ingest"
  },
  "HPD_VIOL_RESOURCE_ID": {
    "locations": ["backend/app/ingestion/catalog.yml"],
    "notes": "HPD violations dataset id"
  },
  "HPD_VIOL_DATE_FIELD": {
    "locations": ["backend/app/ingestion/catalog.yml"],
    "notes": "Date field override for HPD violations"
  },
  "HPD_REG_RESOURCE_ID": {
    "locations": ["backend/app/ingestion/catalog.yml"],
    "notes": "HPD registrations dataset id"
  },
  "HPD_REG_DATE_FIELD": {
    "locations": ["backend/app/ingestion/catalog.yml"],
    "notes": "Date field override for HPD registrations"
  },
  "ACRIS_LEGAL_RESOURCE_ID": {
    "locations": ["backend/app/ingestion/catalog.yml"],
    "notes": "ACRIS legal dataset id"
  },
  "ACRIS_LEGAL_DATE_FIELD": {
    "locations": ["backend/app/ingestion/catalog.yml"],
    "notes": "Date field override for ACRIS legal ingest"
  },
  "ACRIS_MTG_RESOURCE_ID": {
    "locations": ["backend/app/ingestion/catalog.yml"],
    "notes": "ACRIS mortgage dataset id"
  },
  "ACRIS_MTG_DATE_FIELD": {
    "locations": ["backend/app/ingestion/catalog.yml"],
    "notes": "Date field override for ACRIS mortgage ingest"
  },
  "NEXT_PUBLIC_API_BASE": {
    "locations": ["frontend/app/api.ts:2"],
    "notes": "Frontend fetch base URL"
  }
}
JSON

# Secrets scan already performed, oversize logs done

