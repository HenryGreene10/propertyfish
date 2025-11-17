from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.routers.search import SearchRow, get_pool, run_search

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    borough: str | None = None
    year_min: int | None = None


class ChatResponse(BaseModel):
    message: str
    total: int
    rows: list[SearchRow]


@router.post("/chat", response_model=ChatResponse)
async def chat_search(payload: ChatRequest, pool=Depends(get_pool)) -> ChatResponse:
    total, rows = await run_search(
        q=payload.message,
        borough=payload.borough,
        floors_min=None,
        units_min=None,
        year_min=payload.year_min,
        permits_min_12m=None,
        sort=None,
        order=None,
        limit=24,
        offset=0,
        pool=pool,
    )

    msg = (
        f"No properties found for: {payload.message}"
        if total == 0
        else f"Found {total} properties for: {payload.message}"
    )

    return ChatResponse(message=msg, total=total, rows=rows)
