from fastapi import FastAPI
from app.core.config import settings
from app.core.logging import setup_logging

# Initialize logging configuration
setup_logging()

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)


@app.get("/")
def read_root():
    return {"status": "healthy", "service": settings.PROJECT_NAME}

