from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.search import SearchResponse
from app.services.search import answer_query

router = APIRouter()


@router.get("/search", response_model=SearchResponse)
def search(
    query: str = Query(..., description="Natural language question or keyword"),
    workspace: str | None = Query(None, description="Filter by workspace path"),
    db: Session = Depends(get_db),
):
    """
    Search development sessions or answer a natural language question
    using stored development memory.

    Examples:
    - `?query=What did I work on yesterday?`
    - `?query=auth.py`
    - `?query=resume`
    """
    result = answer_query(db, query=query, workspace=workspace)
    return SearchResponse(
        query=result["query"],
        answer=result["answer"],
        matched_sessions=result["matched_sessions"],
    )
