"""PLUTO/MapPLUTO ingest (Sprint A).

Reads a CSV of PLUTO-like fields and upserts into `parcels`.

Env:
- PLUTO_CSV_PATH: path to CSV; defaults to the local seed file.
"""

import csv
import os
from datetime import datetime, timezone

from app.db.connection import get_conn


SEED_DEFAULT = os.path.join(
    os.path.dirname(__file__), "..", "app", "db", "seeds", "pluto_sample.csv"
)


def _now_utc_iso():
    return datetime.now(timezone.utc).isoformat()


def ingest(csv_path: str | None = None) -> int:
    path = csv_path or os.getenv("PLUTO_CSV_PATH") or SEED_DEFAULT
    inserted = 0
    with open(path, newline="", encoding="utf-8") as f, get_conn() as conn:
        reader = csv.DictReader(f)
        with conn.cursor() as cur:
            for row in reader:
                # Map PLUTO-like columns to parcels schema
                params = {
                    "bbl": row["bbl"],
                    "address_std": row.get("address") or row.get("address_std"),
                    "borough": row.get("borough"),
                    "block": int(row["block"]) if row.get("block") else None,
                    "lot": int(row["lot"]) if row.get("lot") else None,
                    "bin": int(row["bin"]) if row.get("bin") else None,
                    "land_use": str(row.get("landuse")) if row.get("landuse") else None,
                    "tax_class": str(row.get("taxclass")) if row.get("taxclass") else None,
                    "lot_area_sqft": int(row["lotarea"]) if row.get("lotarea") else None,
                    "bldg_sqft": int(row["bldgarea"]) if row.get("bldgarea") else None,
                    "stories": int(float(row["numfloors"])) if row.get("numfloors") else None,
                    "year_built": int(row["yearbuilt"]) if row.get("yearbuilt") else None,
                    "last_updated": _now_utc_iso(),
                }
                cur.execute(
                    """
                    INSERT INTO parcels (
                        bbl, address_std, borough, block, lot, bin,
                        land_use, tax_class, lot_area_sqft, bldg_sqft,
                        stories, year_built, last_updated
                    ) VALUES (
                        %(bbl)s, %(address_std)s, %(borough)s, %(block)s, %(lot)s, %(bin)s,
                        %(land_use)s, %(tax_class)s, %(lot_area_sqft)s, %(bldg_sqft)s,
                        %(stories)s, %(year_built)s, %(last_updated)s
                    )
                    ON CONFLICT (bbl) DO UPDATE SET
                        address_std = EXCLUDED.address_std,
                        borough = EXCLUDED.borough,
                        block = EXCLUDED.block,
                        lot = EXCLUDED.lot,
                        bin = EXCLUDED.bin,
                        land_use = EXCLUDED.land_use,
                        tax_class = EXCLUDED.tax_class,
                        lot_area_sqft = EXCLUDED.lot_area_sqft,
                        bldg_sqft = EXCLUDED.bldg_sqft,
                        stories = EXCLUDED.stories,
                        year_built = EXCLUDED.year_built,
                        last_updated = EXCLUDED.last_updated
                    ;
                    """,
                    params,
                )
                inserted += 1
        conn.commit()
    return inserted


if __name__ == "__main__":
    count = ingest()
    print(f"Ingested rows: {count}")
