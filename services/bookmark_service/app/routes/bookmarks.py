from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, func, desc, asc
from uuid import UUID
from typing import Literal, Optional
from datetime import datetime, timezone
from app.database import get_db
from app.models.bookmark import Bookmark
from app.schemas.bookmark import (
    BookmarkCreate,
    BookmarkUpdate,
    BookmarkResponse,
    BookmarkListResponse,
)
from app.config import get_settings
from app.dependencies import get_current_tenant_id
from app.kafka import get_kafka_producer
from app.kafka.producer import KafkaEventProducer

settings = get_settings()
router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])


@router.post(
    "",
    response_model=BookmarkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new bookmark",
)
async def create_bookmark(
    bookmark: BookmarkCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    kafka_producer: Optional[KafkaEventProducer] = Depends(get_kafka_producer),
) -> BookmarkResponse:
    """
    Create a new bookmark with the following fields:
    - **url**: Valid HTTP/HTTPS URL (must be unique per tenant)
    - **title**: Bookmark title (1-500 characters)
    - **description**: Optional description (max 5000 characters)

    Requires X-Tenant-ID header for authentication.
    """
    try:
        bookmark_data = bookmark.model_dump()
        bookmark_data["url"] = str(bookmark.url)
        bookmark_data["tenant_id"] = tenant_id

        db_bookmark = Bookmark(**bookmark_data)
        db.add(db_bookmark)
        await db.commit()
        await db.refresh(db_bookmark)

        # Publish bookmark.created event
        if kafka_producer:
            await kafka_producer.publish_event(
                event_type="created",
                bookmark_data=BookmarkResponse.model_validate(db_bookmark).model_dump(
                    mode="json"
                ),
            )

        return BookmarkResponse.model_validate(db_bookmark)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A bookmark with this URL already exists",
        )


@router.get(
    "",
    response_model=BookmarkListResponse,
    summary="List all bookmarks with pagination",
)
async def list_bookmarks(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(
        settings.default_page_size,
        ge=1,
        le=settings.max_page_size,
        description=f"Items per page (max {settings.max_page_size})",
    ),
    sort_by: Literal["created_time", "changed_time", "title"] = Query(
        "created_time", description="Field to sort by"
    ),
    sort_order: Literal["asc", "desc"] = Query("desc", description="Sort order"),
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
) -> BookmarkListResponse:
    """
    Retrieve a paginated list of bookmarks for the authenticated tenant.

    Query parameters:
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 50, max: 100)
    - **sort_by**: Field to sort by (created_time, changed_time, title)
    - **sort_order**: Sort order (asc, desc)

    Requires X-Tenant-ID header for authentication.
    """
    # Calculate pagination
    offset = (page - 1) * page_size

    # Build query with sorting and tenant filter
    sort_column = getattr(Bookmark, sort_by)
    order_func = desc if sort_order == "desc" else asc

    # Fetch one extra item to determine if there's a next page
    query = (
        select(Bookmark)
        .where(Bookmark.tenant_id == tenant_id)
        .order_by(order_func(sort_column))
        .offset(offset)
        .limit(page_size + 1)
    )

    result = await db.execute(query)
    all_items = result.scalars().all()

    # Determine if there's a next page
    has_next = len(all_items) > page_size
    items = all_items[:page_size]  # Return only requested amount

    return BookmarkListResponse(
        items=[BookmarkResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        has_next=has_next,
    )


@router.get(
    "/{bookmark_id}",
    response_model=BookmarkResponse,
    summary="Get a single bookmark by ID",
)
async def get_bookmark(
    bookmark_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
) -> BookmarkResponse:
    """
    Retrieve a specific bookmark by its UUID.

    Raises 404 if the bookmark doesn't exist or doesn't belong to the tenant.
    Requires X-Tenant-ID header for authentication.
    """
    query = select(Bookmark).where(
        Bookmark.id == bookmark_id, Bookmark.tenant_id == tenant_id
    )
    result = await db.execute(query)
    bookmark = result.scalar_one_or_none()

    if not bookmark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bookmark with id '{bookmark_id}' not found",
        )

    return BookmarkResponse.model_validate(bookmark)


@router.put(
    "/{bookmark_id}", response_model=BookmarkResponse, summary="Update a bookmark"
)
async def update_bookmark(
    bookmark_id: UUID,
    bookmark_update: BookmarkUpdate,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    kafka_producer: Optional[KafkaEventProducer] = Depends(get_kafka_producer),
) -> BookmarkResponse:
    """
    Update an existing bookmark. Supports partial updates.

    All fields are optional:
    - **url**: New URL (must be unique per tenant if changed)
    - **title**: New title
    - **description**: New description

    The `changed_time` field is automatically updated.
    Requires X-Tenant-ID header for authentication.
    """
    # Get existing bookmark for tenant
    query = select(Bookmark).where(
        Bookmark.id == bookmark_id, Bookmark.tenant_id == tenant_id
    )
    result = await db.execute(query)
    bookmark = result.scalar_one_or_none()

    if not bookmark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bookmark with id '{bookmark_id}' not found",
        )

    # Update fields
    update_data = bookmark_update.model_dump(exclude_unset=True)

    # Convert URL to string if present
    if "url" in update_data:
        update_data["url"] = str(update_data["url"])

    try:
        for field, value in update_data.items():
            setattr(bookmark, field, value)

        # Manually update changed_time for databases that don't support onupdate
        bookmark.changed_time = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(bookmark)

        # Publish bookmark.updated event
        if kafka_producer:
            await kafka_producer.publish_event(
                event_type="updated",
                bookmark_data=BookmarkResponse.model_validate(bookmark).model_dump(
                    mode="json"
                ),
            )

        return BookmarkResponse.model_validate(bookmark)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A bookmark with this URL already exists",
        )


@router.delete(
    "/{bookmark_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a bookmark",
)
async def delete_bookmark(
    bookmark_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    kafka_producer: Optional[KafkaEventProducer] = Depends(get_kafka_producer),
) -> None:
    """
    Delete a bookmark by its UUID.

    Raises 404 if the bookmark doesn't exist or doesn't belong to the tenant.
    Requires X-Tenant-ID header for authentication.
    """
    query = select(Bookmark).where(
        Bookmark.id == bookmark_id, Bookmark.tenant_id == tenant_id
    )
    result = await db.execute(query)
    bookmark = result.scalar_one_or_none()

    if not bookmark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bookmark with id '{bookmark_id}' not found",
        )

    # Capture minimal data before deletion for event
    bookmark_data = {
        "id": str(bookmark.id),
        "tenant_id": bookmark.tenant_id,
        "url": str(bookmark.url),
    }

    await db.delete(bookmark)
    await db.commit()

    # Publish bookmark.deleted event
    if kafka_producer:
        await kafka_producer.publish_event(
            event_type="deleted", bookmark_data=bookmark_data
        )
