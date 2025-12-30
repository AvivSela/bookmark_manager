from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Integer,
    Index,
    TypeDecorator,
    CHAR,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Dialect
from sqlalchemy.sql import func
from typing import Optional, Any
import uuid
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
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(
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
        elif dialect.name == "postgresql":
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return str(uuid.UUID(value))
            else:
                return str(value)

    def process_result_value(
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
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
            else:
                return value


class Bookmark(Base):
    """Bookmark database model."""

    __tablename__ = "bookmarks"

    # Primary key as UUID
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # User ID for multi-tenancy
    user_id = Column(String(255), nullable=False, index=True)

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

    # Enrichment fields - Open Graph metadata
    og_title = Column(String(500), nullable=True)
    og_description = Column(Text, nullable=True)
    og_image = Column(String(2048), nullable=True)
    og_type = Column(String(100), nullable=True)
    og_site_name = Column(String(200), nullable=True)

    # Enrichment fields - Standard meta tags (fallback)
    meta_description = Column(Text, nullable=True)

    # Enrichment fields - Favicon
    favicon_url = Column(String(2048), nullable=True)

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
        Index("idx_user_bookmarks", "user_id", "created_time"),
        Index("idx_validation_status", "validation_status"),
        Index("idx_validation_last_checked", "validation_last_checked"),
        Index("idx_pending_validation", "validation_status", "validation_last_checked"),
        UniqueConstraint("user_id", "url", name="uq_user_url"),
    )

    def __repr__(self) -> str:
        return f"<Bookmark(id={self.id}, url={self.url}, title={self.title})>"
