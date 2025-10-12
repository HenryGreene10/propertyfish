"""DOB permits/violations ingest (Sprint C)."""

import csv
import os
from datetime import datetime, timezone

from app.db.connection import get_conn


BASE_DIR = os.path.dirname(__file__)
SEED_PERMITS = os.path.join(BASE_DIR, "..", "app", "db", "seeds", "dob_permits_sample.csv")
SEED_VIOLS = os.path.join(BASE_DIR, "..", "app", "db", "seeds", "dob_violations_sample.csv")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ingest_permits(csv_path: str | None = None) -> int:
    path = csv_path or os.getenv("DOB_PERMITS_CSV_PATH") or SEED_PERMITS
    count = 0
    with open(path, newline="", encoding="utf-8") as f, get_conn() as conn:
        reader = csv.DictReader(f)
        with conn.cursor() as cur:
            for row in reader:
                params = {
                    "bbl": row.get("bbl"),
                    "kind": "permit",
                    "filed_at": row.get("filed_at"),
                    "job_type": row.get("job_type"),
                    "status": row.get("status"),
                    "description": row.get("description"),
                    "initial_cost": row.get("initial_cost"),
                    "last_updated": _now_iso(),
                }
                # Upsert heuristic by (bbl, kind, filed_at, description)
                cur.execute(
                    """
                    UPDATE permits_violations
                    SET details = jsonb_build_object(
                            'job_type', %(job_type)s,
                            'status', %(status)s,
                            'description', %(description)s,
                            'initial_cost', %(initial_cost)s
                        ),
                        last_updated = %(last_updated)s
                    WHERE bbl=%(bbl)s AND kind='permit' AND filed_at=%(filed_at)s AND (details->>'description') = %(description)s
                    """,
                    params,
                )
                if cur.rowcount == 0:
                    cur.execute(
                        """
                        INSERT INTO permits_violations (
                            bbl, kind, status, filed_at, details, last_updated
                        ) VALUES (
                            %(bbl)s, 'permit', %(status)s, %(filed_at)s,
                            jsonb_build_object('job_type', %(job_type)s, 'status', %(status)s, 'description', %(description)s, 'initial_cost', %(initial_cost)s),
                            %(last_updated)s
                        )
                        """,
                        params,
                    )
                count += 1
        conn.commit()
    return count


def ingest_violations(csv_path: str | None = None) -> int:
    path = csv_path or os.getenv("DOB_VIOLATIONS_CSV_PATH") or SEED_VIOLS
    count = 0
    with open(path, newline="", encoding="utf-8") as f, get_conn() as conn:
        reader = csv.DictReader(f)
        with conn.cursor() as cur:
            for row in reader:
                # Store issued_at in filed_at column to avoid schema migration; expose as issued_at in API
                params = {
                    "bbl": row.get("bbl"),
                    "kind": "violation",
                    "issued_at": row.get("issued_at"),
                    "code": row.get("code"),
                    "status": row.get("status"),
                    "description": row.get("description"),
                    "last_updated": _now_iso(),
                }
                cur.execute(
                    """
                    UPDATE permits_violations
                    SET status=%(status)s,
                        filed_at=%(issued_at)s,
                        details = jsonb_build_object('code', %(code)s, 'status', %(status)s, 'description', %(description)s),
                        last_updated=%(last_updated)s
                    WHERE bbl=%(bbl)s AND kind='violation' AND filed_at=%(issued_at)s AND (details->>'description') = %(description)s
                    """,
                    params,
                )
                if cur.rowcount == 0:
                    cur.execute(
                        """
                        INSERT INTO permits_violations (
                            bbl, kind, status, filed_at, details, last_updated
                        ) VALUES (
                            %(bbl)s, 'violation', %(status)s, %(issued_at)s,
                            jsonb_build_object('code', %(code)s, 'status', %(status)s, 'description', %(description)s),
                            %(last_updated)s
                        )
                        """,
                        params,
                    )
                count += 1
        conn.commit()
    return count


if __name__ == "__main__":
    permits = ingest_permits()
    violations = ingest_violations()
    print(f"Ingested permits={permits}, violations={violations}")
