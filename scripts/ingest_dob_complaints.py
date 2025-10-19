#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from psycopg2.extras import execute_values

from scripts.util_bbl import normalize_bbl

DEFAULT_RESOURCE_ID = "eabe-havv"
SOURCE_NAME = "dob_complaints_v1"
SOURCE_VERSION = "dob_complaints_v1"
DEFAULT_PAGE_LIMIT = 50000
DAYS_BACK_DEFAULT = 7
MAX_RETRIES = 5
RETRY_STATUS = {429, 500, 502, 503, 504}
BACKOFF_INITIAL_SECONDS = 2.0
BACKOFF_MAX_SECONDS = 60.0
REQUEST_TIMEOUT = 60

DATE_FIELD_PREFERENCES = [
    "date_received",
    "date_entered",
    "inspection_date",
    "last_inspection_date",
    "last_status_date",
    "date",
]

DEFAULT_FIELD_CANDIDATES = [
    "complaint_id",
    "complaintid",
    "complaint_number",
    "complaintnumber",
    "complaintno",
    "complaintnum",
    "complaint",
    "bbl",
    "bbl_number",
    "bin",
    "borough",
    "boro",
    "block",
    "block_number",
    "lot",
    "lot_number",
    "house_number",
    "house__",
    "housenumber",
    "street",
    "street_name",
    "streetname",
    "zip",
    "zip_code",
    "apartment",
    "apt",
    "community_board",
    "complaint_category",
    "complaint_type",
    "category",
    "type",
    "status",
    "status_description",
    "priority",
    "disposition",
    "inspector",
    "date_received",
    "date_entered",
    "inspection_date",
    "last_inspection_date",
    "last_status_date",
    "date",
    "latitude",
    "longitude",
    "lat",
    "long",
    "source",
    "complaint_source",
]

BOROUGH_CODES = {
    "1": "1",
    "01": "1",
    "manhattan": "1",
    "mn": "1",
    "new york": "1",
    "2": "2",
    "02": "2",
    "bronx": "2",
    "bx": "2",
    "3": "3",
    "03": "3",
    "brooklyn": "3",
    "bk": "3",
    "kings": "3",
    "4": "4",
    "04": "4",
    "queens": "4",
    "qn": "4",
    "5": "5",
    "05": "5",
    "staten island": "5",
    "si": "5",
    "richmond": "5",
}

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


class SocrataError(Exception):
    def __init__(self, status: Optional[int], body: str, url: str):
        super().__init__(f"Socrata request failed (status={status}, url={url}): {body}")
        self.status = status
        self.body = body
        self.url = url


class SocrataClient:
    def __init__(self, base_url: str, resource_id: str, app_token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.resource_id = resource_id
        self.headers: Dict[str, str] = {"Accept": "application/json"}
        if app_token:
            self.headers["X-App-Token"] = app_token

    def _request(self, url: str, params: Optional[Dict[str, Any]] = None, expect: str = "list"):
        query = ""
        if params:
            query = "?" + urlencode(params, doseq=True)
        attempt = 0
        while True:
            req = Request(url + query, headers=self.headers)
            try:
                with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                    payload = resp.read()
            except HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                if exc.code in RETRY_STATUS and attempt < MAX_RETRIES:
                    delay = min(BACKOFF_MAX_SECONDS, BACKOFF_INITIAL_SECONDS * (2**attempt))
                    time.sleep(delay + random.random())
                    attempt += 1
                    continue
                raise SocrataError(exc.code, body, url + query)
            except URLError as exc:
                body = str(getattr(exc, "reason", exc))
                if attempt < MAX_RETRIES:
                    delay = min(BACKOFF_MAX_SECONDS, BACKOFF_INITIAL_SECONDS * (2**attempt))
                    time.sleep(delay + random.random())
                    attempt += 1
                    continue
                raise SocrataError(None, body, url + query)

            if not payload:
                return [] if expect == "list" else {}
            data = json.loads(payload)

            if expect == "list":
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    if any(k in data for k in ("error", "code", "message")):
                        raise SocrataError(200, json.dumps(data), url + query)
                    return [data]
                raise SocrataError(200, f"Unexpected payload type {type(data).__name__}", url + query)

            if not isinstance(data, dict):
                raise SocrataError(200, f"Unexpected payload type {type(data).__name__}", url + query)
            return data

    def get_view_columns(self) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/api/views/{self.resource_id}.json"
        data = self._request(url, expect="dict")
        return data.get("columns", []) if isinstance(data, dict) else []

    def query_resource(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/resource/{self.resource_id}.json"
        return self._request(url, params=params, expect="list")

    def get_max_value(self, field: str) -> Optional[str]:
        rows = self.query_resource({"$select": f"max({field}) as max_value"})
        if not rows:
            return None
        return rows[0].get("max_value")

    def count_rows(self, where_clause: str) -> int:
        rows = self.query_resource({"$select": "count(1) as count", "$where": where_clause})
        if not rows:
            return 0
        value = rows[0].get("count")
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest DOB complaints from Socrata.")
    parser.add_argument("--since", help="Fetch complaints updated since ISO timestamp (UTC).")
    parser.add_argument("--until", help="Fetch complaints updated before ISO timestamp (UTC).")
    parser.add_argument(
        "--days",
        type=int,
        default=DAYS_BACK_DEFAULT,
        help=f"Fetch complaints within the past N days (default {DAYS_BACK_DEFAULT}).",
    )
    parser.add_argument(
        "--date-field",
        help="Force using this column as the incremental date/timestamp field.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run discovery and counting only; do not write to the database.",
    )
    parser.add_argument(
        "--diagnose-date-fields",
        action="store_true",
        help="Print candidate date fields with recency metrics and exit.",
    )
    parser.add_argument(
        "--page-limit",
        type=int,
        default=DEFAULT_PAGE_LIMIT,
        help=f"Number of rows to request per page (default {DEFAULT_PAGE_LIMIT}).",
    )
    return parser.parse_args()


def load_environment() -> None:
    load_dotenv()
    repo_root = Path(__file__).resolve().parents[1]
    backend_env = repo_root / "backend" / ".env"
    if backend_env.exists():
        load_dotenv(backend_env, override=False)


def get_connection_factory():
    repo_root = Path(__file__).resolve().parents[1]
    backend_path = repo_root / "backend"
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))
    try:
        from app.db.connection import get_conn as conn_factory
    except ImportError as exc:  # pragma: no cover
        raise ImportError("Unable to import database connection helper.") from exc
    return conn_factory


def parse_datetime_arg(value: str) -> datetime:
    text = value.strip()
    try:
        if "T" in text:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        else:
            dt = datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"Invalid ISO date/time: {value!r}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def floor_to_midnight(dt: datetime) -> datetime:
    return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)


def compute_window(
    watermark: datetime,
    since_arg: Optional[str],
    until_arg: Optional[str],
    days: int,
) -> Tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    default_until = floor_to_midnight(now)

    if until_arg:
        until_dt = parse_datetime_arg(until_arg)
        until = floor_to_midnight(until_dt)
    else:
        until = default_until

    if since_arg:
        since_dt = parse_datetime_arg(since_arg)
        since = floor_to_midnight(since_dt)
    else:
        days = max(days, 1)
        since = until - timedelta(days=days)

    since = max(since, watermark or EPOCH)
    if since > until:
        since = until
    return since, until


def format_soql_timestamp(dt: datetime) -> str:
    dt_utc = dt.astimezone(timezone.utc)
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%S.000")


def parse_any_datetime(value: Any) -> Optional[datetime]:
    if value in (None, "", "null", "NULL"):
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def build_available_map(columns: List[Dict[str, Any]]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for column in columns:
        field = column.get("fieldName")
        if field:
            mapping[field.lower()] = field
    return mapping


def build_candidate_fields(columns: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    candidates: List[Tuple[str, str]] = []
    for column in columns:
        field = column.get("fieldName")
        if not field:
            continue
        dtype = (column.get("dataTypeName") or "").lower()
        if dtype in {"calendar_date", "floating_timestamp", "date"}:
            candidates.append((field, dtype))
    return candidates


def order_candidate_fields(fields: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    ordered: List[Tuple[str, str]] = []
    seen: set[str] = set()
    for preferred in DATE_FIELD_PREFERENCES:
        for field, dtype in fields:
            if field.lower() == preferred and field.lower() not in seen:
                ordered.append((field, dtype))
                seen.add(field.lower())
    for field, dtype in fields:
        if field.lower() not in seen:
            ordered.append((field, dtype))
            seen.add(field.lower())
    return ordered


def build_select_fields(date_field: str, available_map: Dict[str, str]) -> List[str]:
    desired = [date_field] + DEFAULT_FIELD_CANDIDATES
    fields: List[str] = []
    seen: set[str] = set()
    for name in desired:
        actual = available_map.get(name.lower())
        if actual and actual.lower() not in seen:
            fields.append(actual)
            seen.add(actual.lower())
    return fields


def count_with_fallback(client: SocrataClient, field: str, since_iso: str, until_iso: str) -> Tuple[int, str]:
    primary = f"{field} >= '{since_iso}' AND {field} < '{until_iso}'"
    try:
        count = client.count_rows(primary)
        return count, primary
    except SocrataError as exc:
        if exc.status == 400:
            print(f"[dob_complaints] 400 using >=/< filter: {exc.body}", file=sys.stderr)
            between = f"{field} between '{since_iso}' and '{until_iso}'"
            try:
                count = client.count_rows(between)
                return count, between
            except SocrataError as exc2:
                if exc2.status == 400:
                    raise RuntimeError(
                        f"SoQL count failed for field '{field}' with SINCE={since_iso}, UNTIL={until_iso}. "
                        f"Errors: primary={exc.body!r}, between={exc2.body!r}"
                    ) from exc2
                raise
        raise


def select_date_field(
    client: SocrataClient,
    columns: List[Dict[str, Any]],
    since_iso: str,
    until_iso: str,
    override: Optional[str],
) -> Tuple[str, Optional[str], int, str]:
    available_map = build_available_map(columns)
    all_column_names = sorted(available_map.values())
    candidates = order_candidate_fields(build_candidate_fields(columns))

    if override:
        actual = available_map.get(override.lower())
        if not actual:
            raise RuntimeError(
                f"Requested date field '{override}' not found. Available columns: {', '.join(all_column_names)}"
            )
        dtype = None
        for column in columns:
            if column.get("fieldName") == actual:
                dtype = (column.get("dataTypeName") or "").lower()
                break
        count, where_clause = count_with_fallback(client, actual, since_iso, until_iso)
        if count == 0:
            print(
                f"[dob_complaints] Warning: field '{actual}' returned 0 rows for window "
                f"[{since_iso},{until_iso}).",
                file=sys.stderr,
            )
        return actual, dtype, count, where_clause

    if not candidates:
        raise RuntimeError(
            "No date-typed columns found in Socrata metadata. "
            f"Available columns: {', '.join(all_column_names)}. Try --date-field."
        )

    freshest_field: Optional[str] = None
    freshest_dt: Optional[datetime] = None
    metadata: Dict[str, Tuple[int, str, str]] = {}
    max_values: Dict[str, Optional[datetime]] = {}

    for field, dtype in candidates:
        try:
            count, where_clause = count_with_fallback(client, field, since_iso, until_iso)
        except SocrataError as exc:
            print(f"[dob_complaints] Skipping field '{field}' (count failed: {exc.body})", file=sys.stderr)
            continue

        metadata[field] = (count, where_clause, dtype)

        if count > 0:
            print(f"[dob_complaints] Selected field '{field}' with {count} rows in window.")
            return field, dtype, count, where_clause

        try:
            max_value = client.get_max_value(field)
        except SocrataError as exc:
            print(f"[dob_complaints] max({field}) lookup failed: {exc.body}", file=sys.stderr)
            max_dt = None
        else:
            max_dt = parse_any_datetime(max_value)
        max_values[field] = max_dt

        if max_dt and (freshest_dt is None or max_dt > freshest_dt):
            freshest_dt = max_dt
            freshest_field = field

    if freshest_field and freshest_field in metadata:
        count, where_clause, dtype = metadata[freshest_field]
        max_dt = max_values.get(freshest_field)
        if max_dt:
            print(
                f"[dob_complaints] Falling back to '{freshest_field}' using max={max_dt.isoformat()} "
                f"(window count={count})."
            )
        else:
            print(
                f"[dob_complaints] Falling back to '{freshest_field}' despite missing recency metadata "
                f"(window count={count})."
            )
        return freshest_field, dtype, count, where_clause

    if metadata:
        field, (count, where_clause, dtype) = next(iter(metadata.items()))
        print(
            f"[dob_complaints] Falling back to field '{field}' (window count={count}) without freshness data."
        )
        return field, dtype, count, where_clause

    raise RuntimeError(
        "No usable date field found for DOB complaints ingestion. "
        f"Available columns: {', '.join(all_column_names)}. Try --date-field."
    )


def diagnose_date_fields(client: SocrataClient) -> None:
    columns = client.get_view_columns()
    available_map = build_available_map(columns)
    candidates = order_candidate_fields(build_candidate_fields(columns))
    all_column_names = sorted(available_map.values())

    if not candidates:
        print(
            "No date-typed columns detected. Available columns:",
            ", ".join(all_column_names),
        )
        print("Pass --date-field <column> to force a specific field.")
        return

    print("Available columns:", ", ".join(all_column_names))
    print("Join key availability:", describe_join_keys(available_map))

    until = floor_to_midnight(datetime.now(timezone.utc))
    until_iso = format_soql_timestamp(until)
    since_7_iso = format_soql_timestamp(until - timedelta(days=7))
    since_30_iso = format_soql_timestamp(until - timedelta(days=30))

    header = f"{'field':<28} | {'type':<18} | {'max(field)':<26} | {'count_7d':<9} | {'count_30d':<10}"
    print(header)
    print("-" * len(header))

    for field, dtype in candidates:
        try:
            max_value = client.get_max_value(field)
            max_dt = parse_any_datetime(max_value)
            max_display = max_dt.isoformat() if max_dt else (max_value or "")
        except SocrataError as exc:
            max_display = f"ERR:{exc.status or ''}"

        try:
            count_7, _ = count_with_fallback(client, field, since_7_iso, until_iso)
            count_7_display = str(count_7)
        except Exception as exc:  # noqa: BLE001
            count_7_display = f"ERR:{getattr(exc, 'status', '')}"

        try:
            count_30, _ = count_with_fallback(client, field, since_30_iso, until_iso)
            count_30_display = str(count_30)
        except Exception as exc:  # noqa: BLE001
            count_30_display = f"ERR:{getattr(exc, 'status', '')}"

        print(
            f"{field:<28} | {dtype or '':<18} | {max_display:<26} | "
            f"{count_7_display:<9} | {count_30_display:<10}"
        )


def normalize_timestamp(value: Any) -> Optional[str]:
    if value in (None, "", "null", "NULL"):
        return None
    text = str(value).strip()
    if not text:
        return None
    processed = text.replace("Z", "+00:00") if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(processed)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        return text


def borough_to_digit(value: Any) -> Optional[str]:
    if value in (None, "", "null", "NULL"):
        return None
    return BOROUGH_CODES.get(str(value).strip().lower())


def compute_bbl_from_parts(boro: Any, block: Any, lot: Any) -> Optional[str]:
    boro_digit = borough_to_digit(boro)
    if not boro_digit:
        return None
    block_digits = "".join(ch for ch in str(block) if ch.isdigit()) if block else ""
    lot_digits = "".join(ch for ch in str(lot) if ch.isdigit()) if lot else ""
    if not block_digits or not lot_digits:
        return None
    return normalize_bbl(f"{boro_digit}{block_digits.zfill(5)}{lot_digits.zfill(4)}")


def resolve_value(row: Dict[str, Any], keys: List[str]) -> Optional[str]:
    for key in keys:
        if key in row and row[key] not in (None, "", "null", "NULL"):
            text = str(row[key]).strip()
            if text:
                return text
    return None


def normalize_float(value: Any) -> Optional[float]:
    if value in (None, "", "null", "NULL"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compute_bbl(row: Dict[str, Any]) -> Optional[str]:
    direct = resolve_value(
        row,
        ["bbl", "bbl_number", "borough_block_lot", "bbl_"],
    )
    normalized = normalize_bbl(direct) if direct else None
    if normalized:
        return normalized
    borough = resolve_value(row, ["borough", "boro"])
    block = resolve_value(row, ["block", "block_number"])
    lot = resolve_value(row, ["lot", "lot_number"])
    return compute_bbl_from_parts(borough, block, lot)


def normalize_row(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    complaint_id_raw = resolve_value(
        row,
        [
            "complaint_number",
            "complaintnumber",
            "complaintid",
            "complaint_id",
            "complaintno",
            "complaintnum",
            "complaint",
        ],
    )
    complaint_id = complaint_id_raw or row.get(":id")
    if complaint_id is None:
        return None
    complaint_id = str(complaint_id).strip()
    if not complaint_id:
        return None

    payload: Dict[str, Any] = {
        "complaint_id": complaint_id,
        "bbl": compute_bbl(row),
        "bin": resolve_value(row, ["bin"]),
        "borough": resolve_value(row, ["borough", "boro"]),
        "house_number": resolve_value(row, ["house_number", "house__", "housenumber"]),
        "street": resolve_value(row, ["street_name", "streetname", "street"]),
        "zip": resolve_value(row, ["zip", "zip_code"]),
        "apartment": resolve_value(row, ["apartment", "apt", "apartment_number"]),
        "community_board": resolve_value(row, ["community_board"]),
        "complaint_category": resolve_value(row, ["complaint_category", "category"]),
        "complaint_type": resolve_value(row, ["complaint_type", "type"]),
        "status": resolve_value(row, ["status", "status_description"]),
        "priority": resolve_value(row, ["priority"]),
        "disposition": resolve_value(row, ["disposition"]),
        "inspector": resolve_value(row, ["inspector"]),
        "date_received": normalize_timestamp(resolve_value(row, ["date_received", "date_entered", "date"])),
        "last_inspection_date": normalize_timestamp(
            resolve_value(row, ["last_inspection_date", "inspection_date"])
        ),
        "last_status_date": normalize_timestamp(
            resolve_value(row, ["last_status_date", "status_date", "lastupdatedate"])
        ),
        "latitude": normalize_float(resolve_value(row, ["latitude", "lat"])),
        "longitude": normalize_float(resolve_value(row, ["longitude", "long", "lng"])),
        "source_version": SOURCE_VERSION,
        "raw": json.dumps(row, sort_keys=True),
    }
    return payload


def ensure_tables(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS dob_complaints__staging (
                complaint_id TEXT PRIMARY KEY,
                bbl TEXT,
                bin TEXT,
                borough TEXT,
                house_number TEXT,
                street TEXT,
                zip TEXT,
                apartment TEXT,
                community_board TEXT,
                complaint_category TEXT,
                complaint_type TEXT,
                status TEXT,
                priority TEXT,
                disposition TEXT,
                inspector TEXT,
                date_received TIMESTAMPTZ,
                last_inspection_date TIMESTAMPTZ,
                last_status_date TIMESTAMPTZ,
                latitude DOUBLE PRECISION,
                longitude DOUBLE PRECISION,
                source_version TEXT,
                raw JSONB NOT NULL,
                loaded_at TIMESTAMPTZ DEFAULT now()
            )
            """
        )


def truncate_staging(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE dob_complaints__staging")


def stage_rows(conn, rows: Iterable[Dict[str, Any]]) -> None:
    values = [
        (
            r["complaint_id"],
            r["bbl"],
            r["bin"],
            r["borough"],
            r["house_number"],
            r["street"],
            r["zip"],
            r["apartment"],
            r["community_board"],
            r["complaint_category"],
            r["complaint_type"],
            r["status"],
            r["priority"],
            r["disposition"],
            r["inspector"],
            r["date_received"],
            r["last_inspection_date"],
            r["last_status_date"],
            r["latitude"],
            r["longitude"],
            r["source_version"],
            r["raw"],
        )
        for r in rows
    ]
    if not values:
        return
    sql = """
        INSERT INTO dob_complaints__staging (
            complaint_id,
            bbl,
            bin,
            borough,
            house_number,
            street,
            zip,
            apartment,
            community_board,
            complaint_category,
            complaint_type,
            status,
            priority,
            disposition,
            inspector,
            date_received,
            last_inspection_date,
            last_status_date,
            latitude,
            longitude,
            source_version,
            raw
        ) VALUES %s
        ON CONFLICT (complaint_id) DO UPDATE SET
            bbl = EXCLUDED.bbl,
            bin = EXCLUDED.bin,
            borough = EXCLUDED.borough,
            house_number = EXCLUDED.house_number,
            street = EXCLUDED.street,
            zip = EXCLUDED.zip,
            apartment = EXCLUDED.apartment,
            community_board = EXCLUDED.community_board,
            complaint_category = EXCLUDED.complaint_category,
            complaint_type = EXCLUDED.complaint_type,
            status = EXCLUDED.status,
            priority = EXCLUDED.priority,
            disposition = EXCLUDED.disposition,
            inspector = EXCLUDED.inspector,
            date_received = EXCLUDED.date_received,
            last_inspection_date = EXCLUDED.last_inspection_date,
            last_status_date = EXCLUDED.last_status_date,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            source_version = EXCLUDED.source_version,
            raw = EXCLUDED.raw,
            loaded_at = now()
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, values)


def upsert_from_staging(conn) -> Tuple[int, int]:
    sql = """
        WITH dedup AS (
            SELECT DISTINCT ON (complaint_id) *
            FROM dob_complaints__staging
            ORDER BY complaint_id,
                     COALESCE(date_received, last_status_date, loaded_at) DESC NULLS LAST
        ),
        upsert AS (
            INSERT INTO dob_complaints (
                complaint_id,
                bbl,
                bin,
                borough,
                house_number,
                street,
                zip,
                apartment,
                community_board,
                complaint_category,
                complaint_type,
                status,
                priority,
                disposition,
                inspector,
                date_received,
                last_inspection_date,
                last_status_date,
                latitude,
                longitude,
                source_version,
                raw,
                updated_at
            )
            SELECT
                complaint_id,
                bbl,
                bin,
                borough,
                house_number,
                street,
                zip,
                apartment,
                community_board,
                complaint_category,
                complaint_type,
                status,
                priority,
                disposition,
                inspector,
                date_received,
                last_inspection_date,
                last_status_date,
                latitude,
                longitude,
                COALESCE(source_version, %s),
                raw,
                now()
            FROM dedup
            ON CONFLICT (complaint_id) DO UPDATE SET
                bbl = EXCLUDED.bbl,
                bin = EXCLUDED.bin,
                borough = EXCLUDED.borough,
                house_number = EXCLUDED.house_number,
                street = EXCLUDED.street,
                zip = EXCLUDED.zip,
                apartment = EXCLUDED.apartment,
                community_board = EXCLUDED.community_board,
                complaint_category = EXCLUDED.complaint_category,
                complaint_type = EXCLUDED.complaint_type,
                status = EXCLUDED.status,
                priority = EXCLUDED.priority,
                disposition = EXCLUDED.disposition,
                inspector = EXCLUDED.inspector,
                date_received = EXCLUDED.date_received,
                last_inspection_date = EXCLUDED.last_inspection_date,
                last_status_date = EXCLUDED.last_status_date,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                source_version = EXCLUDED.source_version,
                raw = EXCLUDED.raw,
                updated_at = now()
            RETURNING (xmax = 0) AS inserted_flag
        )
        SELECT
            COALESCE(SUM(CASE WHEN inserted_flag THEN 1 ELSE 0 END), 0) AS inserted_count,
            COALESCE(SUM(CASE WHEN NOT inserted_flag THEN 1 ELSE 0 END), 0) AS updated_count
        FROM upsert
    """
    with conn.cursor() as cur:
        cur.execute(sql, (SOURCE_VERSION,))
        result = cur.fetchone() or (0, 0)
    return int(result[0] or 0), int(result[1] or 0)


def ensure_watermark_row(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ingestion_watermarks (source, last_run)
            VALUES (%s, %s)
            ON CONFLICT (source) DO NOTHING
            """,
            (SOURCE_NAME, EPOCH),
        )


def fetch_watermark(conn) -> datetime:
    with conn.cursor() as cur:
        cur.execute("SELECT last_run FROM ingestion_watermarks WHERE source = %s", (SOURCE_NAME,))
        row = cur.fetchone()
    if not row:
        return EPOCH
    value = row.get("last_run")
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return EPOCH


def update_watermark(conn, timestamp: datetime) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ingestion_watermarks (source, last_run)
            VALUES (%s, %s)
            ON CONFLICT (source) DO UPDATE SET last_run = EXCLUDED.last_run
            """,
            (SOURCE_NAME, timestamp),
        )


def start_ingest_run(conn, started_at: datetime) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ingest_runs (
                source,
                started_at,
                status,
                rows_inserted,
                rows_updated
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (SOURCE_NAME, started_at, "running", 0, 0),
        )
        return cur.fetchone()[0]


def finalize_ingest_run(
    conn,
    run_id: int,
    finished_at: datetime,
    status: str,
    inserted: int,
    updated: int,
    error: Optional[str],
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE ingest_runs
            SET finished_at = %s,
                status = %s,
                rows_inserted = %s,
                rows_updated = %s,
                error = %s
            WHERE id = %s
            """,
            (
                finished_at,
                status,
                inserted,
                updated,
                (error[:1000] if error else None),
                run_id,
            ),
        )


def get_polite_bounds() -> Tuple[int, int]:
    try:
        min_ms = int(os.getenv("POLITE_MIN_SLEEP_MS", "200"))
    except ValueError:
        min_ms = 200
    try:
        max_ms = int(os.getenv("POLITE_MAX_SLEEP_MS", "600"))
    except ValueError:
        max_ms = 600
    if min_ms < 0:
        min_ms = 0
    if max_ms < min_ms:
        max_ms = min_ms
    return min_ms, max_ms


def polite_sleep(min_ms: int, max_ms: int) -> None:
    if max_ms <= 0:
        return
    duration = random.randint(min_ms, max_ms) / 1000.0 if max_ms >= min_ms else 0
    if duration > 0:
        time.sleep(duration)


def describe_join_keys(available_map: Dict[str, str]) -> str:
    has_bbl = "yes" if "bbl" in available_map else "no"
    has_bin = "yes" if "bin" in available_map else "no"
    has_block = "yes" if any(key in available_map for key in ("block", "block_number")) else "no"
    has_lot = "yes" if any(key in available_map for key in ("lot", "lot_number")) else "no"
    return f"bbl={has_bbl}, bin={has_bin}, block={has_block}, lot={has_lot}"


def print_join_stats(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM dob_complaints WHERE bbl IS NOT NULL")
        with_bbl = cur.fetchone()[0]
        cur.execute(
            """
            SELECT COUNT(*)
            FROM dob_complaints c
            JOIN pluto p ON p.bbl = c.bbl
            """
        )
        joined = cur.fetchone()[0]
    print(f"[dob_complaints] join diagnostics: bbl_count={with_bbl}, pluto_join_count={joined}")


def refresh_materialized_view(conn) -> None:
    try:
        with conn.cursor() as cur:
            cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_property_events__dob_complaints")
        print("[dob_complaints] Refreshed mv_property_events__dob_complaints concurrently.")
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        try:
            with conn.cursor() as cur:
                cur.execute("REFRESH MATERIALIZED VIEW mv_property_events__dob_complaints")
            print("[dob_complaints] Refreshed mv_property_events__dob_complaints (non-concurrent).")
        except Exception as exc2:  # noqa: BLE001
            conn.rollback()
            print(
                f"[dob_complaints] Unable to refresh mv_property_events__dob_complaints automatically: {exc2}",
                file=sys.stderr,
            )


def ingest() -> int:
    args = parse_args()
    load_environment()

    base = os.getenv("NYC_SOCRATA_BASE", "https://data.cityofnewyork.us").rstrip("/")
    resource_id = os.getenv("DOB_COMPLAINTS_RESOURCE_ID", DEFAULT_RESOURCE_ID)
    app_token = os.getenv("NYC_SOCRATA_APP_TOKEN")
    client = SocrataClient(base, resource_id, app_token)

    if args.diagnose_date_fields:
        diagnose_date_fields(client)
        return 0

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is not configured; unable to connect.", file=sys.stderr)
        return 1

    page_limit = max(1, args.page_limit)
    min_sleep_ms, max_sleep_ms = get_polite_bounds()

    conn_factory = get_connection_factory()
    started_at = datetime.now(timezone.utc)
    run_id: Optional[int] = None
    inserted_total = 0
    updated_total = 0

    with conn_factory() as conn:
        try:
            ensure_tables(conn)
            ensure_watermark_row(conn)

            watermark = fetch_watermark(conn)
            since, until = compute_window(watermark, args.since, args.until, args.days)
            since_iso = format_soql_timestamp(since)
            until_iso = format_soql_timestamp(until)
            print(
                f"[dob_complaints] Window request since={since_iso} until={until_iso} "
                f"(watermark={watermark.isoformat()})"
            )

            columns = client.get_view_columns()
            available_map = build_available_map(columns)
            date_field, dtype, window_count, where_clause = select_date_field(
                client, columns, since_iso, until_iso, args.date_field
            )
            print(
                f"[dob_complaints] Selected field {date_field} (type={dtype or 'unknown'}) "
                f"with window count={window_count}"
            )
            print(f"[dob_complaints] using $where: {where_clause}")
            print(f"[dob_complaints] join keys availability: {describe_join_keys(available_map)}")
            if window_count == 0 and not args.date_field:
                print("[dob_complaints] No rows matched the requested window; proceeding cautiously.")

            order_clause = f"{date_field} ASC"
            select_fields = build_select_fields(date_field, available_map)
            if select_fields:
                print(f"[dob_complaints] Using $select columns: {', '.join(select_fields)}")
            else:
                print("[dob_complaints] $select omitted; fetching all columns.")

            if args.dry_run:
                preview_params = {
                    "$where": where_clause,
                    "$order": order_clause,
                    "$limit": 1,
                }
                preview_rows = client.query_resource(preview_params)
                if preview_rows:
                    print(f"[dob_complaints] sample keys: {sorted(preview_rows[0].keys())}")
                else:
                    print("[dob_complaints] No rows in window; nothing to preview.")
                print(
                    f"[dob_complaints] Dry run complete. field={date_field} where={where_clause} "
                    f"order={order_clause} limit=1 select="
                    f"{'omitted' if not select_fields else ','.join(select_fields)}"
                )
                conn.rollback()
                return 0

            truncate_staging(conn)
            run_id = start_ingest_run(conn, started_at)
            conn.commit()

            offset = 0
            sample_logged = False

            while True:
                params = {
                    "$limit": page_limit,
                    "$offset": offset,
                    "$order": order_clause,
                    "$where": where_clause,
                }
                if select_fields:
                    params["$select"] = ", ".join(select_fields)

                rows = client.query_resource(params)
                if not rows:
                    break

                if not sample_logged:
                    print(f"[dob_complaints] sample keys: {sorted(rows[0].keys())}")
                    sample_logged = True

                normalized_rows = [normalize_row(row) for row in rows]
                normalized_rows = [row for row in normalized_rows if row]

                if normalized_rows:
                    stage_rows(conn, normalized_rows)

                offset += len(rows)
                if len(rows) < page_limit:
                    break
                polite_sleep(min_sleep_ms, max_sleep_ms)

            inserted_total, updated_total = upsert_from_staging(conn)
            update_watermark(conn, until)
            conn.commit()

            refresh_materialized_view(conn)
            print_join_stats(conn)
            truncate_staging(conn)

            finished_at = datetime.now(timezone.utc)
            if run_id is not None:
                finalize_ingest_run(
                    conn,
                    run_id,
                    finished_at,
                    "success",
                    inserted_total,
                    updated_total,
                    None,
                )
            conn.commit()
            print(
                f"dob_complaints: field={date_field} window=[{since_iso},{until_iso}) "
                f"inserts={inserted_total} updates={updated_total}"
            )
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            finished_at = datetime.now(timezone.utc)
            if run_id is not None:
                finalize_ingest_run(
                    conn,
                    run_id,
                    finished_at,
                    "failed",
                    inserted_total,
                    updated_total,
                    str(exc),
                )
                conn.commit()
            print(f"[dob_complaints] Error: {exc}", file=sys.stderr)
            raise

    return 0


def main() -> None:
    raise SystemExit(ingest())


if __name__ == "__main__":
    main()
