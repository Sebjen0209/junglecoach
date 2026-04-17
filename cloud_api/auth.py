"""Supabase JWT authentication for FastAPI.

Validates the Bearer token on every protected request by calling
supabase.auth.get_user() — this delegates verification to Supabase's
auth service and handles key rotation automatically.

Usage in a route:

    from auth import CurrentUser

    @router.get("/protected")
    def my_route(current_user: CurrentUser):
        user_id = current_user["id"]
"""

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from db.supabase import get_client

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=True)


async def _validate_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Security(_bearer_scheme)],
) -> dict:
    """Validate a Supabase Bearer JWT and return the authenticated user payload.

    Returns:
        dict with keys 'id' (UUID str) and 'email' (str).

    Raises:
        HTTPException 401: If the token is absent, expired, or invalid.
    """
    token = credentials.credentials
    try:
        response = get_client().auth.get_user(token)
        user = response.user
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return {"id": str(user.id), "email": user.email}
    except HTTPException:
        raise
    except Exception as exc:
        # Log at warning — this is a client error, not a server error
        logger.warning("Token validation failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# Annotated type alias — use this as a route parameter type
CurrentUser = Annotated[dict, Depends(_validate_token)]
