from fastapi import APIRouter, Query
from app.services.property_service import resolve_candidates

router = APIRouter()


@router.get("")
def resolve(query: str = Query(..., min_length=2), limit: int = 5):
    return {"candidates": resolve_candidates(query, limit=limit)}
