import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict

import requests
from sqlalchemy import text
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

SOC_BASE = os.getenv("NYC_SOCRATA_BASE", "https://data.cityofnewyork.us").rstrip("/")
SOC_APP_TOKEN = os.getenv("NYC_SOCRATA_APP_TOKEN")


def row_hash(payload: Any) -> str:
    """Generate a deterministic SHA256 hash from a JSON-serialisable payload."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def stable_bbl(boro: Any, block: Any, lot: Any) -> str | None:
    """
    Return a 10-character BBL string (B + block:05 + lot:04) or None if not valid.
    """
    borough_digit = _normalize_borough(boro)
    block_int = _coerce_int(block)
    lot_int = _coerce_int(lot)
    if not borough_digit or block_int is None or lot_int is None:
        return None
    return f"{borough_digit}{block_int:05d}{lot_int:04d}"


def _normalize_borough(value: Any) -> str | None:
    if value is None:
        return None
    token = str(value).strip().upper()
    if not token:
        return None
    mapping = {
        "1": "1",
        "MANHATTAN": "1",
        "MN": "1",
        "NEW YORK": "1",
        "2": "2",
        "BRONX": "2",
        "BX": "2",
        "3": "3",
        "BROOKLYN": "3",
        "BK": "3",
        "KINGS": "3",
        "4": "4",
        "QUEENS": "4",
        "QN": "4",
        "QNS": "4",
        "5": "5",
        "STATEN ISLAND": "5",
        "SI": "5",
        "RICHMOND": "5",
    }
    return mapping.get(token)


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


@retry(stop=stop_after_attempt(5), wait=wait_exponential(min=1, max=10), reraise=True)
def _socrata_request(resource_id: str, params: Dict[str, Any]) -> list[Dict[str, Any]]:
    url = f"{SOC_BASE}/resource/{resource_id}.json"
    headers = {
        "Accept": "application/json",
        "User-Agent": "propertyfish-ingestor/1.0",
    }
    if SOC_APP_TOKEN:
        headers["X-App-Token"] = SOC_APP_TOKEN
    response = requests.get(url, params=params, headers=headers, timeout=30)
    if response.status_code in {429, 500, 502, 503, 504}:
        _respect_retry_after(response)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise ValueError(f"Unexpected Socrata response for {resource_id}: {data!r}")
    return data


def socrata_fetch(resource_id: str, params: Dict[str, Any]) -> list[Dict[str, Any]]:
    """
    Fetch rows from a Socrata dataset with retry/backoff.
    """
    rows = _socrata_request(resource_id, params)
    logger.debug("Fetched %s rows from %s with params %s", len(rows), resource_id, params)
    return rows


def insert_staging(conn, table: str, source_pk: str, payload: Dict[str, Any]) -> None:
    """
    Insert a raw payload into a staging table using row_hash to dedupe.
    """
    if not source_pk:
        raise ValueError("source_pk is required for staging inserts")
    table_name = _validate_table_name(table)
    payload_json = json.dumps(payload, sort_keys=True)
    hash_value = row_hash(payload)
    conn.execute(
        text(
            f"""
            INSERT INTO {table_name} (source_pk, payload, row_hash)
            VALUES (:source_pk, :payload::jsonb, :row_hash)
            ON CONFLICT (row_hash) DO NOTHING
            """
        ),
        {"source_pk": source_pk, "payload": payload_json, "row_hash": hash_value},
    )


def _validate_table_name(table: str) -> str:
    if not table or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._" for ch in table):
        raise ValueError(f"Unsafe table name: {table}")
    return table


def _respect_retry_after(response: requests.Response) -> None:
    retry_after = response.headers.get("Retry-After")
    if not retry_after:
        return
    wait_seconds: float | None = None
    try:
        wait_seconds = float(retry_after)
    except ValueError:
        try:
            retry_dt = parsedate_to_datetime(retry_after)
        except (TypeError, ValueError):
            retry_dt = None
        if retry_dt is not None:
            if retry_dt.tzinfo is None:
                retry_dt = retry_dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            wait_seconds = max(0.0, (retry_dt - now).total_seconds())
    if wait_seconds is not None:
        capped = min(wait_seconds, 60.0)
        time.sleep(capped)
