#!/usr/bin/env bash
set -euo pipefail
: "${DATABASE_URL:?DATABASE_URL is required}"
CSV_PATH="${1:-data/pad_bin_bbl.csv}"  # CSV headers: bin,bbl

psql "$DATABASE_URL" -v ON_ERROR_STOP=1 <<'SQL'
CREATE TEMP TABLE pad_bin_bbl_stage (bin bigint, bbl bigint);
SQL

psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "\copy pad_bin_bbl_stage (bin,bbl) FROM '${CSV_PATH}' WITH (FORMAT csv, HEADER true)"

psql "$DATABASE_URL" -v ON_ERROR_STOP=1 <<'SQL'
INSERT INTO pad_bin_bbl (bin, bbl)
SELECT s.bin, s.bbl
FROM pad_bin_bbl_stage s
ON CONFLICT (bin) DO UPDATE SET bbl = EXCLUDED.bbl;
DROP TABLE pad_bin_bbl_stage;
SQL

echo "Loaded BIN→BBL: $(psql "$DATABASE_URL" -t -A -c 'SELECT count(*) FROM pad_bin_bbl;') rows"
