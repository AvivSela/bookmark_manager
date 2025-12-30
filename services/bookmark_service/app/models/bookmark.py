from sqlalchemy import Column, String, Text, DateTime, Index, TypeDecorator, CHAR, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func
import uuid
from app.database import Base


class GUID(TypeDecorator):
    """Platform-independent GUID type.

    Uses PostgreSQL's UUID type when available, otherwise uses
    CHAR(36), storing as stringified hex values.
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return str(uuid.UUID(value))
            else:
                return str(value)

    def process_result_value(self, value, dialect):
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
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    changed_time = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
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

    # Indexes and constraints for multi-tenancy
    __table_args__ = (
        Index('idx_bookmark_created_time', 'created_time'),
        Index('idx_user_bookmarks', 'user_id', 'created_time'),
        UniqueConstraint('user_id', 'url', name='uq_user_url'),
    )

    def __repr__(self):
        return f"<Bookmark(id={self.id}, url={self.url}, title={self.title})>"
