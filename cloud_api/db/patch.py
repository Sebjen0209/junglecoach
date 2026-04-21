"""Patch metadata operations — tracks the current matchup data version.

Schema (add to Supabase SQL editor alongside the other tables):

    create table data_versions (
        patch      text primary key,
        db_url     text not null,
        row_count  int  not null,
        scraped_at timestamptz default now()
    );

    -- No RLS: only accessed via service role key server-side.
    -- Desktop clients read via the public GET /data/latest endpoint.
"""

import logging

from db.supabase import get_client

logger = logging.getLogger(__name__)

_TABLE = "data_versions"


def get_latest_version() -> dict | None:
    """Return the most recently scraped data version, or None if none exists."""
    try:
        result = (
            get_client()
            .table(_TABLE)
            .select("patch, db_url, row_count, scraped_at")
            .order("scraped_at", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as exc:
        logger.error("Failed to read data_versions: %s", exc)
        return None


def upsert_version(patch: str, db_url: str, row_count: int) -> None:
    """Insert or replace the version record for a given patch.

    Uses upsert on the `patch` primary key, so re-running the scraper for
    the same patch overwrites the old URL (e.g. if a re-scrape was needed).
    """
    from datetime import datetime, timezone
    row = {
        "patch": patch,
        "db_url": db_url,
        "row_count": row_count,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }
    get_client().table(_TABLE).upsert(row, on_conflict="patch").execute()
    logger.info("data_versions updated: patch=%s rows=%d", patch, row_count)


def prune_old_versions(keep: int = 2) -> int:
    """Delete all but the `keep` most recent patch versions.

    Keeps the last two patches so the desktop client can fall back gracefully
    if the latest scrape was incomplete.

    Returns:
        Number of rows deleted.
    """
    try:
        # Fetch all patches sorted newest-first
        result = (
            get_client()
            .table(_TABLE)
            .select("patch")
            .order("scraped_at", desc=True)
            .execute()
        )
        patches = [r["patch"] for r in (result.data or [])]
        to_delete = patches[keep:]  # everything beyond the `keep` most recent
        if not to_delete:
            return 0

        get_client().table(_TABLE).delete().in_("patch", to_delete).execute()
        logger.info("Pruned %d old patch version(s): %s", len(to_delete), to_delete)
        return len(to_delete)
    except Exception as exc:
        logger.warning("Failed to prune old data_versions: %s", exc)
        return 0
