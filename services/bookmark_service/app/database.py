from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import get_settings

settings = get_settings()

# Create async engine with connection pooling
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,  # Log SQL in debug mode
    pool_pre_ping=True,    # Verify connections before using
    pool_size=5,           # Number of connections in pool
    max_overflow=10        # Max connections beyond pool_size
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False  # Don't expire objects after commit
)

# Base class for models
Base = declarative_base()


async def get_db() -> AsyncSession:
    """
    Dependency for route handlers to get database session.

    Yields:
        AsyncSession: Database session
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Create all tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
