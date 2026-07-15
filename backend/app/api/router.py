from fastapi import APIRouter

from app.api.endpoints import events, sessions, search

api_router = APIRouter()

# Register routes
api_router.include_router(events.router, tags=["events"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(search.router, tags=["search"])
