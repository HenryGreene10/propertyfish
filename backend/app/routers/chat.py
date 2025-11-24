import json
import logging
import os
import re

import google.generativeai as genai
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.routers.search import SearchRow, get_pool, run_search

router = APIRouter()
logger = logging.getLogger(__name__)

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


BOROUGH_KEYWORD_PATTERNS = [
    (re.compile(r"\bmanhattan\b", re.IGNORECASE), "MN"),
    (re.compile(r"\bnew york\b", re.IGNORECASE), "MN"),
    (re.compile(r"\bbrooklyn\b", re.IGNORECASE), "BK"),
    (re.compile(r"\bbronx\b", re.IGNORECASE), "BX"),
    (re.compile(r"\bqueens\b", re.IGNORECASE), "QN"),
    (re.compile(r"\bstaten\s+island\b", re.IGNORECASE), "SI"),
]

STREET_PATTERN = re.compile(
    r"\b\d{1,5}\s+[A-Za-z0-9\s]+?(?:street|st|avenue|ave|road|rd|boulevard|blvd|place|pl|way)\b",
    re.IGNORECASE,
)

YEAR_PATTERN = re.compile(r"\b(18|19|20)\d{2}\b")


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
        logger.warning("parse_filters_with_gemini fallback: %s", exc)
        return None


def _extract_borough(text: str, previous: ChatFilters | None) -> str | None:
    for pattern, code in BOROUGH_KEYWORD_PATTERNS:
        if pattern.search(text):
            return code
    return previous.borough if previous and previous.borough else None


def _extract_query(text: str, previous: ChatFilters | None) -> str | None:
    pronoun_ref = bool(re.search(r"\b(those|them|that|these|ones)\b", text, re.IGNORECASE))
    if pronoun_ref and previous and previous.q:
        return previous.q
    street_match = STREET_PATTERN.search(text)
    if street_match:
        return street_match.group(0).strip()
    trimmed = text.strip()
    if trimmed:
        return trimmed[:120]
    if previous and previous.q:
        return previous.q
    return None


def _extract_year(text: str, previous: ChatFilters | None) -> int | None:
    match = YEAR_PATTERN.search(text)
    if match:
        year = int(match.group(0))
        if 1800 <= year <= 2100:
            return year
    if previous and previous.year_min is not None:
        return previous.year_min
    return None


def infer_filters_from_message(message: str, previous: ChatFilters | None) -> ChatFilters:
    return ChatFilters(
        q=_extract_query(message, previous),
        borough=_extract_borough(message, previous),
        year_min=_extract_year(message, previous),
        sort=previous.sort if previous else None,
    )


def relax_filters(filters: ChatFilters) -> tuple[ChatFilters | None, str]:
    changes: list[str] = []
    new_year = filters.year_min
    if new_year is not None:
        lowered = new_year - 10
        if lowered < 1800:
            new_year = None
            changes.append("removed the minimum year filter")
        else:
            new_year = lowered
            changes.append(f"lowered the minimum year to {new_year}")
    new_sort = filters.sort
    if new_sort:
        new_sort = None
        changes.append("cleared the sort preference")

    if not changes:
        return None, ""

    relaxed = ChatFilters(
        q=filters.q,
        borough=filters.borough,
        year_min=new_year,
        sort=new_sort,
    )
    description = ", ".join(changes)
    return relaxed, description


def resolve_sort_fields(sort: str | None) -> tuple[str | None, str | None]:
    if sort == "permits_desc":
        return "permit_count_12m", "desc"
    if sort == "yearbuilt_desc":
        return "yearbuilt", "desc"
    return None, None


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
    else:
        logger.warning("Gemini parsing failed; falling back to heuristic filters for '%s'", payload.message)
        heuristic = infer_filters_from_message(payload.message, previous_filters)
        if heuristic.q is not None:
            q = heuristic.q
        if heuristic.borough is not None:
            borough = heuristic.borough
        if heuristic.year_min is not None:
            year_min = heuristic.year_min
        if heuristic.sort:
            sort = heuristic.sort

    sort_field, sort_order = resolve_sort_fields(sort)

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

    applied_filters = ChatFilters(
        q=q,
        borough=borough,
        year_min=year_min,
        sort=sort,
    )

    msg = f"Found {total} properties for: {payload.message}"

    if total == 0:
        relaxed_filters, relaxation_desc = relax_filters(applied_filters)
        if relaxed_filters:
            logger.info(
                "Initial chat search returned 0 rows; relaxing filters (%s)",
                relaxation_desc,
            )
            relaxed_sort_field, relaxed_sort_order = resolve_sort_fields(relaxed_filters.sort)
            total_relaxed, rows_relaxed = await run_search(
                q=relaxed_filters.q,
                borough=relaxed_filters.borough,
                floors_min=None,
                units_min=None,
                year_min=relaxed_filters.year_min,
                permits_min_12m=None,
                sort=relaxed_sort_field,
                order=relaxed_sort_order,
                limit=24,
                offset=0,
                pool=pool,
                allow_yearbuilt_sort=True,
            )
            if total_relaxed > 0:
                total = total_relaxed
                rows = rows_relaxed
                applied_filters = relaxed_filters
                msg = (
                    f"Nothing matched the stricter filters, so I broadened the search ({relaxation_desc}) "
                    f"and found {total} properties for: {payload.message}"
                )
            else:
                total = total_relaxed
                rows = rows_relaxed
                msg = (
                    "I couldn't find anything that matched that, even after broadening the filters. "
                    "Try a different street or removing the year filter."
                )
        else:
            msg = (
                "I couldn't find anything that matched that. Try adjusting the street or removing filters like year."
            )

    return ChatResponse(message=msg, total=total, rows=rows, filters=applied_filters)
