from pydantic import BaseModel
from typing import Any, List, Dict

class SourceMeta(BaseModel):
    name: str
    updated: str | None = None
    url: str | None = None

class SummaryOut(BaseModel):
    bbl: str
    address: str | None = None
    borough: str | None = None
    block: int | None = None
    lot: int | None = None
    bin: int | None = None
    land_use: str | None = None
    tax_class: str | None = None
    lot_area_sqft: int | None = None
    bldg_sqft: int | None = None
    stories: int | None = None
    year_built: int | None = None
    sources: List[SourceMeta] = []
