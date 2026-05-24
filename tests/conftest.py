"""
Test Fixtures
─────────────
- Isolated file-based SQLite DB (background workers need shared state)
- Fresh schema per test function
- Patched session factory so workers use the test DB
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.main import app
from src.database import Base, get_db
import src.database as _db_module

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_closira.db"

test_engine = create_async_engine(
    TEST_DATABASE_URL, echo=False, connect_args={"check_same_thread": False}
)
TestSessionLocal = async_sessionmaker(
    bind=test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_test_db():
    """Create fresh tables before each test, drop after."""
    from src import models  # noqa: F401

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session):
    """Async HTTP client with DB overrides for both requests and background tasks."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    original = _db_module.AsyncSessionLocal
    _db_module.AsyncSessionLocal = TestSessionLocal

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    _db_module.AsyncSessionLocal = original
    app.dependency_overrides.clear()
