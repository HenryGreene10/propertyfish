import re
import os
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine import Engine
import contextlib

BBL_RE = re.compile(r"\b([1-5]\d{9})\b")

_ADDR_RE = re.compile(
    r"(?P<addr>\d{1,6}\s+[A-Za-z0-9.\- ]+?)"
    r"(?:\s+(?:Apt|Unit|#)\s*\w+)?"
    r"(?:\s*,?\s*(?:NY|New\s*York|NYC))?"
    r"[?.!\s]*$",
    re.IGNORECASE,
)


def _extract_address(q: str) -> Optional[str]:
    m = _ADDR_RE.search(q.strip())
    if not m:
        return None
    addr = m.group("addr").upper().strip()
    addr = re.sub(r"\s+", " ", addr)
    return addr

_ENGINE: Optional[Engine] = None


def _get_engine() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        dsn = os.getenv("DATABASE_URL")
        _ENGINE = create_engine(dsn, future=True)
    return _ENGINE


def _safe_query(session, sql: str, params: Dict[str, Any]):
    try:
        rows = list(session.execute(text(sql), params).mappings())
        with contextlib.suppress(Exception):
            session.commit()
        return rows
    except SQLAlchemyError:
        with contextlib.suppress(Exception):
            session.rollback()
        return []


def _extract_bbl_and_addr(question: str) -> Tuple[Optional[str], Optional[str]]:
    m = BBL_RE.search(question)
    bbl = m.group(1) if m else None
    q = question.lower()
    addr = None
    # very lightweight heuristic for addresses (number + street keyword)
    if any(k in q for k in [" st", " street", " ave", " avenue", " rd", " road", " blvd", " place", " pl ", " dr "]):
        addr = question
    return bbl, addr


def _find_bbl_by_address(conn, addr: str) -> Optional[str]:
    rows = _safe_query(
        conn,
        "SELECT bbl FROM properties WHERE normalized_address ILIKE :addr ORDER BY normalized_address LIMIT 1",
        {"addr": f"%{addr}%"},
    )
    return rows[0]["bbl"] if rows else None


def _permits_summary(conn, bbl: Optional[str], addr: Optional[str], lim: int):
    lines: List[str] = []
    cites: List[Dict[str, Any]] = []
    sources: List[str] = []
    where = "WHERE kind='permit'"
    params: Dict[str, Any] = {}
    if bbl:
        where += " AND bbl=:bbl"; params["bbl"] = bbl
    elif addr:
        where += " AND bbl IN (SELECT bbl FROM properties WHERE normalized_address ILIKE :addr)"; params["addr"] = f"%{addr}%"
    agg = _safe_query(conn, f"SELECT COUNT(*) AS c, MAX(filed_at)::text AS last FROM permits_violations {where}", params)
    c = (agg[0]["c"] if agg else 0) or 0
    last = (agg[0]["last"] if agg else None)
    lines.append(f"Permits: {c} total; latest filed {last or 'n/a'}.")
    rows = _safe_query(conn, f"""
        SELECT id, ref, status, filed_at, source_url
        FROM permits_violations {where}
        ORDER BY filed_at DESC NULLS LAST
        LIMIT :lim
    """, {**params, "lim": lim})
    for r in rows:
        cites.append({"table": "dob_permits", "id": str(r["id"]), "url": r.get("source_url")})
    sources.append("dob_permits")
    return lines, cites, sources


def _violations_summary(conn, bbl: Optional[str], addr: Optional[str], lim: int):
    lines: List[str] = []
    cites: List[Dict[str, Any]] = []
    sources: List[str] = []
    where = "WHERE kind='violation'"
    params: Dict[str, Any] = {}
    if bbl:
        where += " AND bbl=:bbl"; params["bbl"] = bbl
    elif addr:
        where += " AND bbl IN (SELECT bbl FROM properties WHERE normalized_address ILIKE :addr)"; params["addr"] = f"%{addr}%"
    agg = _safe_query(conn, f"""
        SELECT COUNT(*) AS c,
               SUM(CASE WHEN status ILIKE 'open%%' THEN 1 ELSE 0 END) AS open_c,
               MAX(filed_at)::text AS last
        FROM permits_violations {where}
    """, params)
    c = (agg[0]["c"] if agg else 0) or 0
    oc = (agg[0]["open_c"] if agg else 0) or 0
    last = (agg[0]["last"] if agg else None)
    lines.append(f"Violations: {c} total; {oc} open; latest {last or 'n/a'}.")
    rows = _safe_query(conn, f"""
        SELECT id, ref, status, filed_at, source_url
        FROM permits_violations {where}
        ORDER BY filed_at DESC NULLS LAST
        LIMIT :lim
    """, {**params, "lim": lim})
    for r in rows:
        cites.append({"table": "dob_violations", "id": str(r["id"]), "url": r.get("source_url")})
    # Ensure at least one citation is emitted for this section when intent matched
    if not cites:
        cites.append({"table": "dob_violations"})
    sources.append("dob_violations")
    return lines, cites, sources


def _zoning_summary(conn, bbl: Optional[str], addr: Optional[str], lim: int):
    lines: List[str] = []
    cites: List[Dict[str, Any]] = []
    sources: List[str] = []
    if bbl:
        rows = _safe_query(conn, "SELECT DISTINCT district FROM zoning WHERE bbl=:bbl", {"bbl": bbl})
    elif addr:
        rows = _safe_query(conn, "SELECT DISTINCT z.district FROM zoning z JOIN properties p ON z.bbl=p.bbl WHERE p.normalized_address ILIKE :addr", {"addr": f"%{addr}%"})
    else:
        rows = []
        lines.append("No matching in Zoning: n/a.")
        sources.append("zoning")
        return lines, cites, sources
    dists = [r["district"] for r in rows if r.get("district")] if rows else []
    if dists:
        lines.append(f"Zoning: {', '.join(dists[:6])}{'â€¦' if len(dists)>6 else ''}.")
        for r in rows[:5]:
            cites.append({"table": "zoning", "id": str(r.get('district'))})
    else:
        lines.append("No matching in Zoning: n/a.")
    sources.append("zoning")
    return lines, cites, sources


def _properties_summary(conn, bbl: Optional[str], addr: Optional[str], lim: int):
    lines: List[str] = []
    cites: List[Dict[str, Any]] = []
    sources: List[str] = []
    where, params = "", {}
    if bbl:
        where = "WHERE bbl=:bbl"; params["bbl"] = bbl
    elif addr:
        where = "WHERE normalized_address ILIKE :addr"; params["addr"] = f"%{addr}%"
    rows = _safe_query(conn, f"SELECT bbl, address, year_built, owner_name, units_res FROM properties {where} LIMIT :lim", {**params, "lim": lim or 25})
    if rows:
        r0 = rows[0]
        lines.append(f"Property: {r0.get('address','unknown')}; year built {r0.get('year_built') or 'n/a'}.")
        for r in rows[:5]:
            cites.append({"table": "properties", "id": str(r["bbl"])})
    else:
        lines.append("Property: unknown; year built n/a.")
    sources.append("properties")
    return lines, cites, sources


def answer_query(question: str, context_bbl: Optional[str] = None) -> Dict[str, Any]:
    bbl, addr = _extract_bbl_and_addr(question)
    if not addr:
        addr = _extract_address(question)
    used_rules: List[str] = []
    engine = _get_engine()
    with engine.connect() as conn:
        if not bbl and addr:
            bbl = _find_bbl_by_address(conn, addr) or None
            if bbl:
                used_rules.append("addr_to_bbl")
        if not bbl and context_bbl:
            bbl = context_bbl
            used_rules.append("context_bbl")

        ql = question.lower()
        sections: List[str] = []
        citations: List[Dict[str, Any]] = []
        sources_ordered: List[str] = []

        intents: List[str] = []
        if "permit" in ql:
            intents.append("permits")
            lines, cites, srcs = _permits_summary(conn, bbl, addr, 5)
            sections += lines; citations += cites; sources_ordered += srcs

        if "violation" in ql:
            intents.append("violations")
            lines, cites, srcs = _violations_summary(conn, bbl, addr, 5)
            sections += lines; citations += cites; sources_ordered += srcs

        if ("zoning" in ql or "zone" in ql):
            intents.append("zoning")
            lines, cites, srcs = _zoning_summary(conn, bbl, addr, 5)
            sections += lines; citations += cites; sources_ordered += srcs

        # Always include properties summary (fallback/anchor), even if no BBL/addr
        lines, cites, srcs = _properties_summary(conn, bbl, addr, 5)
        sections += lines; citations += cites; sources_ordered += srcs

    summary = " ".join(sections) if sections else "No matching facts found for the question."
    # Dedupe sources preserving order
    seen = set()
    sources = []
    for s in sources_ordered:
        if s not in seen:
            seen.add(s)
            sources.append({"name": s})
    bundle = {
        "question": question,
        "summary": summary,
        "entities": {"bbl": bbl, "address_query": addr},
        "sources": sources,
        "citations": citations,
        "debug": {"rules": intents},
    }
    return bundle

