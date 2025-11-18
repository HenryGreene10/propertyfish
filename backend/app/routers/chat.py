import json
import os

import google.generativeai as genai
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.routers.search import SearchRow, get_pool, run_search

router = APIRouter()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


class ChatRequest(BaseModel):
    message: str
    borough: str | None = None
    year_min: int | None = None


class ChatResponse(BaseModel):
    message: str
    total: int
    rows: list[SearchRow]
    filters: "ChatFilters"


class ParsedFilters(BaseModel):
    q: str | None = None
    borough: str | None = None
    year_min: int | None = None
    sort: str | None = None


class ChatFilters(BaseModel):
    q: str | None = None
    borough: str | None = None
    year_min: int | None = None
    sort: str | None = None


def parse_filters_with_gemini(message: str) -> ParsedFilters | None:
    """Use Gemini to turn a natural-language message into structured filters."""
    if not GEMINI_API_KEY:
        return None

    prompt = f"""
You are a filter parser for a New York City property search tool.
Extract intent from the user's message and output STRICT JSON with keys: q, borough, year_min, sort.
- q: free-text search for address, street, building name, etc. Use None if not provided.
- borough: one of ["MN","BK","QN","BX","SI"] (Manhattan, Brooklyn, Queens, Bronx, Staten Island). Use None if unclear.
- year_min: integer minimum year built. Use null if not provided.
- sort: "permits_desc" for most permits/activity first, "yearbuilt_desc" for newest buildings first, or null.

Examples:
"new buildings in queens" -> {{"q": null, "borough": "QN", "year_min": 2000, "sort": "yearbuilt_desc"}}
"lots of recent permits in brooklyn" -> {{"q": null, "borough": "BK", "year_min": null, "sort": "permits_desc"}}
"broadway manhattan after 1990" -> {{"q": "broadway", "borough": "MN", "year_min": 1990, "sort": "permits_desc"}}

User message: {message}
Respond with JSON only, no prose, no code fences.
""".strip()

    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        text = (response.text or "").strip() if response else ""
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        parsed = json.loads(text)
        return ParsedFilters(**parsed)
    except Exception as exc:  # noqa: BLE001
        print(f"parse_filters_with_gemini fallback: {exc}")
        return None


@router.post("/chat", response_model=ChatResponse)
async def chat_search(payload: ChatRequest, pool=Depends(get_pool)) -> ChatResponse:
    q = payload.message
    borough = payload.borough
    year_min = payload.year_min
    sort = None
    order = None

    parsed = parse_filters_with_gemini(payload.message)
    if parsed:
        if parsed.q:
            q = parsed.q
        if parsed.borough:
            borough = parsed.borough
        if parsed.year_min is not None:
            year_min = parsed.year_min
        if parsed.sort:
            sort = parsed.sort

    sort_field = None
    sort_order = None
    if sort == "permits_desc":
        sort_field = "permit_count_12m"
        sort_order = "desc"
    elif sort == "yearbuilt_desc":
        sort_field = "yearbuilt"
        sort_order = "desc"

    total, rows = await run_search(
        q=q,
        borough=borough,
        floors_min=None,
        units_min=None,
        year_min=year_min,
        permits_min_12m=None,
        sort=sort_field,
        order=sort_order,
        limit=24,
        offset=0,
        pool=pool,
        allow_yearbuilt_sort=True,
    )

    msg = (
        f"No properties found for: {payload.message}"
        if total == 0
        else f"Found {total} properties for: {payload.message}"
    )

    applied_filters = ChatFilters(
        q=q,
        borough=borough,
        year_min=year_min,
        sort=sort,
    )

    return ChatResponse(message=msg, total=total, rows=rows, filters=applied_filters)
