from datetime import date
from typing import Optional

import asyncpg
import os
from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel

router = APIRouter()
_POOL: Optional[asyncpg.Pool] = None


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

    zipcode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    year_built: Optional[int] = None
    floors: Optional[int] = None
    units_total: Optional[int] = None

    permits_last_12m: int = 0
    last_permit_date: Optional[date] = None


class SearchResponse(BaseModel):
    total: int
    rows: list[SearchRow]

@router.get("/api/search", response_model=SearchResponse)
async def search(
    q: Optional[str] = Query(None, description="free text address"),
    borough: Optional[str] = Query(None, regex="^(MN|BX|BK|QN|SI)$"),
    zipcode: Optional[str] = Query(None, min_length=5, max_length=5),
    bbox: Optional[str] = Query(None, description="minLng,minLat,maxLng,maxLat"),
    min_permits: int = 0,
    min_violations: int = 0,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    pool=Depends(get_pool),
):
    """Search property inventory with optional filters.

    Response rows include year_built, floors, units_total, permits_last_12m, and last_permit_date.
    """
    clauses: list[str] = ["1=1"]
    where_args: list[object] = []

    def ph() -> str:
        return f"${len(where_args) + 1}"

    # q used twice in WHERE
    if q:
        p1 = ph(); where_args.append(q)
        p2 = ph(); where_args.append(q)
        clauses.append(
            f"(ps.address ILIKE '%' || {p1} || '%' OR ps.address_key % UPPER(unaccent({p2})))",
        )

    if borough:
        p = ph(); where_args.append(borough)
        clauses.append(f"ps.borough = {p}")

    if zipcode:
        p = ph(); where_args.append(zipcode)
        clauses.append(f"ps.zipcode = {p}")

    if min_permits > 0:
        p = ph(); where_args.append(min_permits)
        clauses.append(f"ps.permit_count >= {p}")

    if min_violations > 0:
        p = ph(); where_args.append(min_violations)
        clauses.append(f"ps.violations_count >= {p}")

    # bbox: minLng,minLat,maxLng,maxLat
    if bbox:
        try:
            minLng, minLat, maxLng, maxLat = [float(x) for x in bbox.split(",")]
        except Exception:
            raise HTTPException(400, "Invalid bbox; expected minLng,minLat,maxLng,maxLat")
        p1 = ph(); where_args.append(minLng)
        p2 = ph(); where_args.append(minLat)
        p3 = ph(); where_args.append(maxLng)
        p4 = ph(); where_args.append(maxLat)
        clauses.append(f"ps.geom_4326 && ST_MakeEnvelope({p1}, {p2}, {p3}, {p4}, 4326)")

    base = (
        "FROM property_search ps "
        f"WHERE {' AND '.join(clauses)}"
    )

    # total (WHERE args only)
    sql_total = f"SELECT COUNT(*) {base}"

    # rows (WHERE args + similarity arg (if q) + limit/offset)
    order_by = (
        "GREATEST("
        "COALESCE(ps.last_permit_date, '1900-01-01'::date), "
        "'1900-01-01'::date"
        ") DESC"
    )
    rows_args: list[object] = list(where_args)

    if q:
        # similarity extra arg (not part of where_args)
        rows_args.append(q)
        sim_ph = f"${len(where_args) + 1}"
        order_by += f", similarity(ps.address_key, UPPER(unaccent({sim_ph}))) DESC"

    # limit/offset placeholders are after WHERE (+1 if q)
    rows_args.append(limit)
    rows_args.append(offset)
    lim_ph = f"${len(where_args) + (1 if q else 0) + 1}"
    off_ph = f"${len(where_args) + (1 if q else 0) + 2}"

    sql_rows = f"""
      SELECT
        (ps.bbl)::text                   AS bbl,
        ps.address                       AS address,
        ps.borough                       AS borough,

        NULL::text                       AS zipcode,
        NULL::float8                     AS latitude,
        NULL::float8                     AS longitude,
        NULL::int                        AS year_built,
        NULL::int                        AS floors,
        NULL::int                        AS units_total,

        ps.permit_count                  AS permits_last_12m,
        ps.last_permit_date              AS last_permit_date
      {base}
      ORDER BY {order_by}
      LIMIT {lim_ph} OFFSET {off_ph}
    """

    async with pool.acquire() as conn:
        total = await conn.fetchval(sql_total, *where_args)
        rows = await conn.fetch(sql_rows, *rows_args)

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
        NULL::int                        AS year_built,
        NULL::int                        AS floors,
        NULL::int                        AS units_total,

        ps.permit_count                  AS permits_last_12m,
        ps.last_permit_date              AS last_permit_date
      FROM property_search ps
      WHERE ps.bbl = $1::bigint
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(q, bbl)
        if not row:
            raise HTTPException(404, "Not found")
        return dict(row)
