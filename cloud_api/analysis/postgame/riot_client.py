"""Riot Games API client for the cloud API.

Identical to backend/analysis/postgame/riot_client.py except the timeline
cache uses Supabase (persistent, shared across dynos) instead of the local
disk (which is ephemeral on Railway).

TODO: Extract shared logic into a common package (e.g. packages/analysis)
      when the backend and cloud_api diverge enough to warrant it.
"""

import logging
from urllib.parse import quote

import httpx
from riotwatcher import ApiError, LolWatcher

from config import settings
from db.supabase import load_cached_timeline, save_cached_timeline

logger = logging.getLogger(__name__)

# Maps match ID platform prefix → Match-V5 regional routing value.
# Kept in sync with backend/analysis/postgame/riot_client.py.
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
        raise RuntimeError("RIOT_API_KEY is not configured.")
    return LolWatcher(settings.riot_api_key)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _riot_get(url: str) -> dict:
    """Make an authenticated GET request to the Riot API.

    Uses httpx directly instead of riotwatcher to avoid auth issues with
    the developer key.

    Raises:
        RuntimeError: On non-200 response or network error.
    """
    if not settings.riot_api_key:
        raise RuntimeError("RIOT_API_KEY is not configured.")
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers={"X-Riot-Token": settings.riot_api_key})
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 401:
            raise RuntimeError(
                "Riot API key is invalid or expired — regenerate it at developer.riotgames.com"
            )
        if resp.status_code == 404:
            raise RuntimeError(f"Resource not found at {url}")
        raise RuntimeError(
            f"Riot API returned HTTP {resp.status_code} for {url}"
        )
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Could not reach Riot API at {url}: {exc}") from exc


def fetch_match(match_id: str, region: str) -> dict:
    """Fetch the match summary (participants, team stats, final items).

    Not cached — the payload is small and the data is not time-sensitive.

    Raises:
        RuntimeError: On Riot API error.
    """
    logger.info("Fetching match summary: %s (%s)", match_id, region)
    url = f"https://{region}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    return _riot_get(url)


def fetch_timeline(match_id: str, region: str) -> dict:
    """Fetch the match timeline, using Supabase as a persistent cache.

    The timeline (~500 KB of frame-by-frame data) never changes after the
    game ends, so we cache it indefinitely. The Supabase cache is shared
    across all users — if any user previously requested this match,
    it's free for everyone after that.

    Raises:
        RuntimeError: On Riot API error.
    """
    cached = load_cached_timeline(match_id)
    if cached is not None:
        return cached

    logger.info("Fetching timeline from Riot (not cached): %s (%s)", match_id, region)
    url = f"https://{region}.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline"
    data = _riot_get(url)

    save_cached_timeline(match_id, data)
    return data


def _puuid_via_summoner_v4(game_name: str, tag_line: str, platform: str, watcher: LolWatcher) -> str:
    """Fall back to Summoner V4 by-name when Account V1 is unavailable.

    Developer keys sometimes cannot reach the regional Account V1 endpoint.
    Summoner V4 uses the platform endpoint (e.g. euw1) which always works
    for dev keys. The tag_line is not used — Summoner V4 doesn't accept it.
    """
    try:
        logger.info(
            "Summoner V4 fallback: looking up %r on %s (tag %r ignored)",
            game_name, platform, tag_line,
        )
        summoner = watcher.summoner.by_name(platform, game_name)
        return summoner["puuid"]
    except ApiError as exc:
        raise RuntimeError(
            f"Could not find summoner {game_name!r} on {platform}: {exc}"
        ) from exc


def fetch_puuid_by_summoner_name(summoner_name: str, platform: str, region: str) -> str:
    """Resolve a summoner name or Riot ID to a PUUID.

    Accepts both formats:
      - Legacy summoner name: "SomeName"           → Summoner v4 (platform)
      - Riot ID:              "SomeName#TAG"        → Account v1 (region)

    The input is normalised before processing — leading/trailing whitespace and
    any space around the '#' separator are stripped, so "R3R0NI #EXE",
    "R3R0NI# EXE", and "R3R0NI#EXE" are all treated identically.
    Matching is case-insensitive on Riot's side.

    Raises:
        RuntimeError: If the player is not found or the API errors.
    """
    # Normalise: strip outer whitespace and any space around the '#' separator.
    summoner_name = summoner_name.strip()
    if "#" in summoner_name:
        raw_name, raw_tag = summoner_name.split("#", 1)
        summoner_name = f"{raw_name.strip()}#{raw_tag.strip()}"

    watcher = _watcher()

    if "#" in summoner_name:
        # New Riot ID format: "GameName#TAG"
        # LolWatcher doesn't expose Account v1 — call the Riot API directly.
        game_name, tag_line = summoner_name.split("#", 1)
        url = (
            f"https://{region}.api.riotgames.com/riot/account/v1/accounts"
            f"/by-riot-id/{quote(game_name)}/{quote(tag_line)}"
        )
        try:
            logger.info(
                "Looking up PUUID for Riot ID %r (region=%s)", summoner_name, region
            )
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(url, headers={"X-Riot-Token": settings.riot_api_key})
            if resp.status_code == 200:
                return resp.json()["puuid"]
            if resp.status_code == 404:
                raise RuntimeError(f"Riot ID {summoner_name!r} not found")
            if resp.status_code == 401:
                # Developer keys sometimes lack Account V1 regional routing access.
                # Fall back to Summoner V4 on the platform endpoint using the game
                # name only (pre-#). Less precise (ignores tag) but works on dev keys.
                logger.warning(
                    "Account V1 returned 401 for %r — falling back to Summoner V4 (game name only)",
                    summoner_name,
                )
                return _puuid_via_summoner_v4(game_name, tag_line, platform, watcher)
            raise RuntimeError(
                f"Riot Account API returned HTTP {resp.status_code} for {summoner_name!r}"
            )
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"Could not reach Riot Account API for {summoner_name!r}: {exc}"
            ) from exc
    else:
        # Legacy summoner name
        try:
            logger.info(
                "Looking up PUUID for summoner %r on %s", summoner_name, platform
            )
            summoner = watcher.summoner.by_name(platform, summoner_name)
            return summoner["puuid"]
        except ApiError as exc:
            raise RuntimeError(
                f"Could not find summoner {summoner_name!r} on {platform}: {exc}"
            ) from exc


def fetch_summoner_by_puuid(puuid: str, platform: str) -> dict:
    """Return the full Summoner V4 object for a PUUID (id, level, profileIconId)."""
    try:
        return _watcher().summoner.by_puuid(platform, puuid)
    except ApiError as exc:
        raise RuntimeError(f"Could not fetch summoner data for PUUID on {platform}: {exc}") from exc


def fetch_ranked_entries(summoner_id: str, platform: str) -> list[dict]:
    """Return all ranked queue entries for an encrypted summoner ID."""
    try:
        return _watcher().league.by_summoner(platform, summoner_id)
    except ApiError as exc:
        raise RuntimeError(f"Could not fetch ranked entries on {platform}: {exc}") from exc


def get_recent_match_ids(puuid: str, region: str, count: int = 5) -> list[str]:
    """Return the most recent ranked solo/duo match IDs for a PUUID.

    Args:
        puuid:  The player's PUUID.
        region: Match-V5 regional routing value.
        count:  Number of matches to return (keep low on dev key: 100 req/24h quota).

    Raises:
        RuntimeError: On Riot API error.
    """
    try:
        logger.info("Fetching %d recent matches for puuid %.12s... (%s)", count, puuid, region)
        return _watcher().match.matchlist_by_puuid(region, puuid, queue=420, count=count)
    except ApiError as exc:
        raise RuntimeError(f"Riot API error fetching match list: {exc}") from exc
