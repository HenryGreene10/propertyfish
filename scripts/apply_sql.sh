#!/usr/bin/env bash
set -euo pipefail
: "${DATABASE_URL:?DATABASE_URL not set}"

for f in \
  sql/00_helpers.sql \
  sql/10_permits_norm.sql \
  sql/11_violations_norm.sql \
  sql/20_joins_permits.sql \
  sql/21_joins_violations.sql \
  sql/30_indexes.sql
do
  echo ">>> applying $f"
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f"
done

echo "Sanity:"
psql "$DATABASE_URL" -c "SELECT COUNT(*) AS permits FROM vw_permits_norm;"
psql "$DATABASE_URL" -c "SELECT COUNT(*) AS violations FROM vw_violations_norm;"
psql "$DATABASE_URL" -c "SELECT * FROM vw_permits_join_coverage;"
psql "$DATABASE_URL" -c "SELECT * FROM vw_violations_join_coverage;"
