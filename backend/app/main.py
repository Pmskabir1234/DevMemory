from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from app.core.config import settings
from app.core.logging import setup_logging
from app.api.router import api_router
from app.api.endpoints.health import router as health_router

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """On startup: backfill summaries for any sessions that never got one."""
    try:
        from app.db.session import SessionLocal
        from app.services.session import summarise_unsummarised
        db = SessionLocal()
        try:
            updated = summarise_unsummarised(db)
            if updated:
                logger.info(
                    "Startup backfill: generated summaries for %d session(s): %s",
                    len(updated),
                    [s.id for s in updated],
                )
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Startup backfill failed: %s", exc)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

# Include routers
app.include_router(health_router, tags=["health"])
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def read_root():
    return {"status": "healthy", "service": settings.PROJECT_NAME}
