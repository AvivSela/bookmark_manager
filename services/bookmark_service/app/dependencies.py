from fastapi import Header, HTTPException, status
from typing import Annotated
import re

USER_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')


async def get_current_user_id(
    x_user_id: Annotated[str | None, Header()] = None
) -> str:
    """
    Extract and validate user_id from X-User-ID header.

    Args:
        x_user_id: User ID from X-User-ID header

    Returns:
        str: Validated user ID

    Raises:
        HTTPException: 401 if header is missing, empty, too long, or contains invalid characters
    """
    if x_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-ID header"
        )

    if not x_user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-ID cannot be empty"
        )

    if len(x_user_id) > 255:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-ID exceeds maximum length of 255 characters"
        )

    if not USER_ID_PATTERN.match(x_user_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-ID contains invalid characters (allowed: a-z, A-Z, 0-9, _, -)"
        )

    return x_user_id
