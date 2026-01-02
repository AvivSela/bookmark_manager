import uuid
from typing import Any, Optional

from sqlalchemy import (
    CHAR,
    JSON,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Dialect
from sqlalchemy.sql import func

from app.database import Base


class GUID(TypeDecorator):
    """Platform-independent GUID type.

    Uses PostgreSQL's UUID type when available, otherwise uses
    CHAR(36), storing as stringified hex values.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        """Load the appropriate dialect implementation for this type.

        Args:
            dialect: The SQLAlchemy dialect being used.

        Returns:
            Type descriptor for PostgreSQL UUID or CHAR(36) depending on dialect.
        """
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(  # type: ignore[override]
        self, value: Optional[uuid.UUID | str], dialect: Dialect
    ) -> Optional[str | uuid.UUID]:
        """Process a value being sent to the database.

        Args:
            value: UUID value to bind, either as UUID object or string.
            dialect: The SQLAlchemy dialect being used.

        Returns:
            Processed value: UUID for PostgreSQL, string for other databases.
        """
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value
        if not isinstance(value, uuid.UUID):
            return str(uuid.UUID(value))
        return str(value)

    def process_result_value(  # type: ignore[override]
        self, value: Optional[str | uuid.UUID], dialect: Dialect
    ) -> Optional[uuid.UUID]:
        """Process a value received from the database.

        Args:
            value: Raw value from database (UUID or string).
            dialect: The SQLAlchemy dialect being used.

        Returns:
            UUID object, or None if value was None.
        """
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            return uuid.UUID(value)
        return value


class Bookmark(Base):  # type: ignore[valid-type,misc]
    """Bookmark database model."""

    __tablename__ = "bookmarks"

    # Primary key as UUID
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # Tenant ID for multi-tenancy
    tenant_id = Column(String(255), nullable=False, index=True)

    # URL field - indexed but not globally unique (unique per user)
    url = Column(String(2048), nullable=False, index=True)

    # Title and description
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)

    # Timestamps with automatic updates
    created_time = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    changed_time = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Enrichment fields - All enrichment data stored as JSON
    enrichments = Column(JSON, nullable=True)

    # Resource type detection (kept separate for filtering/querying)
    resource_type = Column(
        String(50), nullable=True
    )  # 'webpage', 'api', 'dataset', etc.

    # Validation fields
    validation_status = Column(
        String(20), nullable=True
    )  # 'valid', 'invalid', 'pending', 'error'
    validation_last_checked = Column(DateTime(timezone=True), nullable=True)
    validation_http_status = Column(Integer, nullable=True)  # HTTP status code
    validation_final_url = Column(
        String(2048), nullable=True
    )  # Final URL after redirects
    validation_error_message = Column(Text, nullable=True)  # Error details

    # Indexes and constraints for multi-tenancy
    __table_args__ = (
        Index("idx_bookmark_created_time", "created_time"),
        Index("idx_tenant_bookmarks", "tenant_id", "created_time"),
        Index("idx_validation_status", "validation_status"),
        Index("idx_validation_last_checked", "validation_last_checked"),
        Index("idx_pending_validation", "validation_status", "validation_last_checked"),
        Index(
            "idx_resource_type", "resource_type"
        ),  # NEW: Index for resource type filtering
        UniqueConstraint("tenant_id", "url", name="uq_tenant_url"),
    )

    def __repr__(self) -> str:
        return f"<Bookmark(id={self.id}, url={self.url}, title={self.title})>"
