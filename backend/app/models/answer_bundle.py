from pydantic import BaseModel
from typing import Any, Dict, List

class AnswerBundle(BaseModel):
    bbl: str | None = None
    facts: Dict[str, Any] = {}
    tables: Dict[str, Any] = {}
    sources: List[dict] = []
