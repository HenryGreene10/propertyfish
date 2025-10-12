"""ZoLa/DCP zoning ingest (Sprint C)."""

import csv
import os
from datetime import datetime, timezone

from app.db.connection import get_conn


SEED_DEFAULT = os.path.join(
    os.path.dirname(__file__), "..", "app", "db", "seeds", "zoning_sample.csv"
)


def _split_array(val: str | None):
    if val is None:
        return []
    return [x.strip() for x in str(val).split(",") if x.strip()]


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def ingest(csv_path: str | None = None) -> int:
    path = csv_path or os.getenv("ZONING_CSV_PATH") or SEED_DEFAULT
    count = 0
    with open(path, newline="", encoding="utf-8") as f, get_conn() as conn:
        reader = csv.DictReader(f)
        with conn.cursor() as cur:
            for row in reader:
                params = {
                    "bbl": row.get("bbl"),
                    "base_codes": _split_array(row.get("base_codes")),
                    "overlays": _split_array(row.get("overlays")),
                    "sp_districts": _split_array(row.get("sp_districts")),
                    "far_notes": row.get("far_notes"),
                    "last_updated": _now_iso(),
                }
                cur.execute(
                    """
                    INSERT INTO zoning_layers (bbl, base_codes, overlays, sp_districts, far_notes, last_updated)
                    VALUES (%(bbl)s, %(base_codes)s, %(overlays)s, %(sp_districts)s, %(far_notes)s, %(last_updated)s)
                    ON CONFLICT (bbl) DO UPDATE SET
                        base_codes=EXCLUDED.base_codes,
                        overlays=EXCLUDED.overlays,
                        sp_districts=EXCLUDED.sp_districts,
                        far_notes=EXCLUDED.far_notes,
                        last_updated=EXCLUDED.last_updated
                    """,
                    params,
                )
                count += 1
        conn.commit()
    return count


if __name__ == "__main__":
    print(f"Ingested zoning rows: {ingest()}")
