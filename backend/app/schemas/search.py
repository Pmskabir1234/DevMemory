from typing import List
from pydantic import BaseModel


class MatchedSession(BaseModel):
    id: int
    date: str
    summary: str


class SearchResponse(BaseModel):
    query: str
    answer: str
    matched_sessions: List[MatchedSession]
