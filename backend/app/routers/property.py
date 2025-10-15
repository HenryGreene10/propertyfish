from datetime import datetime, timezone
from typing import Any, Dict, Generator, List

from fastapi import APIRouter, Depends, HTTPException

from app.db.connection import get_conn as get_conn_cm
from app.services.property_service import (
    get_deeds_by_bbl,
    get_mortgages_by_bbl,
    get_permits,
    get_permits_by_bbl,
    get_summary_by_bbl,
    get_violations_by_bbl,
    get_zoning_by_bbl,
    resolve_to_bbl,
)


def get_conn() -> Generator:
    with get_conn_cm() as conn:
        yield conn


router = APIRouter(prefix="/api/property", tags=["property"])
legacy_router = APIRouter(prefix="/property", tags=["property"])


def _resolve(
    conn,
    address: str | None = None,
    houseno: str | None = None,
    street: str | None = None,
    borough: str | None = None,
):
    results = resolve_to_bbl(
        conn,
        {
            "address": address,
            "houseno": houseno,
            "street": street,
            "borough": borough,
        },
    )
    if not results:
        raise HTTPException(status_code=404, detail="No match")
    return results


@router.get("/resolve")
def resolve(
    address: str | None = None,
    houseno: str | None = None,
    street: str | None = None,
    borough: str | None = None,
    conn=Depends(get_conn),
):
    return _resolve(conn, address, houseno, street, borough)


@router.get("/{bbl}/permits")
def permits(bbl: str, conn=Depends(get_conn)) -> List[Dict[str, Any]]:
    return get_permits(conn, bbl)


@router.get("/{bbl}/summary")
def summary(bbl: str):
    row = get_summary_by_bbl(bbl)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    sources = [
        {
            "name": "PLUTO/MapPLUTO",
            "updated": row.get("last_updated"),
            "url": "https://www.nyc.gov/site/planning/data-maps/open-data/dwn-pluto-mappluto.page",
        }
    ]
    out = {k: v for k, v in row.items() if k != "last_updated"}
    out["sources"] = sources
    return out


@router.get("/{bbl}/zoning")
def zoning(bbl: str):
    row = get_zoning_by_bbl(bbl)
    source = {
        "name": "ZoLa/DCP",
        "updated": datetime.now(timezone.utc).isoformat(),
        "url": "https://zola.planning.nyc.gov",
    }
    if not row:
        return {"base": [], "overlays": [], "sp_districts": [], "far_notes": None, "sources": [source]}
    return {
        "base": row.get("base_codes") or [],
        "overlays": row.get("overlays") or [],
        "sp_districts": row.get("sp_districts") or [],
        "far_notes": row.get("far_notes"),
        "sources": [source],
    }


@router.get("/{bbl}/deeds")
def deeds(bbl: str, limit: int = 5):
    rows = get_deeds_by_bbl(bbl, limit)
    source = {
        "name": "ACRIS – Real Property Legals/Master",
        "updated": datetime.now(timezone.utc).isoformat(),
        "url": "https://www.nyc.gov/site/finance/property/acris.page",
    }
    return {"rows": rows, "sources": [source]}


@router.get("/{bbl}/mortgages")
def mortgages(bbl: str, limit: int = 5):
    rows = get_mortgages_by_bbl(bbl, limit)
    source = {
        "name": "ACRIS – Real Property Legals/Master",
        "updated": datetime.now(timezone.utc).isoformat(),
        "url": "https://www.nyc.gov/site/finance/property/acris.page",
    }
    return {"rows": rows, "sources": [source]}


@router.get("/{bbl}/violations")
def violations(bbl: str, since: str | None = None):
    rows = get_violations_by_bbl(bbl, since)
    source = {
        "name": "NYC DOB",
        "updated": datetime.now(timezone.utc).isoformat(),
        "url": "https://data.cityofnewyork.us",
    }
    return {"rows": rows, "sources": [source]}


@router.get("/{bbl}/geo")
def geo(bbl: str):
    return {"parcel": None}


@legacy_router.get("/resolve")
def resolve_legacy(
    address: str | None = None,
    houseno: str | None = None,
    street: str | None = None,
    borough: str | None = None,
    conn=Depends(get_conn),
):
    return _resolve(conn, address, houseno, street, borough)


@legacy_router.get("/{bbl}/summary")
def summary_legacy(bbl: str):
    return summary(bbl)


@legacy_router.get("/{bbl}/zoning")
def zoning_legacy(bbl: str):
    return zoning(bbl)


@legacy_router.get("/{bbl}/deeds")
def deeds_legacy(bbl: str, limit: int = 5):
    return deeds(bbl, limit)


@legacy_router.get("/{bbl}/mortgages")
def mortgages_legacy(bbl: str, limit: int = 5):
    return mortgages(bbl, limit)


@legacy_router.get("/{bbl}/permits")
def permits_legacy(bbl: str, limit: int = 20):
    rows = get_permits_by_bbl(bbl, limit)
    source = {
        "name": "NYC DOB",
        "updated": datetime.now(timezone.utc).isoformat(),
        "url": "https://data.cityofnewyork.us",
    }
    return {"rows": rows, "sources": [source]}


@legacy_router.get("/{bbl}/violations")
def violations_legacy(bbl: str, since: str | None = None):
    return violations(bbl, since)


@legacy_router.get("/{bbl}/geo")
def geo_legacy(bbl: str):
    return geo(bbl)
