from typing import Any, Dict, List, Optional

from app.db.connection import get_conn


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
