from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class ChatIn(BaseModel):
    question: str
    context_bbl: str | None = None

@router.post("")
def chat(body: ChatIn):
    # Intent parse → call property endpoints → assemble answer_bundle → narrate
    return {
        "answer": "Stub answer with [ACRIS • 2025-01-01]",
        "answer_bundle": {"facts": {}, "tables": {}, "sources": []},
        "citations": []
    }
