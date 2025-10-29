#!/usr/bin/env bash
set -euo pipefail
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 <<'SQL'
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_permit_agg;
REFRESH MATERIALIZED VIEW property_search;
SQL
