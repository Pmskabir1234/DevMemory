"""
CLI configuration — reads from environment variables or falls back to defaults.
"""
import os

BACKEND_URL: str = os.getenv("DEVMEM_BACKEND_URL", "http://127.0.0.1:8000")
VERSION: str = "1.0.0"
DEFAULT_LIMIT: int = 10
REQUEST_TIMEOUT: int = 10  # seconds
