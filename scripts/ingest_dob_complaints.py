#!/usr/bin/env python3
from __future__ import annotations

import argparse
import random
import subprocess
import time
import os, json, logging, sys, re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from dateutil import parser as dtp
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SOURCE_NAME = "dob_complaints_v1"
DEFAULT_RESOURCE_ID = "eabe-havv"
PAGE_SIZE = 25000
UPSERT_CHUNK_SIZE = 5000
DEFAULT_DAYS = 365
SAMPLE_LIMIT = 200
DATASET_MAX_SAMPLE_LIMIT = 2000
MAX_RETRIES = 5
RETRY_STATUS = {429, 500, 502, 503, 504}
BACKOFF_INITIAL_SECONDS = 2.0
BACKOFF_MAX_SECONDS = 60.0
BACKOFF_BASE = 1.8
REQUEST_TIMEOUT = 30
DEFAULT_SELECT_FIELDS = [
    "date_entered",
    "complaint_number",
    "bin",
    "house_number",
    "house_street",
    "zip_code",
    "community_board",
    "complaint_category",
    "status",
    "inspection_date",
    "disposition_date",
    "dobrundate",
]
DATE_PREF_ORDER = ["date_entered", "inspection_date", "disposition_date", "dobrundate"]
DATE_FALLBACK = "date_entered"
_INGEST_RUNS_NOTES_CACHE: Optional[bool] = None
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


def _parse_dt_safe(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in {"null", "none"}:
        return None
    try:
        base = datetime(1970, 1, 1)
        parsed = dtp.parse(s, default=base)
        if parsed.tzinfo:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except Exception:
        return None


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
                    delay = min(
                        BACKOFF_MAX_SECONDS,
                        BACKOFF_INITIAL_SECONDS * (BACKOFF_BASE**attempt),
                    )
                    time.sleep(delay + random.random())
                    attempt += 1
                    continue
                raise SocrataError(exc.code, body, url + query)
            except URLError as exc:
                body = str(getattr(exc, "reason", exc))
                if attempt < MAX_RETRIES:
                    delay = min(
                        BACKOFF_MAX_SECONDS,
                        BACKOFF_INITIAL_SECONDS * (BACKOFF_BASE**attempt),
                    )
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

    def get(self, dataset_id: Optional[str] = None, **params: Any) -> List[Dict[str, Any]]:
        resource = dataset_id or self.resource_id
        soql_params: Dict[str, Any] = {}
        for key, value in params.items():
            if key.startswith("$"):
                soql_params[key] = value
            else:
                soql_params[f"${key}"] = value
        url = f"{self.base_url}/resource/{resource}.json"
        return self._request(url, params=soql_params or None, expect="list")

    def get_view_columns(self, dataset_id: Optional[str] = None) -> List[Dict[str, Any]]:
        resource = dataset_id or self.resource_id
        url = f"{self.base_url}/api/views/{resource}.json"
        data = self._request(url, expect="dict")
        return data.get("columns", []) if isinstance(data, dict) else []

    def query_resource(self, params: Dict[str, Any], dataset_id: Optional[str] = None) -> List[Dict[str, Any]]:
        resource = dataset_id or self.resource_id
        url = f"{self.base_url}/resource/{resource}.json"
        return self._request(url, params=params, expect="list")

    def get_max_value(self, field: str) -> Optional[str]:
        rows = self.query_resource({"$select": f"max({field}) AS max_value"})
        if not rows:
            return None
        return rows[0].get("max_value")

    def count_rows(self, where_clause: str) -> int:
        rows = self.query_resource({"$select": "count(1) AS count", "$where": where_clause})
        if not rows:
            return 0
        value = rows[0].get("count")
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest DOB complaints from Socrata.")
    parser.add_argument(
        "--since",
        help="Fetch complaints updated/entered on or after this ISO date (UTC).",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        help=(
            "Fetch complaints updated within the past N days when --since is omitted "
            f"(default {DEFAULT_DAYS})."
        ),
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
        help="Print candidate date fields diagnostics and exit.",
    )
    args = parser.parse_args()

    if args.days is not None and args.days <= 0:
        parser.error("--days must be positive")
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


def floor_to_midnight(dt: datetime) -> datetime:
    dt_utc = dt.astimezone(timezone.utc)
    return datetime(dt_utc.year, dt_utc.month, dt_utc.day, tzinfo=timezone.utc)


def parse_since_arg(value: str) -> datetime:
    text = value.strip()
    try:
        if "T" in text:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        else:
            parsed = datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"Invalid ISO date/time: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def determine_since_dt(args: argparse.Namespace) -> datetime:
    if args.since:
        try:
            since_dt = parse_since_arg(args.since)
        except ValueError as exc:
            raise SystemExit(f"[dob_complaints] Invalid --since value: {exc}") from exc
        return floor_to_midnight(since_dt)
    days = args.days if args.days is not None else DEFAULT_DAYS
    baseline = datetime.now(timezone.utc) - timedelta(days=days)
    return floor_to_midnight(baseline)


def format_soql_timestamp(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000")


def socrata_base_from_env() -> str:
    domain = os.getenv("SOCRATA_DOMAIN") or os.getenv("NYC_SOCRATA_BASE") or "data.cityofnewyork.us"
    if not domain.startswith(("http://", "https://")):
        domain = f"https://{domain}"
    parsed = urlparse(domain)
    scheme = parsed.scheme or "https"
    host = parsed.netloc or parsed.path
    return f"{scheme}://{host}".rstrip("/")


def crosswalk_exists(conn) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
          SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'pad_bin_bbl'
          )
        """
        )
        return bool(cur.fetchone()[0])


def map_bins_to_bbl(conn, bins: List[int]) -> Dict[int, int]:
    if not bins:
        return {}
    with conn.cursor() as cur:
        cur.execute("SELECT bin, bbl FROM pad_bin_bbl WHERE bin = ANY(%s)", (bins,))
        return {bin_: bbl for (bin_, bbl) in cur.fetchall()}


def count_with_fallback(
    client: SocrataClient, field_expr: str, label: str, start_iso: str, end_iso: str
) -> Tuple[int, Optional[str]]:
    primary = f"{field_expr} >= '{start_iso}' AND {field_expr} < '{end_iso}'"
    try:
        return client.count_rows(primary), primary
    except SocrataError as exc:
        if exc.status == 400:
            between = f"{field_expr} BETWEEN '{start_iso}' AND '{end_iso}'"
            try:
                return client.count_rows(between), between
            except SocrataError as exc2:
                logging.info(
                    "[dob_complaints] count fallback failed for %s: %s", label, exc2.body
                )
                return 0, None
        logging.info(
            "[dob_complaints] count failed for %s: %s", label, getattr(exc, "body", exc)
        )
        return 0, None


def _inspect_date_fields(
    client: "SocrataClient", dataset_id: str, override: Optional[str]
) -> Tuple[str, Dict[str, Any]]:
    columns = client.get_view_columns(dataset_id)
    available: Dict[str, str] = {}
    for column in columns:
        field = column.get("fieldName")
        if field:
            available[field.lower()] = field

    candidates: List[str] = []
    for column in columns:
        field = column.get("fieldName")
        if field and "date" in field.lower():
            candidates.append(field)
    if not candidates:
        candidates = [DATE_FALLBACK]

    seen: set[str] = set()
    ordered_candidates: List[str] = []
    for field in candidates:
        key = field.lower()
        if key not in seen:
            ordered_candidates.append(field)
            seen.add(key)

    sample = client.query_resource({"$limit": SAMPLE_LIMIT}, dataset_id) or []
    parsed_counts: Dict[str, int] = {}
    parsed_max: Dict[str, Optional[datetime]] = {}
    stats: List[Dict[str, Any]] = []

    for field in ordered_candidates:
        values: List[datetime] = []
        for row in sample:
            parsed = _parse_dt_safe(row.get(field))
            if parsed:
                values.append(parsed)
        values.sort()
        parsed_counts[field] = len(values)
        parsed_max[field] = values[-1] if values else None
        stats.append(
            {
                "field": field,
                "parsed_count": len(values),
                "max": values[-1].isoformat() if values else None,
            }
        )

    preferred_available = [field for field in DATE_PREF_ORDER if field in ordered_candidates]

    chosen: Optional[str] = None
    if override:
        chosen = available.get(override.lower())
        if not chosen:
            raise RuntimeError(f"Requested date field '{override}' not found in dataset metadata.")
    else:
        for field in preferred_available:
            if parsed_counts.get(field, 0) > 0:
                chosen = field
                break
        if not chosen:
            freshest_field: Optional[str] = None
            freshest_dt: Optional[datetime] = None
            for field, max_dt in parsed_max.items():
                if max_dt and (freshest_dt is None or max_dt > freshest_dt):
                    freshest_dt = max_dt
                    freshest_field = field
            if freshest_field:
                chosen = freshest_field

    if not chosen:
        chosen = DATE_FALLBACK

    diag_payload = {
        "candidates": stats,
        "preferred_available": preferred_available,
        "discovered_choice": chosen,
    }
    return chosen, diag_payload


def discover_date_field(client: "SocrataClient", dataset_id: str, override: Optional[str]) -> str:
    chosen, _ = _inspect_date_fields(client, dataset_id, override)
    return chosen


def discover_date_field_diagnostics(
    client: "SocrataClient", dataset_id: str, override: Optional[str]
) -> Dict[str, Any]:
    _, payload = _inspect_date_fields(client, dataset_id, override)
    return payload


def diagnose_date_fields(client: SocrataClient, override: Optional[str]) -> None:
    payload = discover_date_field_diagnostics(client, client.resource_id, override)
    print(json.dumps(payload, indent=2))


def parsed_dataset_max(client: "SocrataClient", dataset_id: str, date_field: str) -> Optional[datetime]:
    maximum: Optional[datetime] = None
    for row in client.get(dataset_id, limit=DATASET_MAX_SAMPLE_LIMIT) or []:
        parsed = _parse_dt_safe(row.get(date_field))
        if parsed and (maximum is None or parsed > maximum):
            maximum = parsed
    return maximum


def build_window(
    client: "SocrataClient", dataset_id: str, date_field: str, days: Optional[int]
) -> Tuple[datetime, datetime]:
    days_back = max(int(days or DEFAULT_DAYS), 1)
    ds_max = parsed_dataset_max(client, dataset_id, date_field)
    now_utc = datetime.now(timezone.utc)
    end_dt = min(now_utc, (ds_max + timedelta(days=1)) if ds_max else now_utc)
    start_dt = end_dt - timedelta(days=days_back)
    if start_dt >= end_dt:
        start_dt = end_dt - timedelta(days=1)
    return start_dt, end_dt


def upsert_records(conn, records: Iterable[Dict[str, Any]]) -> Tuple[int, int]:
    inserted = 0
    updated = 0
    if not records:
        return inserted, updated

    sql = """
        INSERT INTO dob_complaints (
            complaint_id,
            status,
            date_entered,
            house_number,
            house_street,
            zip_code,
            bin,
            community_board,
            complaint_category,
            inspection_date,
            disposition_date,
            dobrundate,
            updated_at
        )
        VALUES (
            %(complaint_id)s,
            %(status)s,
            %(date_entered)s,
            %(house_number)s,
            %(house_street)s,
            %(zip_code)s,
            %(bin)s,
            %(community_board)s,
            %(complaint_category)s,
            %(inspection_date)s,
            %(disposition_date)s,
            %(dobrundate)s,
            now()
        )
        ON CONFLICT (complaint_id) DO UPDATE SET
            status = EXCLUDED.status,
            date_entered = EXCLUDED.date_entered,
            house_number = EXCLUDED.house_number,
            house_street = EXCLUDED.house_street,
            zip_code = EXCLUDED.zip_code,
            bin = EXCLUDED.bin,
            community_board = EXCLUDED.community_board,
            complaint_category = EXCLUDED.complaint_category,
            inspection_date = EXCLUDED.inspection_date,
            disposition_date = EXCLUDED.disposition_date,
            dobrundate = EXCLUDED.dobrundate,
            updated_at = now()
        RETURNING (xmax = 0) AS inserted_flag;
    """

    with conn.cursor() as cur:
        for record in records:
            payload = {
                "complaint_id": record.get("complaint_id"),
                "status": record.get("status"),
                "date_entered": record.get("date_entered"),
                "house_number": record.get("house_number"),
                "house_street": record.get("house_street"),
                "zip_code": record.get("zip_code"),
                "bin": record.get("bin"),
                "community_board": record.get("community_board"),
                "complaint_category": record.get("complaint_category"),
                "inspection_date": record.get("inspection_date"),
                "disposition_date": record.get("disposition_date"),
                "dobrundate": record.get("dobrundate"),
            }
            cur.execute(sql, payload)
            row = cur.fetchone()
            if row is None:
                inserted_flag = False
            elif isinstance(row, dict):
                inserted_flag = bool(row.get("inserted_flag"))
            else:
                inserted_flag = bool(row[0])
            if inserted_flag:
                inserted += 1
            else:
                updated += 1

    return inserted, updated





def ensure_watermark_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
        CREATE TABLE IF NOT EXISTS ingestion_watermarks (
            source       text NOT NULL,
            window_start date  NOT NULL,
            window_end   date  NOT NULL,
            last_offset  integer NOT NULL DEFAULT 0,
            last_run     timestamptz,
            notes        text,
            CONSTRAINT ingestion_watermarks_pk PRIMARY KEY (source, window_start)
        );
        """
        )
    conn.commit()


def get_window_offset(conn, window_start_dt: datetime, window_end_dt: datetime) -> int:
    """Return last_offset for (source, window_start). 0 if none."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(last_offset, 0) AS last_offset
            FROM ingestion_watermarks
            WHERE source = %s AND window_start = %s
            LIMIT 1
        """,
            (SOURCE_NAME, window_start_dt.date()),
        )
        row = cur.fetchone()
        if not row:
            return 0
        if isinstance(row, dict):
            return int(row.get("last_offset", 0) or 0)
        return int((row[0] if len(row) else 0) or 0)


def upsert_window_offset(
    conn,
    window_start_dt: datetime,
    window_end_dt: datetime,
    last_offset: int,
) -> None:
    """Upsert watermark for (source, window_start)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ingestion_watermarks (source, window_start, window_end, last_offset, last_run)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (source, window_start) DO UPDATE
            SET window_end  = EXCLUDED.window_end,
                last_offset = EXCLUDED.last_offset,
                last_run    = NOW()
        """,
            (SOURCE_NAME, window_start_dt.date(), window_end_dt.date(), int(last_offset)),
        )
    conn.commit()


def _next_month_start(day: datetime) -> datetime:
    year = day.year + (1 if day.month == 12 else 0)
    month = 1 if day.month == 12 else day.month + 1
    return datetime(year, month, 1, tzinfo=timezone.utc)


def build_month_windows(start_dt: datetime, end_dt: datetime) -> List[Tuple[datetime, datetime]]:
    windows: List[Tuple[datetime, datetime]] = []
    current = start_dt
    while current < end_dt:
        next_month = _next_month_start(current)
        window_end = min(next_month, end_dt)
        windows.append((current, window_end))
        current = window_end
    return windows


def ingest_runs_has_notes(conn) -> bool:
    global _INGEST_RUNS_NOTES_CACHE
    if _INGEST_RUNS_NOTES_CACHE is None:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'ingest_runs' AND column_name = 'notes'
                """
            )
            _INGEST_RUNS_NOTES_CACHE = cur.fetchone() is not None
    return bool(_INGEST_RUNS_NOTES_CACHE)


def record_ingest_run(
    conn,
    started_at: datetime,
    finished_at: datetime,
    status: str,
    inserted: int,
    updated: int,
    error: Optional[str],
    notes: Optional[str],
) -> None:
    has_notes = ingest_runs_has_notes(conn)
    with conn.cursor() as cur:
        if has_notes:
            cur.execute(
                """
                INSERT INTO ingest_runs (
                    source,
                    started_at,
                    finished_at,
                    status,
                    rows_inserted,
                    rows_updated,
                    error,
                    notes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    SOURCE_NAME,
                    started_at,
                    finished_at,
                    status,
                    inserted,
                    updated,
                    (error[:1000] if error else None),
                    notes,
                ),
            )
        else:
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


def refresh_materialized_view(conn) -> None:
    try:
        with conn.cursor() as cur:
            cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_property_events__dob_complaints")
        logging.info("[dob_complaints] Refreshed mv_property_events__dob_complaints concurrently.")
    except Exception:
        conn.rollback()
        try:
            with conn.cursor() as cur:
                cur.execute("REFRESH MATERIALIZED VIEW mv_property_events__dob_complaints")
            logging.info("[dob_complaints] Refreshed mv_property_events__dob_complaints (non-concurrent).")
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            logging.info(
                "[dob_complaints] Unable to refresh mv_property_events__dob_complaints automatically: %r",
                exc,
            )


def ingest(args: argparse.Namespace, client: SocrataClient) -> int:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is not configured; unable to connect.", file=sys.stderr)
        return 1

    conn_factory = get_connection_factory()
    started_at = datetime.now(timezone.utc)
    since_dt = determine_since_dt(args)
    since_display = since_dt.date().isoformat()

    if args.since:
        logging.info("[dob_complaints] --since provided; overriding --days=%s", args.days)
    else:
        logging.info("[dob_complaints] --since not provided; using --days=%s", args.days)
    logging.info("[dob_complaints] Starting ingest since=%s", since_display)

    dataset_id = client.resource_id
    date_field_for_logs = args.date_field or "<auto>"
    date_field = discover_date_field(client, dataset_id, args.date_field)
    date_field_for_logs = date_field
    logging.info("[dob_complaints] Using date_field=%s", date_field)

    columns = client.get_view_columns(dataset_id)
    available_map: Dict[str, str] = {}
    for column in columns:
        field_name = column.get("fieldName")
        if field_name:
            available_map[field_name.lower()] = field_name

    select_fields: List[str] = list(dict.fromkeys(DEFAULT_SELECT_FIELDS + [date_field]))

    filter_candidates: List[str] = [":updated_at"] + DATE_PREF_ORDER
    if date_field not in DATE_PREF_ORDER:
        filter_candidates.append(date_field)

    filter_fields: List[str] = []
    for candidate in filter_candidates:
        if candidate.startswith(":"):
            if candidate not in filter_fields:
                filter_fields.append(candidate)
            continue
        actual = available_map.get(candidate.lower())
        if actual and actual not in filter_fields:
            filter_fields.append(actual)

    if filter_fields:
        logging.info("[dob_complaints] Applying filters on: %s", ", ".join(filter_fields))
    else:
        logging.warning(
            "[dob_complaints] No filter fields available; relying on client-side filtering."
        )

    order_field: Optional[str] = ":updated_at" if filter_fields else None
    if order_field and order_field not in filter_fields:
        order_field = None
    if not order_field and filter_fields:
        order_field = filter_fields[0]
    if order_field:
        logging.info("[dob_complaints] Ordering by %s", order_field)
    else:
        logging.warning("[dob_complaints] No order field resolved; using API default order.")

    page_size = PAGE_SIZE
    total_downloaded = 0
    total_inserted = 0
    total_updated = 0
    total_skipped = 0
    pages = 0
    should_refresh = False
    latest_processed: Optional[datetime] = None

    today_floor = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    end_dt = today_floor + timedelta(days=1)
    if since_dt >= end_dt:
        since_dt = today_floor
    windows = build_month_windows(since_dt, end_dt)
    if not windows:
        windows = [(since_dt, end_dt)]

    with conn_factory() as conn:
        ensure_watermark_table(conn)
        try:
            crosswalk_available = False
            warned_crosswalk_missing = False
            if not args.dry_run:
                try:
                    crosswalk_available = crosswalk_exists(conn)
                except Exception as exc:
                    logging.info("[dob_complaints] Unable to check BIN→BBL crosswalk: %r", exc)
                    crosswalk_available = False
                if not crosswalk_available:
                    logging.warning("[dob_complaints] BIN→BBL mapping skipped (pad_bin_bbl not found).")
                    warned_crosswalk_missing = True

            for window_start_dt, window_end_dt in windows:
                window_label = f"{window_start_dt.date()}->{window_end_dt.date()}"
                offset = get_window_offset(conn, window_start_dt, window_end_dt)
                offset = max(offset, 0)

                window_start_iso = format_soql_timestamp(window_start_dt)
                window_end_iso = format_soql_timestamp(window_end_dt)
                window_start_naive = window_start_dt.replace(tzinfo=None)
                window_end_naive = window_end_dt.replace(tzinfo=None)

                if filter_fields:
                    window_conditions = [
                        f"{field} >= '{window_start_iso}' AND {field} < '{window_end_iso}'"
                        for field in filter_fields
                    ]
                    window_where_clause: Optional[str] = "(" + " OR ".join(window_conditions) + ")"
                else:
                    window_where_clause = None

                logging.info(
                    "[dob_complaints] Processing window %s starting offset=%d",
                    window_label,
                    offset,
                )

                current_offset = offset
                window_pages = 0

                try:
                    while True:
                        current_offset = offset
                        params: Dict[str, Any] = {
                            "$select": ",".join(select_fields),
                            "$limit": page_size,
                            "$offset": current_offset,
                        }
                        if window_where_clause:
                            params["$where"] = window_where_clause
                        if order_field:
                            params["$order"] = f"{order_field} ASC"

                        rows = client.query_resource(params)
                        if not rows:
                            if not args.dry_run:
                                upsert_window_offset(conn, window_start_dt, window_end_dt, 0)
                                conn.commit()
                            break

                        window_pages += 1
                        pages += 1
                        batch_count = len(rows)
                        total_downloaded += batch_count

                        bin_to_bbl: Dict[int, int] = {}
                        bins_seen: set[int] = set()
                        if crosswalk_available:
                            for row in rows:
                                try:
                                    bin_raw = row.get("bin")
                                    bin_int = int(bin_raw) if bin_raw not in (None, "") else None
                                except Exception:
                                    bin_int = None
                                if bin_int is not None:
                                    bins_seen.add(bin_int)
                            if bins_seen:
                                try:
                                    bin_to_bbl = map_bins_to_bbl(conn, list(bins_seen))
                                except Exception as exc:
                                    logging.warning(
                                        "[dob_complaints] BIN→BBL mapping unavailable; continuing without crosswalk. %r",
                                        exc,
                                    )
                                    crosswalk_available = False
                                    bin_to_bbl = {}
                                    if not warned_crosswalk_missing:
                                        logging.warning("[dob_complaints] BIN→BBL mapping skipped.")
                                        warned_crosswalk_missing = True

                        skipped_before = total_skipped
                        normalized_rows: List[Dict[str, Any]] = []
                        for row in rows:
                            dt_value = _parse_dt_safe(row.get(date_field))
                            if (
                                dt_value is None
                                or dt_value < window_start_naive
                                or dt_value >= window_end_naive
                            ):
                                total_skipped += 1
                                continue

                            complaint_number = row.get("complaint_number")
                            if not complaint_number:
                                total_skipped += 1
                                continue
                            complaint_id = str(complaint_number).strip()
                            if not complaint_id:
                                total_skipped += 1
                                continue

                            house_number = (row.get("house_number") or "").strip()
                            house_street = (row.get("house_street") or "").strip()
                            zip_code = (row.get("zip_code") or "").strip()
                            bin_text = (row.get("bin") or "").strip()

                            record: Dict[str, Any] = {
                                "complaint_id": complaint_id,
                                "status": row.get("status"),
                                "date_entered": _parse_dt_safe(row.get("date_entered")),
                                "house_number": house_number or None,
                                "house_street": house_street or None,
                                "zip_code": zip_code or None,
                                "bin": bin_text or None,
                                "community_board": row.get("community_board"),
                                "complaint_category": row.get("complaint_category"),
                                "inspection_date": _parse_dt_safe(row.get("inspection_date")),
                                "disposition_date": _parse_dt_safe(row.get("disposition_date")),
                                "dobrundate": _parse_dt_safe(row.get("dobrundate")),
                            }

                            if crosswalk_available and bin_text:
                                try:
                                    bin_int = int(bin_text)
                                except Exception:
                                    bin_int = None
                                if bin_int is not None:
                                    record["bbl"] = bin_to_bbl.get(bin_int)

                            normalized_rows.append(record)

                            dt_value_aware = dt_value.replace(tzinfo=timezone.utc)
                            if latest_processed is None or dt_value_aware > latest_processed:
                                latest_processed = dt_value_aware

                        if (
                            crosswalk_available
                            and bins_seen
                            and not warned_crosswalk_missing
                            and not bin_to_bbl
                        ):
                            logging.info(
                                "[dob_complaints] BIN→BBL crosswalk returned no matches for current window."
                            )
                            warned_crosswalk_missing = True

                        page_inserted = 0
                        page_updated = 0
                        if normalized_rows and not args.dry_run:
                            for start_idx in range(0, len(normalized_rows), UPSERT_CHUNK_SIZE):
                                chunk = normalized_rows[start_idx : start_idx + UPSERT_CHUNK_SIZE]
                                inserted, updated = upsert_records(conn, chunk)
                                page_inserted += inserted
                                page_updated += updated
                                total_inserted += inserted
                                total_updated += updated
                                conn.commit()
                            if page_inserted or page_updated:
                                should_refresh = True
                        elif args.dry_run:
                            page_inserted = 0
                            page_updated = 0

                        page_skipped = total_skipped - skipped_before
                        print(
                            "[dob_complaints] window=%s page=%d offset=%d downloaded=%d inserted=%d updated=%d skipped=%d"
                            % (
                                window_label,
                                window_pages,
                                current_offset,
                                batch_count,
                                page_inserted,
                                page_updated,
                                page_skipped,
                            )
                        )

                        next_offset = 0 if batch_count < page_size else current_offset + batch_count
                        if not args.dry_run:
                            upsert_window_offset(conn, window_start_dt, window_end_dt, next_offset)
                            conn.commit()

                        if batch_count < page_size:
                            break

                        offset = next_offset

                except KeyboardInterrupt:
                    if not args.dry_run:
                        upsert_window_offset(conn, window_start_dt, window_end_dt, current_offset)
                        conn.commit()
                    raise
                except Exception:
                    if not args.dry_run:
                        upsert_window_offset(conn, window_start_dt, window_end_dt, current_offset)
                        conn.commit()
                    raise

            finished_at = datetime.now(timezone.utc)

            if args.dry_run:
                conn.rollback()
            else:
                notes_text = f"date_field={date_field}, since={since_display}, windows={len(windows)}"
                record_ingest_run(
                    conn,
                    started_at,
                    finished_at,
                    "success",
                    total_inserted,
                    total_updated,
                    None,
                    notes_text,
                )
                conn.commit()
        except Exception as exc:
            conn.rollback()
            finished_at = datetime.now(timezone.utc)
            if not args.dry_run:
                failure_notes = f"date_field={date_field_for_logs}, since={since_display}"
                try:
                    record_ingest_run(
                        conn,
                        started_at,
                        finished_at,
                        "failed",
                        total_inserted,
                        total_updated,
                        str(exc),
                        failure_notes,
                    )
                    conn.commit()
                except Exception:
                    conn.rollback()
            print(f"[dob_complaints] Error: {exc}", file=sys.stderr)
            raise

    logging.info("[dob_complaints] Pages fetched: %s", pages)
    print(
        f"[dob_complaints] totals downloaded={total_downloaded} inserted={total_inserted} "
        f"updated={total_updated} skipped={total_skipped}"
    )
    suffix = " (dry-run)" if args.dry_run else ""
    print(f"complaints backfill complete | since={since_display} | rows={total_downloaded}{suffix}")

    if should_refresh and not args.dry_run:
        script_dir = Path(__file__).resolve().parent
        refresh_script = script_dir / "refresh_mv.sh"
        subprocess.run(["bash", str(refresh_script)], check=True)

    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parse_args()
    load_environment()

    base = socrata_base_from_env()
    resource_id = os.getenv("DOB_COMPLAINTS_RESOURCE_ID", DEFAULT_RESOURCE_ID)
    app_token = os.getenv("SOCRATA_APP_TOKEN") or os.getenv("NYC_SOCRATA_APP_TOKEN")
    client = SocrataClient(base, resource_id, app_token)

    if args.diagnose_date_fields:
        diagnose_date_fields(client, args.date_field)
        return 0

    return ingest(args, client)



if __name__ == "__main__":
    raise SystemExit(main())
