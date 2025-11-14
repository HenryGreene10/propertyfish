from datetime import date
from typing import Optional
import logging
import os
import re

import asyncpg
from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel

from settings.config import settings

router = APIRouter()
_POOL: Optional[asyncpg.Pool] = None

logger = logging.getLogger(__name__)

BOROUGH_ABBREVS = {"MN", "BX", "BK", "QN", "SI"}
BOROUGH_NAME_MAP = {
    "MANHATTAN": "MN",
    "NY": "MN",
    "NEW YORK": "MN",
    "BRONX": "BX",
    "BROOKLYN": "BK",
    "KINGS": "BK",
    "QUEENS": "QN",
    "STATEN ISLAND": "SI",
}

_TABLE_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\.]+$")


def _coerce_table_name(value: Optional[str]) -> str:
    candidate = (value or "property_search").strip()
    if not candidate or not _TABLE_NAME_PATTERN.fullmatch(candidate):
        raise RuntimeError(
            "Invalid TABLE_SEARCH value; only letters, numbers, underscores, and dots are allowed.",
        )
    return candidate


TABLE_SEARCH = _coerce_table_name(settings.TABLE_SEARCH)


async def get_pool():
    global _POOL
    if _POOL is None:
        _POOL = await asyncpg.create_pool(
            dsn=os.getenv("DATABASE_URL"),
            min_size=2,
            max_size=int(os.getenv("DB_POOL_MAX", "12")),
            command_timeout=30,
        )
    return _POOL


class SearchRow(BaseModel):
    bbl: str
    address: str
    borough: str
    borough_full: Optional[str] = None

    zipcode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    yearbuilt: Optional[int] = None
    numfloors: Optional[float] = None
    unitsres: Optional[int] = None
    unitstotal: Optional[int] = None
    zonedist1: Optional[str] = None
    landuse: Optional[str] = None
    bldgarea: Optional[int] = None
    lotarea: Optional[int] = None

    permit_count_12m: int = 0
    last_permit_date: Optional[date] = None


class SearchResponse(BaseModel):
    total: int
    rows: list[SearchRow]


@router.get("/api/search", response_model=SearchResponse)
async def search(
    q: Optional[str] = Query(None, description="Free-text address or BBL"),
    borough: Optional[str] = Query(None, description="Two-letter code or borough name"),
    floors_min: Optional[int] = Query(None, ge=0),
    units_min: Optional[int] = Query(None, ge=0),
    year_min: Optional[int] = Query(None, ge=0),
    permits_min_12m: Optional[int] = Query(None, ge=0),
    sort: Optional[str] = Query(
        None,
        description="Sort field: last_permit_date|year_built|permit_count_12m|relevance",
    ),
    order: Optional[str] = Query(None, description="asc|desc"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    pool=Depends(get_pool),
):
    """Search property inventory with optional filters.

    Response rows expose the limited property_search view fields (address, borough labels, permit_count_12m, last_permit_date); other attributes remain placeholders.
    """
    limit = max(1, min(limit, 50))
    offset = max(0, offset)

    select_columns = [
        "(ps.bbl)::text AS bbl",
        "ps.address AS address",
        "ps.borough AS borough",
        "ps.borough_full AS borough_full",
        "NULL::text AS zipcode",
        "NULL::float8 AS latitude",
        "NULL::float8 AS longitude",
        "ps.yearbuilt AS yearbuilt",
        "ps.numfloors::float8 AS numfloors",
        "ps.unitsres AS unitsres",
        "ps.unitstotal AS unitstotal",
        "ps.zonedist1 AS zonedist1",
        "ps.landuse AS landuse",
        "ps.bldgarea AS bldgarea",
        "ps.lotarea AS lotarea",
        "ps.permit_count_12m AS permit_count_12m",
        "ps.last_permit_date AS last_permit_date",
    ]

    where_clauses: list[str] = ["1=1"]
    where_args: list[object] = []
    active_filters: list[str] = []

    def add_param(value: object) -> str:
        where_args.append(value)
        return f"${len(where_args)}"

    normalized_q = q.strip() if isinstance(q, str) else None
    if normalized_q:
        like_value = f"%{normalized_q}%"
        clause_parts = [
            "ps.address ILIKE " + add_param(like_value),
            "(ps.bbl)::text ILIKE " + add_param(like_value),
            "ps.borough_full ILIKE " + add_param(like_value),
        ]
        where_clauses.append("(" + " OR ".join(clause_parts) + ")")
        active_filters.append("q")
    elif normalized_q is not None and not normalized_q:
        normalized_q = None

    borough_filter = None
    if borough:
        token = borough.strip().upper()
        if token in BOROUGH_ABBREVS:
            borough_filter = token
        else:
            borough_filter = BOROUGH_NAME_MAP.get(token.replace(".", ""))
        if not borough_filter:
            raise HTTPException(400, "Invalid borough; use MN,BX,BK,QN,SI or full names")
    if borough_filter:
        where_clauses.append(f"ps.borough = {add_param(borough_filter)}")
        active_filters.append("borough")

    if floors_min is not None:
        logger.debug("PF-BE-SEARCH ignoring floors_min until column is available")
    if units_min is not None:
        logger.debug("PF-BE-SEARCH ignoring units_min until column is available")

    if year_min is not None:
        logger.debug("PF-BE-SEARCH skipping year_min; restricted column set")

    if permits_min_12m is not None:
        where_clauses.append(f"ps.permit_count_12m >= {add_param(permits_min_12m)}")
        active_filters.append("permits_min_12m")

    # property_search_rich_mv exposes extended PLUTO attributes used here
    base = f"FROM {TABLE_SEARCH} ps WHERE " + " AND ".join(where_clauses)

    sql_total = f"SELECT COUNT(*) {base}"

    normalized_sort = (sort or "").strip().lower() or None
    normalized_order = (order or "").strip().lower() or None

    valid_sorts = {"last_permit_date", "permit_count_12m", "relevance"}
    if normalized_sort and normalized_sort not in valid_sorts:
        raise HTTPException(400, f"Invalid sort '{normalized_sort}'")

    if normalized_order not in {"asc", "desc"}:
        normalized_order = "desc"

    def nulls_clause(direction: str) -> str:
        return "NULLS LAST" if direction == "desc" else "NULLS FIRST"

    order_by_parts: list[str] = []
    rows_args: list[object] = list(where_args)

    similarity_placeholder = None
    use_similarity = bool(normalized_q and normalized_sort in (None, "relevance"))
    if use_similarity:
        similarity_placeholder = f"${len(rows_args) + 1}"
        rows_args.append(normalized_q)

    if use_similarity and similarity_placeholder:
        order_by_parts.append(
            f"similarity(ps.address, UPPER(unaccent({similarity_placeholder}))) DESC NULLS LAST",
        )
        if normalized_sort == "relevance":
            active_filters.append("sort=relevance")
        normalized_sort = "last_permit_date"

    if normalized_sort == "relevance" and not normalized_q:
        normalized_sort = None

    def append_sort(column: str, direction: str):
        order_by_parts.append(
            f"ps.{column} {'DESC' if direction == 'desc' else 'ASC'} {nulls_clause(direction)}",
        )

    if normalized_sort == "last_permit_date":
        append_sort("last_permit_date", normalized_order)
    elif normalized_sort == "permit_count_12m":
        append_sort("permit_count_12m", normalized_order)

    append_sort("last_permit_date", "desc")
    order_by_parts.append("ps.bbl ASC")
    order_by = ", ".join(order_by_parts)

    lim_ph = f"${len(rows_args) + 1}"
    rows_args.append(limit)
    off_ph = f"${len(rows_args) + 1}"
    rows_args.append(offset)

    sql_rows = f"""
      SELECT
        {', '.join(select_columns)}
      {base}
      ORDER BY {order_by}
      LIMIT {lim_ph} OFFSET {off_ph}
    """

    validated_params = {
        "q": q if normalized_q else None,
        "borough": borough_filter,
        "year_min": year_min,
        "permits_min_12m": permits_min_12m,
        "sort": sort,
        "order": normalized_order,
        "limit": limit,
        "offset": offset,
    }
    logger.info(
        "PF-BE-SEARCH params: %s order: %s where: %s",
        {k: v for k, v in validated_params.items() if v not in (None, "")},
        order_by,
        ", ".join(active_filters) or "none",
    )
    logger.debug("PF-BE-SEARCH sql_total: %s params=%s", sql_total.strip(), list(where_args))
    logger.debug("PF-BE-SEARCH sql_rows: %s params=%s", sql_rows.strip(), list(rows_args))

    try:
        async with pool.acquire() as conn:
            total = await conn.fetchval(sql_total, *where_args)
            rows = await conn.fetch(sql_rows, *rows_args)
    except (asyncpg.exceptions.UndefinedTableError, asyncpg.exceptions.UndefinedColumnError) as exc:
        logger.exception("PF-BE-SEARCH relation/columns missing for table %s", TABLE_SEARCH)
        raise HTTPException(
            status_code=500,
            detail="Search backing relation/columns not found. Create the 'property_search' view or set TABLE_SEARCH.",
        ) from exc

    return {"total": total, "rows": [dict(r) for r in rows]}


@router.get("/api/properties/{bbl}", response_model=SearchRow)
async def property_detail(bbl: str, pool=Depends(get_pool)):
    q = """
      SELECT
        (ps.bbl)::text                   AS bbl,
        ps.address                       AS address,
        ps.borough                       AS borough,

        NULL::text                       AS zipcode,
        NULL::float8                     AS latitude,
        NULL::float8                     AS longitude,
        ps.yearbuilt                     AS yearbuilt,
        ps.numfloors::float8             AS numfloors,
        ps.unitsres                      AS unitsres,
        ps.unitstotal                    AS unitstotal,
        ps.zonedist1                     AS zonedist1,
        ps.landuse                       AS landuse,
        ps.bldgarea                      AS bldgarea,
        ps.lotarea                       AS lotarea,

        ps.permit_count_12m              AS permit_count_12m,
        ps.last_permit_date              AS last_permit_date
      FROM property_search_rich_mv ps
      WHERE ps.bbl = $1
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(q, bbl)
        if not row:
            raise HTTPException(404, "Not found")
        return dict(row)
