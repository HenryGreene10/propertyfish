from fastapi import APIRouter, HTTPException
from app.services.property_service import (
    get_summary_by_bbl,
    get_deeds_by_bbl,
    get_mortgages_by_bbl,
    get_permits_by_bbl,
    get_violations_by_bbl,
    get_zoning_by_bbl,
)
from datetime import datetime, timezone

router = APIRouter()

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

@router.get("/{bbl}/permits")
def permits(bbl: str, since: str | None = None):
    rows = get_permits_by_bbl(bbl, since)
    source = {
        "name": "NYC DOB",
        "updated": datetime.now(timezone.utc).isoformat(),
        "url": "https://data.cityofnewyork.us",
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
