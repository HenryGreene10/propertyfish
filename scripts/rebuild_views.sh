#!/usr/bin/env bash
set -euo pipefail
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/joins/mv_permit_agg.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/joins/mv_property_search.sql
echo "Views rebuilt."
