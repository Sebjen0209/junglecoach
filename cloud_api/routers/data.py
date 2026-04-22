"""Data versioning endpoints.

GET  /data/latest    — public; desktop clients poll this on startup to check
                       whether their local matchup DB is stale.

POST /data/versions  — internal; called by the GitHub Actions scraper job after
                       a successful scrape + upload. Protected by SCRAPER_SECRET.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import settings
from db.patch import get_latest_version, prune_old_versions, upsert_version
from models import DataVersion

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data", tags=["data"])

_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Auth dependency — validates the scraper's secret bearer token
# ---------------------------------------------------------------------------

def _require_scraper_secret(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    """Raise 401 if the request doesn't carry the correct SCRAPER_SECRET."""
    if not settings.scraper_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SCRAPER_SECRET is not configured on this server.",
        )
    if creds is None or creds.credentials != settings.scraper_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing scraper secret.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------------------------------------------------------------------------
# Request body for POST /data/versions
# ---------------------------------------------------------------------------

from pydantic import BaseModel, Field, HttpUrl


class _VersionPayload(BaseModel):
    patch: str = Field(..., pattern=r"^\d+\.\d+$", examples=["16.9"])
    db_url: str = Field(..., description="Public URL of the uploaded matchups.db file.")
    row_count: int = Field(..., ge=1)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/latest",
    response_model=DataVersion,
    summary="Get the current matchup data version",
    description=(
        "Returns the patch string, public download URL, and row count of the "
        "latest scraped matchup database. Desktop clients call this on startup "
        "and re-download if their local patch differs."
    ),
)
def get_latest() -> DataVersion:
    """Public endpoint — no authentication required."""
    version = get_latest_version()
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No matchup data has been uploaded yet.",
        )
    return DataVersion(**version)


@router.post(
    "/versions",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Register a new matchup data version (scraper use only)",
    include_in_schema=not settings.is_production,
)
def post_version(
    payload: _VersionPayload,
    _: None = Depends(_require_scraper_secret),
) -> None:
    """Called by the GitHub Actions patch-update job after a successful scrape.

    Upserts the new version record and prunes anything beyond the two most
    recent patches.
    """
    upsert_version(
        patch=payload.patch,
        db_url=payload.db_url,
        row_count=payload.row_count,
    )
    pruned = prune_old_versions(keep=2)
    logger.info(
        "New data version registered: patch=%s url=%s rows=%d pruned=%d",
        payload.patch,
        payload.db_url,
        payload.row_count,
        pruned,
    )
