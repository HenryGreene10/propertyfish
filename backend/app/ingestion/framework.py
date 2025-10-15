import json
import os
import random
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
except ImportError as exc:
    raise ImportError(
        "PyYAML not installed. Activate your venv and run: pip install pyyaml"
    ) from exc
from sqlalchemy import text

from app.ingestion.common import insert_staging, row_hash, socrata_fetch
from app.ingestion.normalizers import (
    normalize_acris_legal,
    normalize_acris_mortgage,
    normalize_dob_permit,
    normalize_dob_violation,
    normalize_hpd_registration,
    normalize_hpd_violation,
    normalize_pluto,
)

CATALOG_PATH = Path(__file__).resolve().parent / "catalog.yml"
DATE_FIELD_CANDIDATES = [
    "updated_at",
    "filing_date",
    "filed_date",
    "issuance_date",
    "latest_status_date",
    "record_date",
    "recorded_date",
    "issue_date",
    "inspection_date",
    "date",
]
DEFAULT_MIN_SLEEP_MS = int(os.getenv("POLITE_MIN_SLEEP_MS", "200"))
DEFAULT_MAX_SLEEP_MS = int(os.getenv("POLITE_MAX_SLEEP_MS", "600"))

NORMALIZERS = {
    "normalize_dob_permit": normalize_dob_permit,
    "normalize_dob_violation": normalize_dob_violation,
    "normalize_hpd_violation": normalize_hpd_violation,
    "normalize_hpd_registration": normalize_hpd_registration,
    "normalize_acris_legal": normalize_acris_legal,
    "normalize_acris_mortgage": normalize_acris_mortgage,
    "normalize_pluto": normalize_pluto,
}

_CATALOG_CACHE: Optional[Dict[str, Dict[str, Any]]] = None


def get_catalog() -> Dict[str, Dict[str, Any]]:
    global _CATALOG_CACHE
    if _CATALOG_CACHE is None:
        with CATALOG_PATH.open("r", encoding="utf-8") as stream:
            loaded = yaml.safe_load(stream) or {}
        if not isinstance(loaded, dict):
            raise ValueError("Ingestion catalog must be a mapping")
        _CATALOG_CACHE = loaded
    return _CATALOG_CACHE


def run_job(conn, name: str, days_back: int = 3, page_size: int = 50000) -> None:
    catalog = get_catalog()
    entry = catalog.get(name)
    if not entry:
        raise ValueError(f"Ingestion job '{name}' is not defined in catalog.")

    resource_id = _resolve_resource(entry)
    date_field = _resolve_date_field(entry, resource_id)
    pk_field = entry["pk"]
    staging_table = entry["staging_table"]
    final_table = entry["final_table"]
    normalizer = NORMALIZERS.get(entry.get("normalizer"))

    days_back = int(days_back)
    page_size = int(page_size)
    _ensure_watermarks(conn)
    _ensure_staging_table(conn, staging_table)
    _ensure_final_table(conn, final_table, pk_field)

    start_date = date.today() - timedelta(days=days_back)
    offset = 0
    last_seen_at: Optional[datetime] = None
    more_data = True

    while more_data:
        params = {
            "$limit": page_size,
            "$offset": offset,
        }
        if date_field:
            params["$order"] = f"{date_field} DESC"
            params["$where"] = f"{date_field} >= '{start_date.isoformat()}T00:00:00.000'"

        params = {k: v for k, v in params.items() if v is not None}
        rows = socrata_fetch(resource_id, params)
        if not rows:
            break

        page_max_seen: Optional[datetime] = None
        for row in rows:
            source_pk = _extract_primary_key(row, pk_field)
            insert_staging(conn, staging_table, source_pk, row)

            if normalizer:
                normalized = normalizer(row) or {}
                record_pk = normalized.get(pk_field)
                if record_pk:
                    _upsert_final(conn, final_table, pk_field, normalized)

            seen_value = _coerce_datetime(row.get(date_field)) if date_field else None
            if seen_value and (page_max_seen is None or seen_value > page_max_seen):
                page_max_seen = seen_value

        last_seen_at = page_max_seen or last_seen_at
        offset += len(rows)
        _update_watermark(conn, name, offset, last_seen_at, date_field, note="page processed")

        if len(rows) < page_size:
            more_data = False
        _polite_sleep()

    _update_watermark(conn, name, offset, last_seen_at, date_field, note="job complete")

    if entry.get("refresh_mv"):
        conn.execute(text("REFRESH MATERIALIZED VIEW mv_property_activity"))


def _resolve_resource(entry: Dict[str, Any]) -> str:
    env_key = entry["env_resource"]
    resource_id = os.getenv(env_key)
    if not resource_id:
        raise RuntimeError(
            f"Environment variable '{env_key}' is required for ingestion job."
        )
    return resource_id


def _resolve_date_field(entry: Dict[str, Any], resource_id: str) -> Optional[str]:
    env_key = entry.get("env_date_field")
    if env_key:
        env_value = os.getenv(env_key)
        if env_value:
            return env_value

    # Probe the dataset to find a suitable date field
    try:
        sample = socrata_fetch(resource_id, {"$limit": 1})
    except Exception:
        sample = []
    if sample:
        keys = set(sample[0].keys())
        for candidate in DATE_FIELD_CANDIDATES:
            if candidate in keys:
                return candidate
    return None


def _extract_primary_key(row: Dict[str, Any], pk_field: str) -> str:
    value = row.get(pk_field)
    if value not in (None, "", "N/A"):
        return str(value)
    return row_hash(row)


def _upsert_final(conn, table: str, pk_field: str, record: Dict[str, Any]) -> None:
    table_name = _safe_identifier(table)
    pk_column = _safe_identifier(pk_field)
    payload = dict(record)
    raw_payload = payload.pop("raw", record)
    if pk_field not in payload or payload[pk_field] in (None, "", "N/A"):
        return

    insert_columns = list(payload.keys()) + ["raw"]
    params = {**payload, "raw": json.dumps(raw_payload, sort_keys=True)}
    column_sql = ", ".join(_safe_identifier(col) for col in insert_columns)
    values_sql = ", ".join(
        f":{col}" if col != "raw" else ":raw::jsonb" for col in insert_columns
    )
    update_assignments = [
        f"{_safe_identifier(col)} = EXCLUDED.{_safe_identifier(col)}"
        for col in insert_columns
        if col != pk_field
    ]
    update_assignments.append("updated_at = now()")
    update_sql = ", ".join(update_assignments)

    conn.execute(
        text(
            f"""
            INSERT INTO {table_name} ({column_sql})
            VALUES ({values_sql})
            ON CONFLICT ({pk_column}) DO UPDATE SET
            {update_sql}
            """
        ),
        params,
    )


def _ensure_staging_table(conn, table: str) -> None:
    name = _safe_identifier(table)
    conn.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {name} (
              id BIGSERIAL PRIMARY KEY,
              source_pk TEXT NOT NULL,
              payload JSONB NOT NULL,
              pulled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              row_hash TEXT NOT NULL,
              UNIQUE (row_hash)
            )
            """
        )
    )


def _ensure_final_table(conn, table: str, pk_field: str) -> None:
    table_name = _safe_identifier(table)
    pk_column = _safe_identifier(pk_field)
    conn.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
              {pk_column} TEXT PRIMARY KEY,
              raw JSONB,
              updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )


def _ensure_watermarks(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS ingestion_watermarks (
              source TEXT PRIMARY KEY,
              last_cursor BIGINT,
              last_seen_at TIMESTAMPTZ,
              last_run TIMESTAMPTZ,
              notes TEXT
            )
            """
        )
    )
    conn.execute(
        text(
            """
            ALTER TABLE ingestion_watermarks
            ADD COLUMN IF NOT EXISTS last_cursor BIGINT,
            ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS last_run TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS notes TEXT
            """
        )
    )


def _update_watermark(
    conn,
    source: str,
    cursor: int,
    last_seen_at: Optional[datetime],
    date_field: Optional[str],
    note: str = "",
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO ingestion_watermarks (source, last_cursor, last_seen_at, last_run, notes)
            VALUES (:source, :cursor, :last_seen_at, now(), :notes)
            ON CONFLICT (source) DO UPDATE SET
              last_cursor = EXCLUDED.last_cursor,
              last_seen_at = COALESCE(EXCLUDED.last_seen_at, ingestion_watermarks.last_seen_at),
              last_run = EXCLUDED.last_run,
              notes = EXCLUDED.notes
            """
        ),
        {
            "source": source,
            "cursor": cursor,
            "last_seen_at": last_seen_at,
            "notes": f"{note}; date_field={date_field}",
        },
    )


def _coerce_datetime(value: Any) -> Optional[datetime]:
    if value in (None, "", "N/A"):
        return None
    if isinstance(value, datetime):
        return value
    text_value = str(value).strip()
    if not text_value:
        return None
    if text_value.endswith("Z"):
        text_value = text_value[:-1]
    try:
        return datetime.fromisoformat(text_value)
    except ValueError:
        try:
            return datetime.strptime(text_value, "%Y-%m-%d").replace(tzinfo=None)
        except ValueError:
            return None


def _polite_sleep() -> None:
    lower = min(DEFAULT_MIN_SLEEP_MS, DEFAULT_MAX_SLEEP_MS)
    upper = max(DEFAULT_MIN_SLEEP_MS, DEFAULT_MAX_SLEEP_MS)
    delay = random.uniform(lower, upper) / 1000.0
    time.sleep(delay)


def _safe_identifier(name: str) -> str:
    if not name:
        raise ValueError("Identifier cannot be empty.")
    parts = name.split(".")
    for part in parts:
        if not all(ch.isalnum() or ch == "_" for ch in part):
            raise ValueError(f"Unsafe identifier: {name}")
    return ".".join(parts)
