"""Populate the pluto_attrs table from a PLUTO CSV using the configured DATABASE_URL."""

from __future__ import annotations

import csv
import os
import sys
import zipfile
from collections.abc import Iterable
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any, List, Sequence, Tuple

import psycopg2
from psycopg2.extras import execute_values
import requests


BATCH_SIZE = 1000
PROGRESS_INTERVAL = 10_000


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"{name} environment variable is required")
    return value


@contextmanager
def db_connection(dsn: str):
    conn = psycopg2.connect(dsn)
    try:
        yield conn
    finally:
        conn.close()


def ensure_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS pluto_attrs (
              bbl        text PRIMARY KEY,
              yearbuilt  integer,
              numfloors  numeric,
              unitsres   integer,
              unitstotal integer,
              zonedist1  text,
              landuse    text,
              bldgarea   integer,
              lotarea    integer
            )
            """
        )
    conn.commit()


def download_zip(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 15):
                if chunk:
                    fh.write(chunk)
    return dest


def extract_csv(zip_path: Path, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        csv_names = [name for name in zf.namelist() if name.lower().endswith(".csv")]
        if not csv_names:
            raise RuntimeError("No CSV file found in PLUTO archive")
        csv_name = csv_names[0]
        zf.extract(csv_name, path=target_dir)
        return target_dir / csv_name


def parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def parse_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return Decimal(value)
    except Exception:
        return None


def upsert_batch(conn, rows: Sequence[Tuple[Any, ...]]) -> Tuple[int, int]:
    if not rows:
        return 0, 0
    sql = """
        INSERT INTO pluto_attrs (
          bbl, yearbuilt, numfloors, unitsres, unitstotal,
          zonedist1, landuse, bldgarea, lotarea
        ) VALUES %s
        ON CONFLICT (bbl) DO UPDATE SET
          yearbuilt = EXCLUDED.yearbuilt,
          numfloors = EXCLUDED.numfloors,
          unitsres = EXCLUDED.unitsres,
          unitstotal = EXCLUDED.unitstotal,
          zonedist1 = EXCLUDED.zonedist1,
          landuse = EXCLUDED.landuse,
          bldgarea = EXCLUDED.bldgarea,
          lotarea = EXCLUDED.lotarea
        RETURNING (xmax = 0) AS inserted
    """
    with conn.cursor() as cur:
        result = execute_values(cur, sql, rows, fetch=True)
    conn.commit()
    inserted = sum(1 for (flag,) in result if flag)
    total = len(result)
    updated = total - inserted
    return inserted, updated


def build_record(row: dict[str, str | None]) -> Tuple[Any, ...] | None:
    bbl = (row.get("bbl") or "").strip()
    if not bbl:
        return None
    return (
        bbl,
        parse_int(row.get("yearbuilt")),
        parse_decimal(row.get("numfloors")),
        parse_int(row.get("unitsres")),
        parse_int(row.get("unitstotal")),
        (row.get("zonedist1") or None),
        (row.get("landuse") or None),
        parse_int(row.get("bldgarea")),
        parse_int(row.get("lotarea")),
    )


def main() -> None:
    database_url = require_env("DATABASE_URL")
    pluto_url = require_env("PLUTO_URL")
    pluto_version = require_env("PLUTO_VERSION")
    data_dir = Path(os.getenv("DATA_DIR", "./data")).resolve()

    zip_path = data_dir / f"pluto_{pluto_version}.zip"
    extract_dir = data_dir / f"pluto_{pluto_version}"

    print(f"Downloading PLUTO archive from {pluto_url} -> {zip_path}")
    download_zip(pluto_url, zip_path)

    print(f"Extracting archive to {extract_dir}")
    csv_path = extract_csv(zip_path, extract_dir)
    print(f"Reading CSV from {csv_path}")

    total_inserted = 0
    total_updated = 0
    processed = 0

    with db_connection(database_url) as conn:
        ensure_table(conn)

        batch: List[Tuple[Any, ...]] = []
        with open(csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                record = build_record(row)
                if not record:
                    continue
                batch.append(record)
                processed += 1

                if processed % PROGRESS_INTERVAL == 0:
                    print(f"Processed {processed:,} rows...")

                if len(batch) >= BATCH_SIZE:
                    inserted, updated = upsert_batch(conn, batch)
                    total_inserted += inserted
                    total_updated += updated
                    batch.clear()

        if batch:
            inserted, updated = upsert_batch(conn, batch)
            total_inserted += inserted
            total_updated += updated

    print(
        f"Finished PLUTO ingest. Inserted {total_inserted:,} rows, updated {total_updated:,} rows."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise

