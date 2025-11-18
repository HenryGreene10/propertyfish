import logging
import os
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Generator, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import routes as api_routes
from app.db.connection import get_conn as get_conn_cm
from app.ingestion.normalizers import normalize_pluto as normalize_pluto_row
from app.routers import chat, property as property_router, resolve, search as search_router
from app.utils.normalize import normalize_borough

app = FastAPI(title="PropertyFish API", version="0.1.0")

_cors_origins = {
    "http://localhost:3000",
}
_env_frontend_origin = os.getenv("FRONTEND_ORIGIN")
if _env_frontend_origin:
    _cors_origins.add(_env_frontend_origin.strip())

_env_cors = os.getenv("CORS_ORIGINS")
if _env_cors:
    _cors_origins.update(
        origin.strip()
        for origin in _env_cors.split(",")
        if origin.strip()
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(_cors_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(resolve.router, prefix="/resolve", tags=["resolve"])
app.include_router(property_router.router)
app.include_router(property_router.legacy_router)
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(api_routes.router, prefix="/api", tags=["chat-query"])
app.include_router(search_router.router)

BOROUGH_CODE_TO_ABBR = {
    "1": ("MN", "Manhattan"),
    "2": ("BX", "Bronx"),
    "3": ("BK", "Brooklyn"),
    "4": ("QN", "Queens"),
    "5": ("SI", "Staten Island"),
}

BOROUGH_ABBRS = {abbr for abbr, _ in BOROUGH_CODE_TO_ABBR.values()}

logger = logging.getLogger(__name__)


def normalize_bbl(value: str | int) -> int:
    # "1015457502.000000000" -> 1015457502
    if isinstance(value, int):
        return value
    return int(Decimal(str(value)))


def _borough_labels_from_bbl(bbl_int: int) -> tuple[Optional[str], Optional[str]]:
    digits = str(bbl_int)
    if digits:
        entry = BOROUGH_CODE_TO_ABBR.get(digits[0])
        if entry:
            return entry
    return None, None


def _borough_labels_from_code(code: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if not code:
        return None, None
    entry = BOROUGH_CODE_TO_ABBR.get(str(code)[0])
    if entry:
        return entry
    return None, None


def _maybe_decimal_to_float(value: Any):
    if isinstance(value, Decimal):
        return float(value)
    return value


def _safe_float(value: Any) -> Optional[float]:
    if value in (None, "", "N/A"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_lower_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    return {str(key).lower(): value for key, value in data.items()}


def _to_iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def get_conn() -> Generator:
    with get_conn_cm() as conn:
        yield conn


@app.get("/property/{bbl}")
async def get_property(bbl: str, limit: int = 5):
    try:
        bbl_int = normalize_bbl(bbl)
    except (InvalidOperation, ValueError):
        raise HTTPException(status_code=400, detail="Invalid BBL")

    limit = max(1, min(limit, 50))

    base_sql = """
      SELECT p.bbl, p.address, p.zipcode, p.borough, p.houseno, p.street,
             p.latitude, p.longitude, p.raw
      FROM public.pluto p
      WHERE NULLIF(p.bbl,'')::bigint = $1::bigint
      LIMIT 1
    """

    agg_sql = """
      SELECT permit_count_12m, last_permit_date
      FROM public.mv_permit_agg
      WHERE bbl_norm = $1::bigint
    """

    recent_sql = """
      SELECT job_number, status, issuance_date_norm, filing_date, filed_date
      FROM public.permits_norm
      WHERE bbl_text ~ '^[0-9]+$'
        AND bbl_text::bigint = $1::bigint
      ORDER BY issuance_date_norm DESC NULLS LAST
      LIMIT $2
    """

    async with (await search_router.get_pool()).acquire() as conn:
        base_row = await conn.fetchrow(base_sql, bbl_int)
        if base_row is None:
            raise HTTPException(status_code=404, detail="Not found")

        agg_row = await conn.fetchrow(agg_sql, bbl_int)
        recent_rows = await conn.fetch(recent_sql, bbl_int, limit)

    raw_pluto = base_row["raw"] or {}
    raw_lower = _to_lower_dict(raw_pluto) if isinstance(raw_pluto, dict) else {}
    normalized_pluto = normalize_pluto_row(raw_pluto) if isinstance(raw_pluto, dict) else {}

    centroid = None
    if base_row["latitude"] is not None and base_row["longitude"] is not None:
        centroid = {
            "latitude": float(base_row["latitude"]),
            "longitude": float(base_row["longitude"]),
        }

    bbox = None
    xmin = raw_lower.get("xmin")
    ymin = raw_lower.get("ymin")
    xmax = raw_lower.get("xmax")
    ymax = raw_lower.get("ymax")
    if all(value not in (None, "", "N/A") for value in (xmin, ymin, xmax, ymax)):
        try:
            bbox = [float(xmin), float(ymin), float(xmax), float(ymax)]
        except (TypeError, ValueError):
            bbox = None

    pluto_data = {
        "bbl": base_row["bbl"],
        "address": base_row["address"],
        "zipcode": base_row["zipcode"],
        "borough": base_row["borough"],
        "house_number": base_row["houseno"],
        "street": base_row["street"],
        "block": normalized_pluto.get("block"),
        "lot": normalized_pluto.get("lot"),
        "land_use": normalized_pluto.get("landuse"),
        "lot_area": _maybe_decimal_to_float(normalized_pluto.get("lot_area")),
        "building_area": _maybe_decimal_to_float(normalized_pluto.get("bldg_area")),
        "units_residential": normalized_pluto.get("units_res"),
        "units_rental": normalized_pluto.get("units_rent"),
        "year_built": normalized_pluto.get("year_built"),
        "num_floors": _safe_float(raw_lower.get("numfloors")),
        "latitude": float(base_row["latitude"]) if base_row["latitude"] is not None else None,
        "longitude": float(base_row["longitude"]) if base_row["longitude"] is not None else None,
        "geometry": {
            "centroid": centroid,
            "bbox": bbox,
        },
    }

    agg_data = {
        "permit_count_12m": agg_row["permit_count_12m"] if agg_row else 0,
        "last_permit_date": _to_iso(agg_row["last_permit_date"]) if agg_row else None,
    }

    recent_permits = [
        {
            "job_number": row["job_number"],
            "status": row["status"],
            "issuance_date_norm": _to_iso(row["issuance_date_norm"]),
            "filing_date": _to_iso(row["filing_date"]),
            "filed_date": _to_iso(row["filed_date"]),
        }
        for row in recent_rows
    ]

    borough_abbr, borough_full = _borough_labels_from_bbl(bbl_int)
    if not borough_abbr:
        borough_abbr, borough_full = _borough_labels_from_code(normalized_pluto.get("borough"))
    if not borough_abbr and base_row["borough"]:
        borough_code, borough_name = normalize_borough(base_row["borough"])
        if borough_code:
            borough_abbr, borough_full = _borough_labels_from_code(borough_code)
        elif borough_name:
            borough_full = borough_name.title()
            borough_abbr = (borough_name[:2] or "").upper()

    return {
        "bbl": bbl_int,
        "address": base_row["address"],
        "borough": borough_abbr,
        "borough_full": borough_full,
        "pluto": pluto_data,
        "agg": agg_data,
        "recent_permits": recent_permits,
    }


@app.get("/search")
def search(
    q: Optional[str] = Query(None, description="Free-text query"),
    borough: Optional[str] = Query(None, description="Comma-separated borough codes"),
    sort: Optional[str] = Query(None, description="e.g. permit_count:desc"),
    year_built_gte: Optional[int] = Query(None, ge=0),
    year_built_lte: Optional[int] = Query(None, ge=0),
    units_total_gte: Optional[int] = Query(None, ge=0),
    units_total_lte: Optional[int] = Query(None, ge=0),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    conn=Depends(get_conn),
):
    logger.debug(
        "search params q=%s borough=%s sort=%s limit=%s offset=%s",
        q,
        borough,
        sort,
        limit,
        offset,
    )

    with conn.cursor() as cur_meta:
        cur_meta.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'property_search'
            """,
        )
        available_columns = {row["column_name"] for row in cur_meta.fetchall()}

    optional_columns = {
        column for column in {"year_built", "units_total"} if column in available_columns
    }

    select_columns: List[str] = [
        "address",
        "bbl",
        "borough",
        "borough_full",
        "permit_count",
        "last_permit_date",
    ]
    if "year_built" in optional_columns:
        select_columns.append("year_built")
    else:
        select_columns.append("NULL AS year_built")
    if "units_total" in optional_columns:
        select_columns.append("units_total")
    else:
        select_columns.append("NULL AS units_total")

    where_clauses: List[str] = ["1=1"]
    params: List[Any] = []

    if q:
        term = q.strip()
        if term:
            like_value = f"%{term}%"
            where_clauses.append(
                "(address ILIKE %s OR borough_full ILIKE %s OR CAST(bbl AS TEXT) ILIKE %s)",
            )
            params.extend([like_value, like_value, like_value])

    borough_values: List[str] = []
    if borough:
        tokens = [token.strip().upper() for token in borough.split(",")]
        for token in tokens:
            if not token:
                continue
            if token in BOROUGH_ABBRS:
                borough_values.append(token)
                continue
            code, _ = normalize_borough(token)
            if code and code in BOROUGH_CODE_TO_ABBR:
                borough_values.append(BOROUGH_CODE_TO_ABBR[code][0])
        borough_values = sorted({value for value in borough_values if value})
        if borough_values:
            placeholders = ", ".join(["%s"] * len(borough_values))
            where_clauses.append(f"UPPER(borough) IN ({placeholders})")
            params.extend(borough_values)

    numeric_filters = [
        ("year_built_gte", ">=", "year_built"),
        ("year_built_lte", "<=", "year_built"),
        ("units_total_gte", ">=", "units_total"),
        ("units_total_lte", "<=", "units_total"),
    ]
    for param_name, operator, column in numeric_filters:
        value = locals().get(param_name)
        if value is None:
            continue
        if column not in optional_columns:
            logger.debug("Skipping filter %s; column %s not available", param_name, column)
            continue
        where_clauses.append(f"{column} {operator} %s")
        params.append(value)

    sort_mapping = {
        "permit_count:desc": "permit_count DESC, bbl ASC",
        "last_permit_date:desc": "last_permit_date DESC NULLS LAST, bbl ASC",
    }
    if "year_built" in optional_columns:
        sort_mapping["year_built:desc"] = "year_built DESC NULLS LAST, bbl ASC"

    order_by_clause = sort_mapping.get(sort or "", "permit_count DESC, bbl ASC")

    where_sql = " AND ".join(where_clauses)
    where_params = tuple(params)

    logger.debug("search WHERE: %s params=%s", where_sql, where_params)
    logger.debug("search ORDER BY: %s", order_by_clause)

    count_sql = f"""
        SELECT COUNT(*)::bigint AS total_count
        FROM public.property_search
        WHERE {where_sql}
    """
    rows_sql = f"""
        SELECT {', '.join(select_columns)}
        FROM public.property_search
        WHERE {where_sql}
        ORDER BY {order_by_clause}
        LIMIT %s OFFSET %s
    """

    with conn.cursor() as cur:
        cur.execute(count_sql, where_params)
        count_row = cur.fetchone() or {}
        total = int(count_row.get("total_count") or 0)

        rows_params = where_params + (limit, offset)
        cur.execute(rows_sql, rows_params)
        rows = cur.fetchall()

    results: List[Dict[str, Any]] = []
    for row in rows:
        row_bbl = row.get("bbl")
        normalized_bbl: Optional[str] = None
        if row_bbl is not None:
            try:
                normalized_bbl = str(normalize_bbl(row_bbl))
            except (InvalidOperation, ValueError):
                normalized_bbl = str(row_bbl)

        permit_count = row.get("permit_count")
        if isinstance(permit_count, Decimal):
            permit_count_value = int(permit_count)
        else:
            permit_count_value = permit_count

        results.append(
            {
                "bbl": normalized_bbl,
                "address": row.get("address"),
                "borough": row.get("borough"),
                "borough_full": row.get("borough_full"),
                "permit_count_12m": permit_count_value if permit_count_value is not None else None,
                "last_permit_date": _to_iso(row.get("last_permit_date")),
                "year_built": row.get("year_built"),
                "units_total": row.get("units_total"),
            },
        )

    return {"results": results, "total": total}


@app.get("/parcels/{bbl}")
def parcel_detail(bbl: str, conn=Depends(get_conn)):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                bbl,
                address,
                borough,
                zipcode,
                houseno,
                street,
                latitude,
                longitude,
                updated_at
            FROM pluto
            WHERE bbl = %s
            """,
            (bbl,),
        )
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Not found")

    data = {
        "bbl": row["bbl"],
        "address": row["address"],
        "borough": row["borough"],
        "zipcode": row["zipcode"],
        "houseno": row["houseno"],
        "street": row["street"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "updated_at": row["updated_at"],
        "latest_permits": [],
    }
    return data


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/version")
def version():
    return {"service": "propertyfish-chat", "env": os.getenv("ENV", "dev")}

@app.get("/")
def root():
    return {"ok": True, "service": "propertyfish"}
