from typing import Any, Dict, List, Optional

from app.db.connection import get_conn
from app.utils.resolve import bbl_for_address


def get_summary_by_bbl(bbl: str) -> Optional[Dict[str, Any]]:
    sql = (
        """
        SELECT bbl, address_std AS address, borough, block, lot, bin,
               land_use, tax_class, lot_area_sqft, bldg_sqft, stories, year_built,
               last_updated
        FROM parcels WHERE bbl = %s LIMIT 1;
        """
    )
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (bbl,))
        row = cur.fetchone()
        return dict(row) if row else None


def resolve_candidates(q: str, limit: int = 5) -> List[Dict[str, Any]]:
    like = f"%{q}%"
    sql = (
        """
        SELECT bbl, address_std
        FROM parcels
        WHERE address_std ILIKE %s
        ORDER BY similarity(address_std, %s) DESC
        LIMIT %s;
        """
    )
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (like, q, limit))
        rows = cur.fetchall() or []
        return [dict(r) for r in rows]


def get_deeds_by_bbl(bbl: str, limit: int) -> List[Dict[str, Any]]:
    sql = (
        """
        SELECT recorded_at, consideration, parties, doc_id, doc_url
        FROM acris_events
        WHERE bbl = %s AND doc_type = 'deed'
        ORDER BY recorded_at DESC
        LIMIT %s;
        """
    )
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (bbl, limit))
        rows = cur.fetchall() or []
        return [dict(r) for r in rows]


def get_mortgages_by_bbl(bbl: str, limit: int) -> List[Dict[str, Any]]:
    sql = (
        """
        SELECT recorded_at, consideration, parties, doc_id, doc_url
        FROM acris_events
        WHERE bbl = %s AND doc_type = 'mortgage'
        ORDER BY recorded_at DESC
        LIMIT %s;
        """
    )
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (bbl, limit))
        rows = cur.fetchall() or []
        return [dict(r) for r in rows]


def get_permits_by_bbl(bbl: str, limit: int = 20) -> List[Dict[str, Any]]:
    sql = (
        """
        SELECT job_number,
               status,
               job_type,
               work_type,
               filing_date,
               latest_status_date,
               estimated_cost,
               raw
        FROM dob_permits
        WHERE bbl = %s
        ORDER BY COALESCE(filing_date, latest_status_date) DESC NULLS LAST
        LIMIT %s;
        """
    )
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (bbl, limit))
        rows = cur.fetchall() or []
        return [dict(r) for r in rows]


def get_violations_by_bbl(bbl: str, since: str | None = None) -> List[Dict[str, Any]]:
    # issued_at stored in filed_at; alias on select
    base_sql = (
        """
        SELECT filed_at AS issued_at, details
        FROM permits_violations
        WHERE bbl=%s AND kind='violation'
        """
    )
    params: List[Any] = [bbl]
    if since:
        base_sql += " AND filed_at >= %s"
        params.append(since)
    base_sql += " ORDER BY filed_at DESC"
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(base_sql, tuple(params))
        rows = cur.fetchall() or []
        return [dict(r) for r in rows]


def get_zoning_by_bbl(bbl: str) -> Optional[Dict[str, Any]]:
    sql = (
        """
        SELECT base_codes, overlays, sp_districts, far_notes, last_updated
        FROM zoning_layers WHERE bbl=%s LIMIT 1
        """
    )
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (bbl,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_permits(conn, bbl: str) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT bbl,
                   job_number,
                   status,
                   filing_date AS filed_date,
                   estimated_cost,
                   raw
            FROM dob_permits
            WHERE bbl = %s
            ORDER BY filing_date DESC NULLS LAST
            LIMIT 200
            """,
            (bbl,),
        )
        rows = cur.fetchall() or []
        return [dict(r) for r in rows]


def resolve_to_bbl(conn, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    return bbl_for_address(conn, **params)
