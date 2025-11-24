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


class ChatFilters(BaseModel):
    q: str | None = None
    borough: str | None = None
    year_min: int | None = None
    sort: str | None = None


class ChatRequest(BaseModel):
    message: str
    borough: str | None = None
    year_min: int | None = None
    previous_filters: ChatFilters | None = None


class ChatResponse(BaseModel):
    message: str
    total: int
    rows: list[SearchRow]
    filters: ChatFilters


class ParsedFilters(BaseModel):
    q: str | None = None
    borough: str | None = None
    year_min: int | None = None
    sort: str | None = None


def parse_filters_with_gemini(
    message: str,
    previous: ChatFilters | None = None,
) -> ParsedFilters | None:
    """Use Gemini to turn a natural-language message into structured filters."""
    if not GEMINI_API_KEY:
        return None

    previous_json = json.dumps(previous.model_dump()) if previous else "null"
    prompt = f"""
You are a filter parser for a New York City property search tool.
Your job is to return STRICT JSON with keys: q, borough, year_min, sort.

Previous filters (JSON): {previous_json}
User message: {message}

Rules:
- If previous filters are not null, treat them as the starting point. Only change q, borough, year_min, or sort when the new message clearly changes them. Words such as "those", "them", or "now only" refer to the previous results.
- q: address, street, or building keyword. Keep the prior q unless a new location/building is clearly stated.
- borough: one of ["MN","BK","QN","BX","SI"]. Keep the prior borough unless the user names a different borough.
- year_min: integer minimum year built. Adjust it when the user mentions a minimum year; otherwise keep the previous year_min.
- sort: "permits_desc" for most active, "yearbuilt_desc" for newest, or null.
- Always return the FINAL filters after applying the new instructions (not just a diff).

Examples:
prev={{"q":"10th st","borough":"MN","year_min":null,"sort":null}}, message="now only if they are from 2020" -> {{"q":"10th st","borough":"MN","year_min":2020,"sort":null}}
prev=null, message="new buildings in queens" -> {{"q":null,"borough":"QN","year_min":2000,"sort":"yearbuilt_desc"}}

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
    previous_filters = payload.previous_filters
    q = payload.message
    borough = payload.borough
    year_min = payload.year_min
    sort = None
    order = None

    if previous_filters:
        if previous_filters.q:
            q = previous_filters.q
        if previous_filters.borough:
            borough = previous_filters.borough
        if previous_filters.year_min is not None:
            year_min = previous_filters.year_min
        if previous_filters.sort:
            sort = previous_filters.sort

    parsed = parse_filters_with_gemini(payload.message, previous=previous_filters)
    if parsed:
        if parsed.q is not None:
            q = parsed.q
        if parsed.borough is not None:
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
