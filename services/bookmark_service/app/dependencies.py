from fastapi import Header, HTTPException, status
from typing import Annotated
import re

TENANT_ID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


async def get_current_tenant_id(x_tenant_id: Annotated[str | None, Header()] = None) -> str:
    """
    Extract and validate tenant_id from X-Tenant-ID header.

    Args:
        x_tenant_id: Tenant ID from X-Tenant-ID header

    Returns:
        str: Validated tenant ID

    Raises:
        HTTPException: 401 if header is missing, empty, too long, or contains invalid characters
    """
    if x_tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-Tenant-ID header"
        )

    if not x_tenant_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="X-Tenant-ID cannot be empty"
        )

    if len(x_tenant_id) > 255:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Tenant-ID exceeds maximum length of 255 characters",
        )

    if not TENANT_ID_PATTERN.match(x_tenant_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Tenant-ID must be a valid UUID format (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)",
        )

    return x_tenant_id
