#!/usr/bin/env bash
set -euo pipefail

VER=25v2_1
DATA_DIR="${DATA_DIR:-$(git rev-parse --show-toplevel)/data/pluto/$VER}"
ZIP="$DATA_DIR/nyc_pluto_${VER}_csv.zip"
CSV="$DATA_DIR/pluto_${VER}.csv"
SLIM="$DATA_DIR/pluto_slim.csv"

mkdir -p "$DATA_DIR"
echo "[*] Using $DATA_DIR"

# 1) fetch zip if missing
if [ ! -f "$ZIP" ]; then
  echo "[*] Downloading PLUTO $VER..."
  curl -fL --retry 3 -H 'User-Agent: Mozilla/5.0' \
    -o "$ZIP" \
    "https://s-media.nyc.gov/agencies/dcp/assets/files/zip/data-tools/bytes/pluto/nyc_pluto_${VER}_csv.zip"
fi

# 2) extract main CSV
if [ ! -f "$CSV" ]; then
  echo "[*] Extracting CSV..."
  unzip -j "$ZIP" '*.csv' -d "$DATA_DIR"
  mv "$DATA_DIR"/pluto_*.csv "$CSV"
fi

# 3) make slim file (needs csvkit in venv or PATH)
if ! command -v csvcut >/dev/null 2>&1; then
  echo "csvkit not found. Install with: pip install csvkit"
  exit 1
fi

echo "[*] Building slim CSV..."
csvcut -c bbl,address,zipcode,borough,block,lot "$CSV" > "$SLIM"

# 4) load via SQL
echo "[*] Loading into Postgres..."
psql "$DATABASE_URL" -v csv="$SLIM" -f "$(git rev-parse --show-toplevel)/scripts/pluto_load.sql"

echo "[✓] Done."
