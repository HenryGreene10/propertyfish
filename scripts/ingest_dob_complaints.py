#!/usr/bin/env python3
from __future__ import annotations

import argparse
import random
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
DEFAULT_PAGE_LIMIT = 50000
DEFAULT_DAYS = 30
SAMPLE_LIMIT = 200
DATASET_MAX_SAMPLE_LIMIT = 2000
MAX_RETRIES = 5
RETRY_STATUS = {429, 500, 502, 503, 504}
BACKOFF_INITIAL_SECONDS = 2.0
BACKOFF_MAX_SECONDS = 60.0
REQUEST_TIMEOUT = 60
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
    parser.add_argument("--since", help="Fetch complaints updated since YYYY-MM-DD (UTC).")
    parser.add_argument("--until", help="Fetch complaints updated before YYYY-MM-DD (UTC).")
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        help=f"Fetch complaints updated within the past N days (default {DEFAULT_DAYS}).",
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
    parser.add_argument(
        "--page-limit",
        type=int,
        default=DEFAULT_PAGE_LIMIT,
        help=f"Page size for Socrata requests (default {DEFAULT_PAGE_LIMIT}).",
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
            inserted_flag = cur.fetchone()[0]
            if inserted_flag:
                inserted += 1
            else:
                updated += 1

    return inserted, updated





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
    date_field_for_logs = args.date_field or "<auto>"
    start_iso = "unknown"
    end_iso = "unknown"
    wm = "none"

    with conn_factory() as conn:
        try:
            dataset_id = client.resource_id
            date_field = discover_date_field(client, dataset_id, args.date_field)
            date_field_for_logs = date_field

            ds_max_dt = parsed_dataset_max(client, dataset_id, date_field)
            wm = ds_max_dt.isoformat() if ds_max_dt else "none"

            since_dt, until_dt = build_window(client, dataset_id, date_field, args.days)
            start_iso = since_dt.strftime("%Y-%m-%dT00:00:00.000")
            end_iso = until_dt.strftime("%Y-%m-%dT00:00:00.000")

            server_field = ":updated_at"
            order_clause = f"{server_field} ASC"
            window_count, where_clause = count_with_fallback(client, server_field, date_field, start_iso, end_iso)

            page_limit = max(1, args.page_limit)
            params: Dict[str, Any] = {
                "$select": ",".join(DEFAULT_SELECT_FIELDS),
                "$order": order_clause,
                "$limit": page_limit,
            }
            if where_clause:
                params["$where"] = where_clause

            logging.info("[dob_complaints] Using date_field=%s", date_field)
            logging.info("[dob_complaints] Server window via :updated_at; client filtering via %s", date_field)
            logging.info(
                "[dob_complaints] Window request since=%s until=%s (dataset_max_parsed=%s)",
                start_iso,
                end_iso,
                wm,
            )
            logging.info("[dob_complaints] using $where: %s", where_clause or "<none>")
            logging.info("[dob_complaints] window_count=%s", window_count)

            crosswalk_available = False
            warned_crosswalk_missing = False
            if not args.dry_run:
                try:
                    crosswalk_available = crosswalk_exists(conn)
                except Exception as exc:  # noqa: BLE001
                    logging.info("[dob_complaints] Unable to check BIN→BBL crosswalk: %r", exc)
                    crosswalk_available = False
                if not crosswalk_available:
                    logging.warning("[dob_complaints] BIN→BBL mapping skipped (pad_bin_bbl not found).")
                    warned_crosswalk_missing = True

            pages = 0
            rows_scanned = 0
            rows_in_window = 0
            rows_with_address = 0
            total_inserted = 0
            total_updated = 0
            offset = 0

            while True:
                page_params = dict(params)
                page_params["$offset"] = offset
                rows = client.query_resource(page_params)
                if not rows:
                    break

                pages += 1

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
                        except Exception as exc:  # noqa: BLE001
                            logging.warning("[dob_complaints] BIN→BBL mapping unavailable: %r", exc)
                            crosswalk_available = False
                            bin_to_bbl = {}
                            if not warned_crosswalk_missing:
                                logging.warning("[dob_complaints] BIN→BBL mapping skipped.")
                                warned_crosswalk_missing = True

                filtered_rows: List[Dict[str, Any]] = []
                for row in rows:
                    rows_scanned += 1

                    dt_value = _parse_dt_safe(row.get(date_field))
                    if not dt_value or not (since_dt <= dt_value < until_dt):
                        continue

                    complaint_number = row.get("complaint_number")
                    if not complaint_number:
                        continue
                    complaint_id = str(complaint_number).strip()
                    if not complaint_id:
                        continue

                    house_number = (row.get("house_number") or "").strip()
                    house_street = (row.get("house_street") or "").strip()
                    zip_code = (row.get("zip_code") or "").strip()
                    bin_text = (row.get("bin") or "").strip()

                    if house_number and house_street:
                        rows_with_address += 1

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

                    rows_in_window += 1
                    filtered_rows.append(record)

                if crosswalk_available and bins_seen and not warned_crosswalk_missing and not bin_to_bbl:
                    logging.info("[dob_complaints] BIN→BBL crosswalk returned no matches for current window.")
                    warned_crosswalk_missing = True

                if filtered_rows and not args.dry_run:
                    inserted, updated = upsert_records(conn, filtered_rows)
                    total_inserted += inserted
                    total_updated += updated

                offset += len(rows)

            summary = (
                f"[dob_complaints] Summary{' (dry-run)' if args.dry_run else ''}: "
                f"pages={pages}, rows_scanned={rows_scanned}, rows_in_window={rows_in_window}, "
                f"rows_with_address={rows_with_address}"
            )
            print(summary)
            logging.info(summary)

            if args.dry_run:
                conn.rollback()
                return 0

            update_watermark(conn, until_dt)
            conn.commit()

            refresh_materialized_view(conn)

            notes_text = f"date_field={date_field}, window=[{start_iso},{end_iso})"
            finished_at = datetime.now(timezone.utc)
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
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            finished_at = datetime.now(timezone.utc)
            if not args.dry_run:
                failure_notes = f"date_field={date_field_for_logs}, window=[{start_iso},{end_iso})"
                try:
                    record_ingest_run(
                        conn,
                        started_at,
                        finished_at,
                        "failed",
                        0,
                        0,
                        str(exc),
                        failure_notes,
                    )
                    conn.commit()
                except Exception:  # noqa: BLE001
                    conn.rollback()
            print(f"[dob_complaints] Error: {exc}", file=sys.stderr)
            raise

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
    exit_code = main()
    # --- end of ingestion ---
    import subprocess, sys, os
    subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "refresh_mv.py")],
        check=True,
    )
    raise SystemExit(exit_code)
