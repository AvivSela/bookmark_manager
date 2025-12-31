import pytest
import asyncio
from typing import AsyncGenerator, Generator, Optional
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.main import app
from app.database import Base, get_db
from app.models.bookmark import Bookmark


# Test database URL - using in-memory SQLite for fast tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
def test_tenant_id() -> str:
    """Default test tenant ID."""
    return "550e8400-e29b-41d4-a716-446655440000"


@pytest.fixture
def test_tenant_id_2() -> str:
    """Second test tenant for multi-tenant tests."""
    return "6ba7b810-9dad-11d1-80b4-00c04fd430c8"


# SQLite doesn't have a native UUID type, so we need to register type decorators
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Set SQLite pragmas for better performance"""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Create a fresh test database for each test function.

    Uses SQLite in-memory database for fast, isolated tests.
    StaticPool ensures all connections share the same in-memory database.
    """
    # Import models to ensure they're registered with Base
    from app.models import bookmark  # noqa: F401

    # Create async engine with StaticPool for shared in-memory database
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # Provide session for test
    async with async_session_maker() as session:
        yield session

    # Cleanup: drop all tables after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(scope="function")
async def client(
    test_db: AsyncSession, test_tenant_id: str
) -> AsyncGenerator[AsyncClient, None]:
    """
    Create a test client with overridden database dependency and tenant authentication.

    This ensures all API requests use the test database and default test tenant.
    """

    async def override_get_db():
        yield test_db

    # Override the database dependency
    app.dependency_overrides[get_db] = override_get_db

    # Create async HTTP client with tenant authentication header
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Tenant-ID": test_tenant_id},
    ) as ac:
        yield ac

    # Clear overrides after test
    app.dependency_overrides.clear()


@pytest.fixture
def authenticated_client(test_db: AsyncSession):
    """Factory to create clients with different tenant IDs for multi-tenancy testing.

    Usage:
        client1 = await authenticated_client("550e8400-e29b-41d4-a716-446655440001")
        client2 = await authenticated_client("550e8400-e29b-41d4-a716-446655440002")

    Args:
        test_db: Test database session.

    Returns:
        Callable that creates AsyncClient instances with custom tenant IDs.
    """

    async def _create_client(tenant_id: str) -> AsyncClient:
        async def override_get_db():
            yield test_db

        app.dependency_overrides[get_db] = override_get_db

        return AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"X-Tenant-ID": tenant_id},
        )

    return _create_client


@pytest.fixture
def sample_bookmark_data() -> dict:
    """Provide sample bookmark data for testing.

    Returns:
        dict: Dictionary with valid bookmark fields (url, title, description).
    """
    return {
        "url": "https://example.com",
        "title": "Example Bookmark",
        "description": "This is a test bookmark",
    }


@pytest.fixture
async def create_bookmark(test_db: AsyncSession):
    """Helper fixture to create bookmarks directly in the test database.

    Usage:
        bookmark = await create_bookmark(
            url="https://test.com",
            title="Test",
            description="Description",
            tenant_id="550e8400-e29b-41d4-a716-446655440000"
        )

    Args:
        test_db: Test database session.

    Returns:
        Callable that creates Bookmark instances in the database.
    """

    async def _create_bookmark(
        url: str = "https://example.com",
        title: str = "Test Bookmark",
        description: Optional[str] = None,
        tenant_id: str = "550e8400-e29b-41d4-a716-446655440000",
    ) -> Bookmark:
        bookmark = Bookmark(
            url=url, title=title, description=description, tenant_id=tenant_id
        )
        test_db.add(bookmark)
        await test_db.commit()
        await test_db.refresh(bookmark)
        return bookmark

    return _create_bookmark


@pytest.fixture
def mock_kafka_producer():
    """Mock Kafka producer to prevent actual Kafka connections in tests.

    Returns:
        list: List that collects all published events for assertion.

    Yields:
        list: Published events accumulator for test assertions.
    """
    published_events = []

    class MockKafkaProducer:
        async def publish_event(self, event_type: str, bookmark_data: dict):
            published_events.append({"event_type": event_type, "data": bookmark_data})
            return True

    # Override the global Kafka producer
    import app.kafka

    original_producer = app.kafka._kafka_producer
    app.kafka._kafka_producer = MockKafkaProducer()

    yield published_events

    # Restore original producer after test
    app.kafka._kafka_producer = original_producer
