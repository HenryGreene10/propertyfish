"""ACRIS ingest (Sprint B)

Reads CSV and upserts deed/mortgage events into acris_events.

Env:
- ACRIS_CSV_PATH: CSV path; defaults to local seed file.
"""

import csv
import os
from datetime import datetime, timezone

from app.db.connection import get_conn


SEED_DEFAULT = os.path.join(
    os.path.dirname(__file__), "..", "app", "db", "seeds", "acris_sample.csv"
)


def _normalize_doc_type(value: str | None) -> str | None:
    if not value:
        return None
    v = value.lower()
    if "deed" in v:
        return "deed"
    if "mortgage" in v:
        return "mortgage"
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ingest(csv_path: str | None = None) -> int:
    path = csv_path or os.getenv("ACRIS_CSV_PATH") or SEED_DEFAULT
    count = 0
    with open(path, newline="", encoding="utf-8") as f, get_conn() as conn:
        reader = csv.DictReader(f)
        with conn.cursor() as cur:
            for row in reader:
                doc_type = _normalize_doc_type(row.get("doc_type"))
                if not doc_type:
                    continue  # skip unsupported types
                params = {
                    "bbl": row.get("bbl"),
                    "doc_type": doc_type,
                    "recorded_at": row.get("recorded_at"),
                    "consideration": row.get("consideration") or None,
                    "party_1": row.get("party_1"),
                    "party_2": row.get("party_2"),
                    "doc_id": row.get("doc_id"),
                    "doc_url": row.get("doc_url"),
                    "last_updated": _now_iso(),
                }
                # Manual upsert by doc_id (no unique constraint in schema)
                cur.execute(
                    """
                    UPDATE acris_events
                    SET bbl=%(bbl)s, doc_type=%(doc_type)s, recorded_at=%(recorded_at)s,
                        consideration=%(consideration)s,
                        parties=jsonb_build_object('party_1', %(party_1)s, 'party_2', %(party_2)s),
                        doc_url=%(doc_url)s, last_updated=%(last_updated)s
                    WHERE doc_id=%(doc_id)s
                    """,
                    params,
                )
                if cur.rowcount == 0:
                    cur.execute(
                        """
                        INSERT INTO acris_events (
                            bbl, doc_type, recorded_at, consideration, parties,
                            doc_id, doc_url, last_updated
                        ) VALUES (
                            %(bbl)s, %(doc_type)s, %(recorded_at)s, %(consideration)s,
                            jsonb_build_object('party_1', %(party_1)s, 'party_2', %(party_2)s),
                            %(doc_id)s, %(doc_url)s, %(last_updated)s
                        )
                        """,
                        params,
                    )
                count += 1
        conn.commit()
    return count


if __name__ == "__main__":
    print(f"Ingested rows: {ingest()}")
