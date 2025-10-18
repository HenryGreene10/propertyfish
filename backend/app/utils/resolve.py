from typing import Dict, List, Optional, Tuple

from app.ingestion.normalizers import normalize_street, normalize_text


def _split_address(address: str) -> Tuple[str, str]:
    normalized = normalize_text(address)
    if not normalized:
        return "", ""
    parts = normalized.split(" ", 1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def bbl_for_address(
    conn,
    *,
    address: Optional[str] = None,
    houseno: Optional[str] = None,
    street: Optional[str] = None,
    borough: Optional[str] = None,
    limit: int = 25,
) -> List[Dict[str, str]]:
    if address and not (houseno and street):
        houseno, street = _split_address(address)

    street_norm = normalize_street(street or "")
    houseno = (houseno or "").strip()
    borough = (borough or "").upper()

    params = {
        "boro": borough,
        "street": street_norm,
        "street_raw": street_norm,
        "houseno": houseno,
        "limit": limit,
    }

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT bbl, address, street, zipcode
            FROM pluto
            WHERE (%(boro)s = '' OR borough = %(boro)s)
              AND upper(street) = %(street)s
              AND (%(houseno)s = '' OR houseno = %(houseno)s)
            ORDER BY address
            LIMIT %(limit)s
            """,
            params,
        )
        rows = cur.fetchall()
        if rows:
            return [dict(r) for r in rows]

        cur.execute(
            """
            SELECT bbl, address, street, zipcode
            FROM pluto
            WHERE (%(boro)s = '' OR borough = %(boro)s)
              AND upper(street) ILIKE '%%' || %(street_raw)s || '%%'
              AND (%(houseno)s = '' OR houseno = %(houseno)s)
            ORDER BY address
            LIMIT %(limit)s
            """,
            params,
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
