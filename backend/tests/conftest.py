"""
Shared pytest fixtures.

All tests share an in-memory SQLite database that is created fresh for every
test function.  The FastAPI app's `get_db` dependency is overridden so every
test runs in complete isolation without touching the real devmem.db file.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sqlalchemy.pool import StaticPool

# The declarative Base lives here; importing it creates the metadata registry.
from app.db.session import Base, get_db
from app.main import app

# ---------------------------------------------------------------------------
# In-memory SQLite — one engine per test session, isolated DB per test
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def db_engine():
    """Create all tables in an isolated in-memory SQLite database."""
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Return a SQLAlchemy session bound to the test engine."""
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=db_engine
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db_session):
    """
    FastAPI TestClient with the real `get_db` dependency overridden so every
    HTTP request uses the per-test in-memory database.
    """

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass  # session lifecycle managed by db_session fixture

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()
