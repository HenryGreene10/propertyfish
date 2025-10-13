from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class ChatQuery(BaseModel):
    question: str
    context_bbl: Optional[str] = None


class Citation(BaseModel):
    table: str
    id: Optional[str] = None
    url: Optional[str] = None


class AnswerBundle(BaseModel):
    question: str
    summary: str
    entities: Dict[str, Any] = {}
    sources: List[Dict[str, Any]] = []
    citations: List[Citation] = []
    debug: Dict[str, Any] = {}

