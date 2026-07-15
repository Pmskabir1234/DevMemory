from fastapi import FastAPI
from app.core.config import settings
from app.core.logging import setup_logging
from app.api.router import api_router
from app.api.endpoints.health import router as health_router

# Initialize logging configuration
setup_logging()

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)

# Include routers
app.include_router(health_router, tags=["health"])
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
def read_root():
    return {"status": "healthy", "service": settings.PROJECT_NAME}

