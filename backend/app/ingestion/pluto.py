import csv
import hashlib
import io
import json
import logging
import os
import zipfile
from pathlib import Path
from collections.abc import Iterable
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from psycopg2.extras import execute_values
from requests import RequestException

from app.ingestion.normalizers import (
    canonicalize_headers,
    derive_houseno_street,
    normalize_pluto_row,
    to_borough,
    to_float,
)
from app.utils.activity_log import log_activity

logger = logging.getLogger(__name__)

ZIP_PATH = Path("/tmp/pluto.zip")
FILES_FOR_LOG = ["backend/app/ingestion/pluto.py"]
REQUIRED_FOR_INGEST = {"bbl"}


def run(raw_conn, dry_run: bool = False) -> int:
    """Ingest PLUTO rows from the downloaded ZIP."""
    url = os.getenv("PLUTO_URL", "")
    log_activity(
        FILES_FOR_LOG,
        "PLUTO ingest",
        {"event": "pluto_ingest_start", "url": url, "zip_path": str(ZIP_PATH), "dry_run": dry_run},
    )

    zip_path = _ensure_zip(url)
    member = _csv_member_in_zip(zip_path)
    log_activity(
        FILES_FOR_LOG,
        "PLUTO ingest",
        {"event": "pluto_zip_member", "member": member},
    )

    raw_headers, row_iter = _iter_member_rows(zip_path, member)
    header_map, canonical_headers = canonicalize_headers(raw_headers)
    log_activity(
        FILES_FOR_LOG,
        "PLUTO ingest",
        {"event": "pluto_headers", "raw": raw_headers, "canonical": canonical_headers},
    )

    if not _required_ok(set(canonical_headers)):
        missing = sorted(REQUIRED_FOR_INGEST - set(canonical_headers))
        raise RuntimeError(f"PLUTO CSV missing required columns: {', '.join(missing)}")

    use_bbl_pk = os.getenv("USE_BBL_AS_PK", "true").lower() != "false"

    batch: List[Dict[str, Any]] = []
    batch_size = 1000
    total = 0
    inserted_total = 0
    skipped: Dict[str, int] = {"missing_bbl": 0, "no_rowhash": 0}

    with raw_conn.cursor() as cur:
        for raw_row in row_iter:
            total += 1
            canonical_row = _canonicalize_row(raw_row, raw_headers, header_map)
            normalized = normalize_pluto_row(canonical_row)

            bbl = (normalized.get("bbl") or "").strip()
            if not bbl:
                skipped["missing_bbl"] += 1
                continue

            if use_bbl_pk:
                rowhash = hashlib.sha1(bbl.upper().encode("utf-8")).hexdigest()
            else:
                base = "|".join(
                    str(normalized.get(field) or "").upper()
                    for field in ("borough", "houseno", "street", "zipcode", "bbl")
                )
                rowhash = hashlib.sha1(base.encode("utf-8")).hexdigest()

            if not rowhash:
                skipped["no_rowhash"] += 1
                continue

            normalized["rowhash"] = rowhash
            normalized["__raw__"] = raw_row
            batch.append(normalized)

            if len(batch) >= batch_size:
                inserted_total += _insert_staging(cur, batch)
                log_activity(
                    FILES_FOR_LOG,
                    "PLUTO ingest",
                    {"event": "batch_insert", "rows": len(batch)},
                )
                batch.clear()

        if batch:
            inserted_total += _insert_staging(cur, batch)
            log_activity(
                FILES_FOR_LOG,
                "PLUTO ingest",
                {"event": "batch_insert", "rows": len(batch)},
            )
            batch.clear()

        if dry_run:
            raw_conn.rollback()
        else:
            upserted = _promote_staging(raw_conn)
            raw_conn.commit()
            log_activity(
                FILES_FOR_LOG,
                "PLUTO ingest",
                {"event": "pluto_canonical_upsert", "rows": upserted},
            )

    log_activity(
        FILES_FOR_LOG,
        "PLUTO ingest",
        {
            "event": "pluto_normalize_summary",
            "rows_total": total,
            "rows_inserted": inserted_total,
            "skipped": skipped,
        },
    )
    log_activity(
        FILES_FOR_LOG,
        "PLUTO ingest",
        {"event": "pluto_done", "total": total},
    )
    return total


def _ensure_zip(url: str) -> Path:
    """Ensure the PLUTO ZIP is present at ZIP_PATH."""
    if ZIP_PATH.exists():
        return ZIP_PATH
    if not url:
        raise RuntimeError("PLUTO_URL is required to download PLUTO data.")
    _download_zip(url)
    return ZIP_PATH


def _download_zip(url: str) -> None:
    try:
        with requests.get(url, stream=True, timeout=120) as resp:
            resp.raise_for_status()
            with ZIP_PATH.open("wb") as fh:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        fh.write(chunk)
    except RequestException as exc:
        raise RuntimeError(
            f"Failed to download MapPLUTO archive from {url}. Check network connectivity or set PLUTO_URL explicitly."
        ) from exc


def _csv_member_in_zip(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if name.lower().endswith(".csv"):
                return name
    raise RuntimeError("No CSV found in PLUTO ZIP")


def _iter_member_rows(zip_path: Path, member: str) -> Tuple[List[str], Iterable[Dict[str, Any]]]:
    zf = zipfile.ZipFile(zip_path)
    fh = zf.open(member, "r")
    txt = io.TextIOWrapper(fh, encoding="utf-8", newline="")
    reader = csv.reader(txt)

    try:
        raw_headers = next(reader)
    except StopIteration as exc:
        txt.close()
        fh.close()
        zf.close()
        raise RuntimeError("PLUTO CSV is empty.") from exc

    clean_headers = [(header or "").strip() for header in raw_headers]

    def generator():
        try:
            for row in reader:
                if len(row) < len(clean_headers):
                    row.extend([""] * (len(clean_headers) - len(row)))
                elif len(row) > len(clean_headers):
                    row = row[: len(clean_headers)]
                yield {clean_headers[idx]: value for idx, value in enumerate(row)}
        finally:
            txt.close()
            fh.close()
            zf.close()

    return clean_headers, generator()


def _canonicalize_row(row: Dict[str, Any], raw_headers: List[str], header_map: Dict[int, str]) -> Dict[str, Any]:
    canonical: Dict[str, Any] = {}
    for idx, canonical_name in header_map.items():
        if idx >= len(raw_headers):
            continue
        raw_key = raw_headers[idx]
        canonical[canonical_name] = row.get(raw_key)
    # Ensure direct keys also available
    for canonical_name in header_map.values():
        if canonical_name not in canonical and canonical_name in row:
            canonical[canonical_name] = row[canonical_name]
    if canonical.get("address") and (not canonical.get("houseno") or not canonical.get("street")):
        houseno, street = derive_houseno_street(canonical.get("address"))
        canonical.setdefault("houseno", houseno)
        canonical.setdefault("street", street)
    return canonical


def _required_ok(fields: set[str]) -> bool:
    needed = set(REQUIRED_FOR_INGEST)
    return needed.issubset(fields)


def _insert_staging(cur, batch: List[Dict[str, Any]]) -> int:
    sql = """
    INSERT INTO pluto_staging (
      rowhash,
      bbl,
      borough,
      houseno,
      street,
      zipcode,
      latitude,
      longitude,
      raw
    )
    VALUES %s
    ON CONFLICT (rowhash) DO NOTHING
    """
    values = [
        (
            row.get("rowhash"),
            row.get("bbl"),
            to_borough(row.get("borough")),
            row.get("houseno"),
            row.get("street"),
            row.get("zipcode"),
            to_float(row.get("latitude")),
            to_float(row.get("longitude")),
            json.dumps(row.get("__raw__", row), ensure_ascii=False),
        )
        for row in batch
        if row.get("rowhash")
    ]
    if values:
        execute_values(cur, sql, values)
    return len(values)


def _promote_staging(conn) -> int:
    sql = """
    INSERT INTO pluto AS t (
      rowhash,
      bbl,
      address,
      zipcode,
      borough,
      houseno,
      street,
      latitude,
      longitude,
      raw
    )
    SELECT
      s.rowhash,
      s.bbl,
      NULLIF(TRIM(CONCAT_WS(' ', s.houseno, s.street)), ''),
      s.zipcode,
      s.borough,
      s.houseno,
      s.street,
      s.latitude,
      s.longitude,
      s.raw
    FROM pluto_staging s
    ON CONFLICT (rowhash) DO UPDATE
      SET bbl = EXCLUDED.bbl,
          address = EXCLUDED.address,
          zipcode = EXCLUDED.zipcode,
          borough = EXCLUDED.borough,
          houseno = EXCLUDED.houseno,
          street = EXCLUDED.street,
          latitude = EXCLUDED.latitude,
          longitude = EXCLUDED.longitude,
          raw = EXCLUDED.raw,
          updated_at = now()
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        affected = cur.rowcount
    return affected
