from fastapi import APIRouter
import os
from app.models.dto import ChatQuery, AnswerBundle
from app.services.chat import answer_query

router = APIRouter()


@router.post("/chat/query", response_model=AnswerBundle)
async def chat_query(payload: ChatQuery):
    bundle = answer_query(payload.question, context_bbl=payload.context_bbl)
    if os.getenv("ENV") == "prod":
        if bundle.get("debug") and isinstance(bundle.get("debug"), dict) and "sql" in bundle["debug"]:
            try:
                bundle["debug"]["sql"] = bundle["debug"]["sql"][:10]
            except Exception:
                bundle["debug"]["sql"] = []
    return bundle
