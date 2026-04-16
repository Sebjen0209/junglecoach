"""Supabase client and all database operations for the cloud API.

Responsibilities:
  - Singleton Supabase client (service role — server-side only)
  - Timeline cache: load/save raw Riot timeline JSON (timeline_cache table)
  - Analysis persistence: save/load completed PostGameAnalysis (post_game_analyses table)

Schema (apply in Supabase SQL editor — see deployment instructions):

    create table timeline_cache (
        match_id   text primary key,
        data       jsonb not null,
        cached_at  timestamptz default now()
    );

    create table post_game_analyses (
        id                  uuid primary key default gen_random_uuid(),
        user_id             uuid references auth.users not null,
        match_id            text not null,
        jungler_champion    text,
        analysed_at         timestamptz,
        gank_count          int,
        objective_count     int,
        pathing_issue_count int,
        moments             jsonb not null default '[]',
        created_at          timestamptz default now(),
        unique (user_id, match_id)
    );

    alter table post_game_analyses enable row level security;

    create policy "users_read_own" on post_game_analyses
        for select using (auth.uid() = user_id);

    -- timeline_cache has no RLS — only accessed via service role server-side
"""

import logging
from functools import lru_cache

from supabase import Client, create_client

from config import settings
from models import CoachingMoment, PostGameAnalysis

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_client() -> Client:
    """Return the singleton Supabase client (service role).

    Uses lru_cache so we create exactly one client for the lifetime of the
    process — safe because Railway runs one process per dyno.

    IMPORTANT: This uses the service role key, which bypasses RLS.
    Never expose this client or its key outside this module.
    """
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


# ---------------------------------------------------------------------------
# Timeline cache
# ---------------------------------------------------------------------------

def load_cached_timeline(match_id: str) -> dict | None:
    """Return the cached Riot timeline for a match, or None on cache miss.

    Cache failures are non-fatal — the caller will fetch from Riot instead.
    """
    try:
        result = (
            get_client()
            .table("timeline_cache")
            .select("data")
            .eq("match_id", match_id)
            .limit(1)
            .execute()
        )
        if result.data:
            logger.debug("Timeline cache hit: %s", match_id)
            return result.data[0]["data"]
    except Exception as exc:
        logger.warning("Timeline cache read failed for %s: %s", match_id, exc)
    return None


def save_cached_timeline(match_id: str, data: dict) -> None:
    """Upsert a Riot timeline into the Supabase cache.

    Write failures are non-fatal — the analysis result is still returned
    to the user; the next request for this match will re-fetch from Riot.
    """
    try:
        get_client().table("timeline_cache").upsert(
            {"match_id": match_id, "data": data},
            on_conflict="match_id",
        ).execute()
        logger.debug("Timeline cached: %s", match_id)
    except Exception as exc:
        logger.warning("Timeline cache write failed for %s: %s", match_id, exc)


# ---------------------------------------------------------------------------
# Analysis persistence
# ---------------------------------------------------------------------------

def load_existing_analysis(user_id: str, match_id: str) -> PostGameAnalysis | None:
    """Return a previously persisted analysis for this user+match, or None.

    Deserialises the stored JSONB moments back into CoachingMoment objects.
    """
    try:
        result = (
            get_client()
            .table("post_game_analyses")
            .select("*")
            .eq("user_id", user_id)
            .eq("match_id", match_id)
            .limit(1)
            .execute()
        )
        if result.data:
            row = result.data[0]
            logger.info(
                "Returning cached analysis for user %.8s, match %s",
                user_id,
                match_id,
            )
            return PostGameAnalysis(
                match_id=row["match_id"],
                jungler_champion=row.get("jungler_champion") or "Unknown",
                analysed_at=row["analysed_at"],
                gank_count=row["gank_count"],
                objective_count=row["objective_count"],
                pathing_issue_count=row["pathing_issue_count"],
                moments=[CoachingMoment(**m) for m in (row.get("moments") or [])],
            )
    except Exception as exc:
        logger.warning(
            "Could not load existing analysis for user %.8s, match %s: %s",
            user_id,
            match_id,
            exc,
        )
    return None


def save_analysis(user_id: str, analysis: PostGameAnalysis) -> None:
    """Persist a completed PostGameAnalysis to Supabase.

    Uses upsert on (user_id, match_id) so re-running analysis for the same
    match overwrites the old result rather than creating a duplicate.

    Persistence failures are non-fatal — the result is still returned to the
    user; they just won't see it in their history.
    """
    row = {
        "user_id": user_id,
        "match_id": analysis.match_id,
        "jungler_champion": analysis.jungler_champion,
        "analysed_at": analysis.analysed_at,
        "gank_count": analysis.gank_count,
        "objective_count": analysis.objective_count,
        "pathing_issue_count": analysis.pathing_issue_count,
        "moments": [m.model_dump() for m in analysis.moments],
    }
    try:
        get_client().table("post_game_analyses").upsert(
            row, on_conflict="user_id,match_id"
        ).execute()
        logger.info(
            "Analysis persisted: user %.8s, match %s, champion %s",
            user_id,
            analysis.match_id,
            analysis.jungler_champion,
        )
    except Exception as exc:
        logger.error(
            "Failed to persist analysis for user %.8s, match %s: %s",
            user_id,
            analysis.match_id,
            exc,
        )
