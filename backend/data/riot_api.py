"""Riot Games API client — fetches per-player mastery and rank data.

Called once when a game is first detected. Results are cached in server.py
for the duration of the game so we never repeat these calls mid-game.

Rate limits (developer key): 20 req/s, 100 req/2min.
Worst case for a full 10-player game: 30 async calls — well within limits.

Requires in .env:
    RIOT_API_KEY=RGAPI-xxxxxxxx
    RIOT_REGION=euw1   (or na1, kr, br1, etc.)
"""

import asyncio
import logging
from urllib.parse import quote

import httpx

from models import PlayerProfile

logger = logging.getLogger(__name__)

# Tier names ordered by strength — index is the numeric rank value we store.
_TIER_ORDER = [
    "UNRANKED", "IRON", "BRONZE", "SILVER", "GOLD",
    "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER",
]
_TIER_TO_INT: dict[str, int] = {t: i for i, t in enumerate(_TIER_ORDER)}

# Data Dragon CDN — used to resolve champion names to numeric IDs.
_DDRAGON_VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
_DDRAGON_CHAMPIONS_URL = (
    "https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def fetch_champion_id_map() -> dict[str, int]:
    """Return {champion_name: champion_id} from Riot Data Dragon.

    Used to resolve champion names (e.g. 'Lee Sin') to the numeric IDs
    required by the mastery endpoint. Returns {} on failure — the caller
    handles missing IDs gracefully.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            versions = (await client.get(_DDRAGON_VERSIONS_URL)).json()
            latest = versions[0]
            data = (
                await client.get(_DDRAGON_CHAMPIONS_URL.format(version=latest))
            ).json()
        return {
            info["name"]: int(info["key"])
            for info in data["data"].values()
        }
    except Exception as exc:
        logger.error("Could not fetch champion ID map from Data Dragon: %s", exc)
        return {}


async def fetch_profiles(
    players: list[tuple[str, str]],
    champion_id_map: dict[str, int],
    region: str,
    api_key: str,
) -> dict[str, PlayerProfile]:
    """Fetch mastery + rank profiles for all players concurrently.

    Args:
        players:          List of (summoner_name, champion_name) for each player
                          we want to profile (typically all 10 in the game).
        champion_id_map:  {champion_name: champion_id} from fetch_champion_id_map().
        region:           Riot region slug, e.g. "euw1", "na1", "kr".
        api_key:          RIOT_API_KEY value from settings.

    Returns:
        {summoner_name: PlayerProfile}. Players whose lookups fail (bots,
        network errors, unknown names) are silently omitted.
    """
    base_url = f"https://{region}.api.riotgames.com"
    headers = {"X-Riot-Token": api_key}

    async with httpx.AsyncClient(
        base_url=base_url,
        headers=headers,
        timeout=5.0,
    ) as client:
        tasks = [
            _fetch_single_profile(client, summoner_name, champion_name, champion_id_map)
            for summoner_name, champion_name in players
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    profiles: dict[str, PlayerProfile] = {}
    for (summoner_name, _), result in zip(players, results):
        if isinstance(result, Exception):
            logger.warning("Profile fetch failed for %r: %s", summoner_name, result)
        elif result is not None:
            profiles[summoner_name] = result

    logger.info(
        "Fetched %d/%d player profiles from Riot API", len(profiles), len(players)
    )
    return profiles


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _fetch_single_profile(
    client: httpx.AsyncClient,
    summoner_name: str,
    champion_name: str,
    champion_id_map: dict[str, int],
) -> PlayerProfile | None:
    """Fetch mastery + rank for one summoner. Returns None on any failure."""
    summoner = await _get_summoner(client, summoner_name)
    if summoner is None:
        return None  # bot, invalid name, or API error

    summoner_id: str = summoner["id"]
    champion_id: int | None = champion_id_map.get(champion_name)

    # Fetch mastery and rank concurrently — both can fail independently.
    # asyncio.sleep(0) is used as a no-op when champion_id is unknown — it
    # yields to the event loop once and returns None, same as _get_mastery would.
    mastery_coro = (
        _get_mastery(client, summoner_id, champion_id)
        if champion_id is not None
        else asyncio.sleep(0)
    )
    mastery, rank = await asyncio.gather(
        mastery_coro,
        _get_rank(client, summoner_id),
        return_exceptions=True,
    )

    if isinstance(mastery, Exception):
        logger.debug("Mastery fetch error for %r: %s", summoner_name, mastery)
        mastery = None
    if isinstance(rank, Exception):
        logger.debug("Rank fetch error for %r: %s", summoner_name, rank)
        rank = None

    return PlayerProfile(
        summoner_name=summoner_name,
        champion_name=champion_name,
        mastery_level=int(mastery["championLevel"]) if mastery else 1,
        mastery_points=int(mastery["championPoints"]) if mastery else 0,
        rank_name=str(rank["tier"]) if rank else "UNRANKED",
        rank_tier=_TIER_TO_INT.get(rank["tier"] if rank else "UNRANKED", 0),
    )


async def _get_summoner(client: httpx.AsyncClient, summoner_name: str) -> dict | None:
    """Look up a summoner by name. Returns None if not found."""
    try:
        resp = await client.get(
            f"/lol/summoner/v4/summoners/by-name/{quote(summoner_name)}"
        )
        if resp.status_code == 200:
            return resp.json()
        logger.debug(
            "Summoner lookup for %r → HTTP %d", summoner_name, resp.status_code
        )
        return None
    except Exception as exc:
        logger.debug("Summoner lookup error for %r: %s", summoner_name, exc)
        return None


async def _get_mastery(
    client: httpx.AsyncClient,
    summoner_id: str,
    champion_id: int,
) -> dict | None:
    """Fetch champion mastery entry. Returns None if the summoner has no data."""
    try:
        resp = await client.get(
            f"/lol/champion-mastery/v4/champion-masteries"
            f"/by-summoner/{summoner_id}/by-champion/{champion_id}"
        )
        return resp.json() if resp.status_code == 200 else None
    except Exception as exc:
        logger.debug("Mastery fetch error: %s", exc)
        return None


async def _get_rank(client: httpx.AsyncClient, summoner_id: str) -> dict | None:
    """Return the player's RANKED_SOLO_5x5 entry, or None if unranked."""
    try:
        resp = await client.get(
            f"/lol/league/v4/entries/by-summoner/{summoner_id}"
        )
        if resp.status_code != 200:
            return None
        for entry in resp.json():
            if entry.get("queueType") == "RANKED_SOLO_5x5":
                return entry
        return None
    except Exception as exc:
        logger.debug("Rank fetch error: %s", exc)
        return None
