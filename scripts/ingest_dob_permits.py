#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
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

from scripts.util_bbl import normalize_bbl

SOURCE_NAME = "dob_permits_v1"
PAGE_SIZE = 5000
DAYS_BACK_DEFAULT = 365
DEFAULT_LIMIT = 50000
MAX_RETRIES = 5
RETRY_STATUS = {429, 500, 502, 503, 504}
BACKOFF_INITIAL_SECONDS = 2.0
BACKOFF_MAX_SECONDS = 60.0
REQUEST_TIMEOUT = 60
PREFERRED_FIELDS = [
    "issuance_date",
    "filing_date",
    "status_date",
    "expiration_date",
]

DEFAULT_SELECT_FIELDS = [
    "bbl",
    "bbl_number",
    "job_number",
    "job_no",
    "jobnum",
    "job__",
    "job",
    "job_type",
    "jobtype",
    "status",
    "current_status",
    "filing_date",
    "filed_date",
    "status_date",
    "latest_action_date",
    "issued_date",
    "issuance_date",
    "description",
    "last_update",
    "lastupdatedate",
    "latest_status_date",
    "borough",
    "borocode",
    "boro",
    "block",
    "lot",
    "source_row_id",
]

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def ensure_watermark_table(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.ingestion_watermarks (
                source text NOT NULL,
                window_start timestamptz NOT NULL,
                window_end timestamptz,
                last_offset integer,
                last_run timestamptz,
                CONSTRAINT ux_ingestion_watermarks_source_window
                    UNIQUE (source, window_start)
            );
        """)
    conn.commit()


class SocrataError(Exception):
    def __init__(self, status: Optional[int], body: str, url: str):
        msg = f"Socrata request failed (status={status}, url={url}): {body}"
        super().__init__(msg)
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

            text = payload.decode("utf-8") if payload else ""
            if not text:
                return [] if expect == "list" else {}
            data = json.loads(text)

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
    parser = argparse.ArgumentParser(description="Ingest DOB permits from Socrata.")
    parser.add_argument(
        "--since",
        help="Fetch permits updated/issued on or after this ISO date (UTC).",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DAYS_BACK_DEFAULT,
        help=(
            "Fetch permits updated within the past N days when --since is omitted "
            f"(default {DAYS_BACK_DEFAULT})."
        ),
    )
    parser.add_argument(
        "--until",
        help="Fetch permits before this ISO date (exclusive at midnight).",
    )
    parser.add_argument(
        "--date-field",
        default="latest_status_date",
        help="Use this column as the incremental field (default: latest_status_date).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Maximum rows to fetch from Socrata (default {DEFAULT_LIMIT}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run discovery and counting only; do not write to the database.",
    )
    parser.add_argument(
        "--print-query",
        action="store_true",
        help="Echo the generated Socrata WHERE clause.",
    )
    parser.add_argument(
        "--diagnose-date-fields",
        action="store_true",
        help="Print candidate date fields with recency metrics and exit.",
    )
    args = parser.parse_args()

    if args.days is not None and args.days <= 0:
        parser.error("--days must be positive")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be >= 1")
    return args


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
    midnight = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
    return midnight


def compute_window(
    watermark: datetime,
    since_arg: Optional[str],
    until_arg: Optional[str],
    days: Optional[int],
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
        effective_days = DAYS_BACK_DEFAULT if days is None else max(days, 1)
        since = until - timedelta(days=effective_days)

    since = max(since, watermark or EPOCH)
    if since > until:
        since = until

    return since, until


def determine_since_dt(args: argparse.Namespace) -> datetime:
    if args.since:
        parsed = parse_datetime_arg(args.since)
        since_dt = floor_to_midnight(parsed)
    else:
        days = args.days if args.days is not None else DAYS_BACK_DEFAULT
        baseline = datetime.now(timezone.utc) - timedelta(days=days)
        since_dt = floor_to_midnight(baseline)
    return max(since_dt, EPOCH)


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


def is_date_like_dtype(dtype: Optional[str]) -> bool:
    return (dtype or "").lower() in {"calendar_date", "floating_timestamp", "date"}


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
    for preferred in PREFERRED_FIELDS:
        for field, dtype in fields:
            if field.lower() == preferred and field.lower() not in seen:
                ordered.append((field, dtype))
                seen.add(field.lower())
    for field, dtype in fields:
        if field.lower() not in seen:
            ordered.append((field, dtype))
            seen.add(field.lower())
    return ordered


def _resolve_coordinate_fields(columns: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
    lat_candidates = ["gis_latitude", "latitude"]
    lon_candidates = ["gis_longitude", "longitude"]
    names = { (col.get("fieldName") or "").lower(): col.get("fieldName") for col in columns }

    lat_field = next((names.get(c) for c in lat_candidates if names.get(c)), None)
    lon_field = next((names.get(c) for c in lon_candidates if names.get(c)), None)
    return lat_field, lon_field


def build_select_fields(
    date_field: str,
    available_map: Dict[str, str],
    lat_field: Optional[str],
    lon_field: Optional[str],
) -> List[str]:
    desired = [date_field] + DEFAULT_SELECT_FIELDS
    fields: List[str] = []
    seen: set[str] = set()
    for name in desired:
        key = name.lower()
        actual = available_map.get(key)
        if actual and actual.lower() not in seen:
            fields.append(actual)
            seen.add(actual.lower())

    if lat_field:
        alias = "latitude"
        expression = f"{lat_field} AS {alias}" if lat_field.lower() != alias else lat_field
        fields.append(expression)
        seen.add(alias)
    if lon_field:
        alias = "longitude"
        expression = f"{lon_field} AS {alias}" if lon_field.lower() != alias else lon_field
        fields.append(expression)
        seen.add(alias)
    return fields


def select_date_field(
    client: SocrataClient,
    columns: List[Dict[str, Any]],
    since_iso: str,
    until_iso: str,
    override: Optional[str] = None,
) -> Tuple[str, Optional[str], int, str]:
    available_map = build_available_map(columns)
    all_column_names = sorted(available_map.values())
    candidates = build_candidate_fields(columns)
    ordered_candidates = order_candidate_fields(candidates)

    if override:
        actual_name = available_map.get(override.lower())
        if not actual_name:
            available = ", ".join(sorted(all_column_names))
            raise SystemExit(
                f"[dob_permits] Requested date field '{override}' not found. "
                f"Available columns: {available}"
            )
        dtype = None
        for column in columns:
            if column.get("fieldName") == actual_name:
                dtype = (column.get("dataTypeName") or "").lower()
                break
        count, where_clause = count_with_fallback(client, actual_name, since_iso, until_iso)
        if count == 0:
            print(
                f"[dob_permits] Warning: field '{actual_name}' returned 0 rows for window "
                f"[{since_iso},{until_iso}).",
                file=sys.stderr,
            )
        return actual_name, dtype, count, where_clause

    if not ordered_candidates:
        available = ", ".join(sorted(all_column_names))
        raise SystemExit(
            "[dob_permits] No date-typed columns found in Socrata metadata. "
            f"Available columns: {available}. Try --date-field."
        )

    freshest_field: Optional[str] = None
    freshest_dt: Optional[datetime] = None
    metadata: Dict[str, Tuple[int, str, str]] = {}
    max_timestamps: Dict[str, Optional[datetime]] = {}

    for field, dtype in ordered_candidates:
        try:
            count, where_clause = count_with_fallback(client, field, since_iso, until_iso)
        except SocrataError as exc:
            print(f"[dob_permits] Skipping field '{field}' (count failed: {exc.body})", file=sys.stderr)
            continue

        metadata[field] = (count, where_clause, dtype)

        if count > 0:
            print(f"[dob_permits] Selected field '{field}' with {count} rows in window.")
            return field, dtype, count, where_clause

        try:
            max_value = client.get_max_value(field)
        except SocrataError as exc:
            print(f"[dob_permits] max({field}) lookup failed: {exc.body}", file=sys.stderr)
            max_dt = None
        else:
            max_dt = parse_any_datetime(max_value)
        max_timestamps[field] = max_dt

        if max_dt and (freshest_dt is None or max_dt > freshest_dt):
            freshest_dt = max_dt
            freshest_field = field

    if freshest_field and freshest_field in metadata:
        count, where_clause, dtype = metadata[freshest_field]
        max_info = max_timestamps.get(freshest_field)
        if max_info:
            print(
                f"[dob_permits] Falling back to field '{freshest_field}' "
                f"using max={max_info.isoformat()} (window count={count})."
            )
        else:
            print(
                f"[dob_permits] Falling back to field '{freshest_field}' "
                f"despite missing recent values (window count={count})."
            )
        return freshest_field, dtype, count, where_clause

    if metadata:
        # All counts succeeded but no freshness information.
        field = next(iter(metadata))
        count, where_clause, dtype = metadata[field]
        print(
            f"[dob_permits] Falling back to field '{field}' (window count={count}) "
            "without freshness metadata."
        )
        return field, dtype, count, where_clause

    available = ", ".join(sorted(all_column_names))
    raise SystemExit(
        "[dob_permits] No usable date field found for DOB permits ingestion. "
        f"Available columns: {available}. Try --date-field."
    )


def count_with_fallback(client: SocrataClient, field: str, since_iso: str, until_iso: str) -> Tuple[int, str]:
    primary = f"{field} >= '{since_iso}' AND {field} < '{until_iso}'"
    try:
        count = client.count_rows(primary)
        return count, primary
    except SocrataError as exc:
        if exc.status == 400:
            print(f"[dob_permits] 400 from count using >=/< filter: {exc.body}", file=sys.stderr)
            between = f"{field} between '{since_iso}' and '{until_iso}'"
            try:
                count = client.count_rows(between)
                return count, between
            except SocrataError as exc2:
                if exc2.status == 400:
                    raise SystemExit(
                        f"[dob_permits] SoQL count failed for field '{field}' with SINCE={since_iso}, "
                        f"UNTIL={until_iso}. Errors: primary={exc.body!r}, between={exc2.body!r}"
                    ) from exc2
                raise
        raise


def fetch_recent_rows_for_text_field(
    client: SocrataClient,
    field: str,
    select_fields: List[str],
    limit: int,
    since: datetime,
    until: datetime,
) -> Tuple[List[Dict[str, Any]], int, int]:
    if limit <= 0:
        return [], 0, 0

    params: Dict[str, Any] = {
        "$limit": limit,
        "$order": f"{field} DESC NULLS LAST",
    }
    if select_fields:
        params["$select"] = ", ".join(select_fields)

    rows = client.query_resource(params)
    total_rows = len(rows)
    unparsable = 0
    filtered: List[Dict[str, Any]] = []

    for row in rows:
        raw_value = row.get(field)
        parsed = parse_any_datetime(raw_value)
        if parsed is None:
            unparsable += 1
            continue
        if since <= parsed < until:
            filtered.append(row)

    if total_rows > 0 and unparsable == total_rows:
        raise SystemExit(
            f"[dob_permits] Field '{field}' returned {unparsable} values that are not ISO-8601 timestamps. "
            "Adjust --date-field or confirm the Socrata schema."
        )

    return filtered, unparsable, total_rows


def diagnose_date_fields(client: SocrataClient) -> None:
    columns = client.get_view_columns()
    available_map = build_available_map(columns)
    candidates = order_candidate_fields(build_candidate_fields(columns))
    all_column_names = sorted(available_map.values())

    if not columns:
        print("No columns returned from Socrata metadata; cannot diagnose.")
        return

    print("SoQL metadata types:")
    for column in columns:
        field = column.get("fieldName") or "<unknown>"
        dtype = column.get("dataTypeName") or ""
        print(f"  {field}: {dtype}")
    print()

    if not candidates:
        available = ", ".join(sorted(all_column_names))
        print("No date-typed columns found. Available columns:", available)
        print("Pass --date-field <column> to force a specific field.")
        return

    print("Available columns:", ", ".join(all_column_names))

    until = floor_to_midnight(datetime.now(timezone.utc))
    until_iso = format_soql_timestamp(until)
    since_7_iso = format_soql_timestamp(until - timedelta(days=7))
    since_30_iso = format_soql_timestamp(until - timedelta(days=30))

    header = f"{'field':<24} | {'type':<18} | {'max(field)':<26} | {'count_7d':<9} | {'count_30d':<10}"
    print(header)
    print("-" * len(header))

    for field, dtype in candidates:
        try:
            max_value = client.get_max_value(field)
            max_dt = parse_any_datetime(max_value)
            max_display = max_dt.isoformat() if max_dt else (max_value or "")
        except SocrataError as exc:
            max_display = f"ERR:{exc.status or ''}"

        count_7_display: Any
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
            f"{field:<24} | {dtype or '':<18} | {max_display:<26} | "
            f"{count_7_display:<9} | {count_30_display:<10}"
        )

    try:
        sample = client.query_resource({"$limit": 1})
    except SocrataError as exc:
        print(f"\nSample row schema unavailable (error: {exc.status or ''}).")
        return

    if not sample:
        print("\nSample row schema: no rows returned.")
        return

    print("\nSample row schema:")
    row = sample[0]
    for key in sorted(row.keys()):
        value = row[key]
        print(f"  {key}: {type(value).__name__}")


def normalize_date(value: Any) -> Optional[str]:
    if value in (None, "", "null", "NULL"):
        return None
    text = str(value).strip()
    if not text:
        return None
    if "T" in text:
        text = text.split("T", 1)[0]
    return text


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


def normalize_bbl_token(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) == 10 and digits[0] in "12345":
        return digits
    return None


def resolve_bbl(row: Dict[str, Any]) -> Optional[str]:
    primary = row.get("bbl") or row.get("bbl_number")
    normalized = normalize_bbl_token(primary)
    if normalized:
        return normalized

    borough = (
        row.get("borough")
        or row.get("borocode")
        or row.get("boro")
        or row.get("boroughname")
    )
    block = row.get("block") or row.get("block__") or row.get("block_num")
    lot = row.get("lot") or row.get("lot__") or row.get("lot_num")
    normalized = normalize_bbl(borough, block, lot)
    if normalized:
        return normalized
    return None


def normalize_row(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    bbl = resolve_bbl(row)
    job_number = (
        row.get("job_number")
        or row.get("job_no")
        or row.get("jobnum")
        or row.get("job__")
        or row.get("job")
    )
    if job_number is not None:
        job_number = str(job_number).strip()
    if not bbl or not job_number:
        return None

    borough_value = (
        row.get("borough")
        or row.get("borocode")
        or row.get("boro")
        or row.get("boroughname")
    )
    borough_clean = str(borough_value).strip().upper() if borough_value else None
    issuance_date = normalize_date(row.get("issuance_date") or row.get("issued_date"))
    latest_status_date = normalize_date(row.get("latest_status_date") or row.get("status_date"))
    latest_action_date = normalize_date(row.get("latest_action_date"))
    status_date = normalize_date(row.get("status_date"))
    filed_date = normalize_date(row.get("filed_date"))

    payload: Dict[str, Any] = {
        "bbl": bbl,
        "job_number": job_number,
        "borough": borough_clean,
        "job_type": row.get("job_type") or row.get("jobtype"),
        "status": row.get("status") or row.get("current_status"),
        "filing_date": normalize_date(row.get("filing_date") or row.get("filed_date")),
        "issuance_date": issuance_date,
        "latest_status_date": latest_status_date,
        "latest_action_date": latest_action_date,
        "status_date": status_date,
        "filed_date": filed_date,
        "description": row.get("description"),
        "last_update": normalize_timestamp(
            row.get("last_update") or row.get("lastupdatedate") or row.get("latest_status_date")
        ),
        "source_row_id": row.get(":id") or row.get("source_row_id"),
        "raw": json.dumps(row, sort_keys=True),
    }
    return payload


def upsert_records(conn, records: Iterable[Dict[str, Any]]) -> Tuple[int, int]:
    inserted = 0
    updated = 0
    sql = """
        INSERT INTO dob_permits (
            job_number,
            bbl,
            borough,
            job_type,
            status,
            filing_date,
            filed_date,
            issuance_date,
            status_date,
            latest_status_date,
            latest_action_date,
            description,
            last_update,
            source_row_id,
            raw
        )
        VALUES (
            %(job_number)s,
            %(bbl)s,
            %(borough)s,
            %(job_type)s,
            %(status)s,
            %(filing_date)s,
            %(filed_date)s,
            %(issuance_date)s,
            %(status_date)s,
            %(latest_status_date)s,
            %(latest_action_date)s,
            %(description)s,
            %(last_update)s,
            %(source_row_id)s,
            %(raw)s::jsonb
        )
        ON CONFLICT (job_number) DO UPDATE SET
            bbl = COALESCE(EXCLUDED.bbl, dob_permits.bbl),
            borough = COALESCE(EXCLUDED.borough, dob_permits.borough),
            job_type = COALESCE(EXCLUDED.job_type, dob_permits.job_type),
            status = EXCLUDED.status,
            latest_action_date = COALESCE(EXCLUDED.latest_action_date, dob_permits.latest_action_date),
            latest_status_date = COALESCE(EXCLUDED.latest_status_date, dob_permits.latest_status_date),
            status_date = COALESCE(EXCLUDED.status_date, dob_permits.status_date),
            issuance_date = COALESCE(EXCLUDED.issuance_date, dob_permits.issuance_date),
            filing_date = COALESCE(EXCLUDED.filing_date, dob_permits.filing_date),
            filed_date = COALESCE(EXCLUDED.filed_date, dob_permits.filed_date),
            description = COALESCE(EXCLUDED.description, dob_permits.description),
            last_update = NOW(),
            source_row_id = COALESCE(EXCLUDED.source_row_id, dob_permits.source_row_id),
            raw = EXCLUDED.raw,
            updated_at = now()
        RETURNING (xmax = 0) AS inserted_flag
    """
    with conn.cursor() as cur:
        for record in records:
            cur.execute(sql, record)
            flag = cur.fetchone()
            if bool(flag):
                inserted += 1
            else:
                updated += 1
    return inserted, updated


def update_watermark(conn, finished_at, window_start_dt=None, window_end_dt=None):
    """
    Record last_run in ingestion_watermarks using the (source, window_start) PK.
    If no window dates are passed, use today's date for both.
    """
    from datetime import datetime, timezone

    ws = window_start_dt or finished_at
    we = window_end_dt or ws
    if ws.tzinfo is None:
        ws = ws.replace(tzinfo=timezone.utc)
    else:
        ws = ws.astimezone(timezone.utc)
    if we.tzinfo is None:
        we = we.replace(tzinfo=timezone.utc)
    else:
        we = we.astimezone(timezone.utc)
    finished_ts = finished_at if finished_at.tzinfo else finished_at.replace(tzinfo=timezone.utc)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ingestion_watermarks (source, window_start, window_end, last_offset, last_run)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (source, window_start) DO UPDATE
            SET window_end = EXCLUDED.window_end,
                last_run   = EXCLUDED.last_run
            """,
            (SOURCE_NAME, ws, we, 0, finished_ts),
        )
    conn.commit()


def record_ingest_run(
    conn,
    started_at: datetime,
    finished_at: datetime,
    status: str,
    inserted: int,
    updated: int,
    error: Optional[str],
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ingest_runs (
                source,
                started_at,
                finished_at,
                status,
                rows_inserted,
                rows_updated,
                error
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                SOURCE_NAME,
                started_at,
                finished_at,
                status,
                inserted,
                updated,
                (error[:1000] if error else None),
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


def ingest() -> int:
    args = parse_args()
    load_environment()

    resource_id = os.getenv("DOB_PERMITS_RESOURCE_ID")
    if not resource_id:
        print("DOB_PERMITS_RESOURCE_ID is not configured; nothing to ingest.", file=sys.stderr)
        return 1

    base = os.getenv("NYC_SOCRATA_BASE", "https://data.cityofnewyork.us").rstrip("/")
    app_token = os.getenv("NYC_SOCRATA_APP_TOKEN")
    client = SocrataClient(base, resource_id, app_token)

    if args.diagnose_date_fields:
        diagnose_date_fields(client)
        return 0

    since_dt = determine_since_dt(args)

    columns = client.get_view_columns()
    available_map = build_available_map(columns)

    date_field_input = args.date_field or "latest_status_date"
    date_field_actual = available_map.get(date_field_input.lower())
    if not date_field_actual:
        available = ", ".join(sorted(available_map.values()))
        raise SystemExit(
            f"[dob_permits] Date field '{date_field_input}' not found in Socrata metadata. "
            f"Available columns: {available}"
        )

    if args.since:
        window_start_dt = floor_to_midnight(parse_datetime_arg(args.since))
    else:
        window_start_dt = since_dt

    if args.until:
        window_end_dt = floor_to_midnight(parse_datetime_arg(args.until))
    else:
        window_end_dt = floor_to_midnight(datetime.now(timezone.utc) + timedelta(days=1))
    if window_end_dt <= window_start_dt:
        window_end_dt = window_start_dt + timedelta(days=1)

    since_str = args.since or window_start_dt.strftime("%Y-%m-%d")
    until_str = args.until or window_end_dt.strftime("%Y-%m-%d")
    where_clause = (
        f"{date_field_actual} >= '{since_str}T00:00:00' "
        f"AND {date_field_actual} < '{until_str}T00:00:00'"
    )
    if args.print_query:
        print("WHERE:", where_clause)

    lat_field, lon_field = _resolve_coordinate_fields(columns)
    select_fields = build_select_fields(date_field_actual, available_map, lat_field, lon_field)

    order_field = date_field_actual
    if args.since:
        print(f"[dob_permits] --since provided; overriding --days={args.days}")
    else:
        print(f"[dob_permits] --since not provided; using --days={args.days}")
    print(f"[dob_permits] Using date_field={date_field_actual}")
    print(f"[dob_permits] Starting ingest window [{since_str}, {until_str})")
    print(f"[dob_permits] Ordering by {order_field}")

    page_size = min(PAGE_SIZE, args.limit)
    min_sleep_ms, max_sleep_ms = get_polite_bounds()
    total_downloaded = 0
    total_inserted = 0
    total_updated = 0
    total_skipped = 0
    should_refresh = False
    dry_run_samples: List[Dict[str, Any]] = []
    total_ready = 0
    remaining = args.limit

    conn_factory = get_connection_factory()
    started_at = datetime.now(timezone.utc)

    with conn_factory() as conn:
        if not args.dry_run:
            ensure_watermark_table(conn)
            conn.commit()
        try:
            offset = 0
            while remaining > 0:
                limit_batch = min(page_size, remaining)
                params: Dict[str, Any] = {"$limit": limit_batch, "$offset": offset}
                params["$where"] = where_clause
                if order_field:
                    params["$order"] = f"{order_field} ASC"
                if select_fields:
                    params["$select"] = ", ".join(select_fields)
                rows = client.query_resource(params)
                batch_count = len(rows)
                if batch_count == 0:
                    break

                total_downloaded += batch_count
                normalized_rows: List[Dict[str, Any]] = []
                for raw_row in rows:
                    normalized = normalize_row(raw_row)
                    if not normalized:
                        total_skipped += 1
                        continue
                    normalized_rows.append(normalized)

                if args.dry_run:
                    total_ready += len(normalized_rows)
                    if len(dry_run_samples) < 3:
                        needed = 3 - len(dry_run_samples)
                        dry_run_samples.extend(normalized_rows[:needed])
                elif normalized_rows:
                    inserted, updated = upsert_records(conn, normalized_rows)
                    total_inserted += inserted
                    total_updated += updated
                    conn.commit()

                remaining -= batch_count
                offset += limit_batch
                if batch_count < limit_batch:
                    break
                if remaining <= 0:
                    break
                polite_sleep(min_sleep_ms, max_sleep_ms)

            finished_at = datetime.now(timezone.utc)
            if args.dry_run:
                conn.rollback()
            else:
                update_watermark(conn, finished_at, window_start_dt, window_end_dt)
                record_ingest_run(conn, started_at, finished_at, "success", total_inserted, total_updated, None)
                conn.commit()
                should_refresh = True
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            finished_at = datetime.now(timezone.utc)
            if not args.dry_run:
                try:
                    record_ingest_run(
                        conn, started_at, finished_at, "failed", total_inserted, total_updated, str(exc)
                    )
                    conn.commit()
                except Exception:  # noqa: BLE001
                    conn.rollback()
            print(f"[dob_permits] Error: {exc}", file=sys.stderr)
            raise

    if args.dry_run:
        print(
            f"[dob_permits] dry-run downloaded={total_downloaded} normalized={total_ready} "
            f"skipped={total_skipped}"
        )
        if dry_run_samples:
            print("[dob_permits] sample rows:")
            for sample in dry_run_samples:
                print(json.dumps(sample, indent=2, sort_keys=True))
        return 0

    print(
        f"[dob_permits] totals downloaded={total_downloaded} inserted={total_inserted} "
        f"updated={total_updated} skipped={total_skipped}"
    )
    print(
        f"permits backfill complete | window=[{since_str}, {until_str}) | rows={total_downloaded}"
    )

    if should_refresh:
        script_dir = Path(__file__).resolve().parent
        refresh_script = script_dir / "refresh_mv.sh"
        subprocess.run(["bash", str(refresh_script)], check=True)

    return 0


def fetch_watermark(conn) -> datetime:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT last_run FROM ingestion_watermarks WHERE source = %s",
            (SOURCE_NAME,),
        )
        row = cur.fetchone()
    if not row:
        return EPOCH
    value = row.get("last_run")
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return EPOCH


def main() -> int:
    return ingest()


if __name__ == "__main__":
    raise SystemExit(main())
