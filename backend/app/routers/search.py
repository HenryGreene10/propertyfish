from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import asyncpg
import os

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

class SearchItem(BaseModel):
    bbl: str
    address: Optional[str]
    borough: Optional[str]
    zipcode: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    permits_count: Optional[int]
    violations_count: Optional[int]
    permits_last_filed: Optional[str]
    violations_last_issued: Optional[str]

class SearchResponse(BaseModel):
    total: int
    rows: List[SearchItem]

@router.get("/api/search", response_model=SearchResponse)
async def search(
    q: Optional[str] = Query(None, description="free text address"),
    borough: Optional[str] = Query(None, regex="^(MN|BX|BK|QN|SI)$"),
    zipcode: Optional[str] = Query(None, min_length=5, max_length=5),
    min_permits: int = 0,
    min_violations: int = 0,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    pool=Depends(get_pool),
):
    clauses: List[str] = ["1=1"]
    where_args: List[object] = []

    def ph() -> str:
        """Return a placeholder for the next WHERE arg ($1, $2, ...)."""
        return f"${len(where_args) + 1}"

    # q: use twice in WHERE (ILIKE + trigram)
    if q:
        p1 = ph(); where_args.append(q)
        p2 = ph(); where_args.append(q)
        clauses.append(f"(address ILIKE '%' || {p1} || '%' OR address_key % UPPER(unaccent({p2})))")

    if borough:
        p = ph(); where_args.append(borough)
        clauses.append(f"borough = {p}")

    if zipcode:
        p = ph(); where_args.append(zipcode)
        clauses.append(f"zipcode = {p}")

    if min_permits > 0:
        p = ph(); where_args.append(min_permits)
        clauses.append(f"permits_count >= {p}")

    if min_violations > 0:
        p = ph(); where_args.append(min_violations)
        clauses.append(f"violations_count >= {p}")

    base = f"FROM mv_property_search WHERE {' AND '.join(clauses)}"

    # --- total query (WHERE args ONLY) ---
    sql_total = f"SELECT COUNT(*) {base}"

    # --- rows query (WHERE args + optional similarity + limit/offset) ---
    order_by = """
      GREATEST(
        COALESCE(permits_last_filed, '1900-01-01'::date),
        COALESCE(violations_last_issued, '1900-01-01'::date)
      ) DESC
    """

    rows_args: List[object] = list(where_args)

    if q:
        # add one more arg for similarity used in ORDER BY (not in total)
        rows_args.append(q)
        sim_ph = f"${len(where_args) + 1}"  # similarity uses next placeholder relative to WHERE
        order_by = order_by + f", similarity(address_key, UPPER(unaccent({sim_ph}))) DESC"

    # LIMIT/OFFSET placeholders come after WHERE (+ similarity if present)
    rows_args.append(limit)
    rows_args.append(offset)
    lim_ph = f"${len(where_args) + (1 if q else 0) + 1}"
    off_ph = f"${len(where_args) + (1 if q else 0) + 2}"

    sql_rows = f"""
      SELECT bbl, address, borough, zipcode, latitude, longitude,
             permits_count, violations_count,
             TO_CHAR(permits_last_filed, 'YYYY-MM-DD') AS permits_last_filed,
             TO_CHAR(violations_last_issued, 'YYYY-MM-DD') AS violations_last_issued
      {base}
      ORDER BY {order_by}
      LIMIT {lim_ph} OFFSET {off_ph}
    """

    async with (await get_pool()).acquire() as conn:
        total = await conn.fetchval(sql_total, *where_args)
        rows = await conn.fetch(sql_rows, *rows_args)

    return {"total": total, "rows": [dict(r) for r in rows]}

@router.get("/api/properties/{bbl}", response_model=SearchItem)
async def property_detail(bbl: str, pool=Depends(get_pool)):
    q = """
      SELECT bbl, address, borough, zipcode, latitude, longitude,
             permits_count, violations_count,
             TO_CHAR(permits_last_filed, 'YYYY-MM-DD') AS permits_last_filed,
             TO_CHAR(violations_last_issued, 'YYYY-MM-DD') AS violations_last_issued
      FROM mv_property_search
      WHERE bbl = $1
    """
    async with (await get_pool()).acquire() as conn:
        row = await conn.fetchrow(q, bbl)
        if not row:
            raise HTTPException(404, "Not found")
        return dict(row)
