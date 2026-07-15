from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.event import EventCreate, EventResponse
from app.services.event import record_event

router = APIRouter()


@router.post("/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(event_in: EventCreate, db: Session = Depends(get_db)):
    db_event = record_event(db, event_in)
    return EventResponse(
        id=db_event.id,
        status="recorded",
        session_id=db_event.session_id,
    )
