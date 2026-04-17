"""Riot Games API client for post-game analysis.

Uses riotwatcher for automatic rate limiting (dev key: 20 req/s, 100 req/2min).
Timeline responses are cached to disk so a given match only costs one API call —
critical when on a dev key with its 100 match-history calls per 24h quota.

Region routing is derived automatically from the match ID prefix via
`routing_from_match_id()` — no manual config required.
"""

import json
import logging
from pathlib import Path

from riotwatcher import ApiError, LolWatcher

from config import settings

logger = logging.getLogger(__name__)

# Cache lives next to the SQLite DB so it survives restarts
_CACHE_DIR = Path(settings.db_path).parent / "timeline_cache"

# Maps match ID platform prefix → (platform slug, Match-V5 region)
# Platform is used for summoner lookups; region for Match-V5 endpoints.
_PLATFORM_TO_REGION: dict[str, str] = {
    # Europe
    "euw1": "europe",
    "eun1": "europe",
    "tr1":  "europe",
    "ru":   "europe",
    # Americas
    "na1":  "americas",
    "br1":  "americas",
    "la1":  "americas",
    "la2":  "americas",
    # Asia
    "kr":   "asia",
    "jp1":  "asia",
    # South-East Asia
    "oc1":  "sea",
    "ph2":  "sea",
    "sg2":  "sea",
    "th2":  "sea",
    "tw2":  "sea",
    "vn2":  "sea",
}


def routing_from_match_id(match_id: str) -> tuple[str, str]:
    """Parse a match ID into (platform, region) routing values.

    Match IDs always carry the originating platform as a prefix, e.g.:
      "EUW1_7123456789" → ("euw1", "europe")
      "NA1_7123456789"  → ("na1",  "americas")
      "KR_7123456789"   → ("kr",   "asia")

    Args:
        match_id: Riot match ID string.

    Returns:
        (platform, region) — platform for summoner-V4 calls, region for Match-V5.

    Raises:
        ValueError: If the prefix is not a known Riot platform.
    """
    platform = match_id.split("_")[0].lower()
    region = _PLATFORM_TO_REGION.get(platform)
    if region is None:
        raise ValueError(
            f"Unknown platform prefix {platform!r} in match ID {match_id!r}. "
            f"Known platforms: {', '.join(_PLATFORM_TO_REGION)}"
        )
    return platform, region


def _watcher() -> LolWatcher:
    if not settings.riot_api_key:
        raise RuntimeError("RIOT_API_KEY is not configured in .env")
    return LolWatcher(settings.riot_api_key)


# ---------------------------------------------------------------------------
# Disk cache for timeline responses
# ---------------------------------------------------------------------------

def _cache_path(match_id: str) -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR / f"{match_id}.json"


def _load_cached(match_id: str) -> dict | None:
    p = _cache_path(match_id)
    if p.exists():
        logger.debug("Timeline cache hit: %s", match_id)
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def _save_cached(match_id: str, data: dict) -> None:
    _cache_path(match_id).write_text(json.dumps(data), encoding="utf-8")
    logger.debug("Timeline cached to disk: %s", match_id)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_match(match_id: str, region: str) -> dict:
    """Fetch the match summary (participants, team stats, final items).

    Not cached — the payload is small and contains mutable summary data.

    Args:
        match_id: Riot match ID.
        region:   Match-V5 regional routing value (e.g. "europe").

    Raises:
        RuntimeError: On Riot API error.
    """
    try:
        logger.info("Fetching match summary: %s (%s)", match_id, region)
        return _watcher().match.by_id(region, match_id)
    except ApiError as exc:
        raise RuntimeError(f"Riot API error fetching match {match_id}: {exc}") from exc


def fetch_timeline(match_id: str, region: str) -> dict:
    """Fetch the match timeline, using a disk cache to preserve dev-key quota.

    The timeline is the large (~500 KB) frame-by-frame position + event log.
    It never changes after the game ends, so caching forever is safe.

    Args:
        match_id: Riot match ID.
        region:   Match-V5 regional routing value (e.g. "europe").

    Raises:
        RuntimeError: On Riot API error.
    """
    cached = _load_cached(match_id)
    if cached is not None:
        return cached

    try:
        logger.info("Fetching timeline (not cached): %s (%s)", match_id, region)
        data = _watcher().match.timeline_by_match(region, match_id)
    except ApiError as exc:
        raise RuntimeError(f"Riot API error fetching timeline {match_id}: {exc}") from exc

    _save_cached(match_id, data)
    return data


def fetch_puuid_by_summoner_name(summoner_name: str, platform: str) -> str:
    """Resolve a summoner name to a PUUID (platform-specific lookup).

    Args:
        summoner_name: In-game summoner name.
        platform:      Platform slug (e.g. "euw1"), derived from the match ID prefix.

    Raises:
        RuntimeError: If the summoner is not found or API errors.
    """
    try:
        logger.info("Looking up PUUID for summoner %r on %s", summoner_name, platform)
        summoner = _watcher().summoner.by_name(platform, summoner_name)
        return summoner["puuid"]
    except ApiError as exc:
        raise RuntimeError(
            f"Could not find summoner {summoner_name!r} on {platform}: {exc}"
        ) from exc


def get_recent_match_ids(puuid: str, region: str, count: int = 5) -> list[str]:
    """Return the most recent ranked solo/duo match IDs for a PUUID.

    Args:
        puuid:  The player's PUUID.
        region: Match-V5 regional routing value (e.g. "europe").
        count:  How many match IDs to return (max 20; keep low on dev key).

    Raises:
        RuntimeError: On Riot API error.
    """
    try:
        logger.info("Fetching %d recent matches for puuid %.12s... (%s)", count, puuid, region)
        return _watcher().match.matchlist_by_puuid(region, puuid, queue=420, count=count)
    except ApiError as exc:
        raise RuntimeError(f"Riot API error fetching match list: {exc}") from exc
