"""Match history router.

Single endpoint: GET /match-history?summoner_name=Name%23EUW&region=europe&count=10

Flow:
  1. Authenticate via Supabase JWT
  2. Resolve summoner name/Riot ID to PUUID
  3. Fetch the N most recent ranked match IDs (queue 420)
  4. Fetch full match data for each (champion, items, KDA, vision, CS, etc.)
  5. Flag which matches the user has already analysed (single Supabase call)
  6. Return MatchHistoryResponse with DDragon version for image URLs
"""

import logging

import httpx
from fastapi import APIRouter, HTTPException, Query, status

from analysis.postgame.riot_client import (
    fetch_match,
    fetch_puuid_by_summoner_name,
    fetch_ranked_entries,
    fetch_summoner_by_puuid,
    get_recent_match_ids,
    routing_from_match_id,
)
from auth import CurrentUser
from db.supabase import get_analysed_match_ids
from models import MatchEntry, MatchHistoryResponse, ParticipantSummary, PlayerProfile, RankedStats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/match-history", tags=["match-history"])

_REGION_TO_PLATFORM: dict[str, str] = {
    "europe": "euw1",
    "americas": "na1",
    "asia": "kr",
    "sea": "oc1",
}

_VALID_REGIONS = frozenset(_REGION_TO_PLATFORM)

# Module-level DDragon version cache — refreshed once per process restart.
_ddragon_version: str | None = None


def _get_ddragon_version() -> str:
    global _ddragon_version
    if _ddragon_version is not None:
        return _ddragon_version
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get("https://ddragon.leagueoflegends.com/api/versions.json")
        if resp.status_code == 200:
            versions = resp.json()
            if versions:
                _ddragon_version = versions[0]
                return _ddragon_version
    except Exception as exc:
        logger.warning("Could not fetch DDragon version: %s", exc)
    # Fallback — update if items/spells stop rendering
    return "15.9.1"


_ROLE_ORDER: dict[str, int] = {"TOP": 0, "JUNGLE": 1, "MIDDLE": 2, "BOTTOM": 3, "UTILITY": 4}


def _build_participant(p: dict, self_puuid: str) -> ParticipantSummary:
    game_name = p.get("riotIdGameName") or p.get("summonerName", "")
    tag = p.get("riotIdTagline", "")
    display_name = f"{game_name}#{tag}" if tag else game_name

    raw = [p.get(f"item{i}", 0) for i in range(7)]
    return ParticipantSummary(
        champion=p.get("championName", "Unknown"),
        champion_id=p.get("championId", 0),
        summoner_name=display_name or "Unknown",
        position=p.get("teamPosition") or p.get("individualPosition", ""),
        team_id=p.get("teamId", 100),
        kills=p.get("kills", 0),
        deaths=p.get("deaths", 0),
        assists=p.get("assists", 0),
        cs=p.get("totalMinionsKilled", 0) + p.get("neutralMinionsKilled", 0),
        damage_dealt=p.get("totalDamageDealtToChampions", 0),
        gold_earned=p.get("goldEarned", 0),
        vision_score=p.get("visionScore", 0),
        items=[x for x in raw[:6] if x],
        trinket=raw[6] or None,
        summoner_spell_1=p.get("summoner1Id", 0),
        summoner_spell_2=p.get("summoner2Id", 0),
        is_self=p.get("puuid") == self_puuid,
    )


def _extract_entry(match_data: dict, puuid: str, match_id: str, has_analysis: bool) -> MatchEntry | None:
    """Pull all display fields from a Match V5 response for the tracked player."""
    raw_participants: list[dict] = match_data.get("info", {}).get("participants", [])
    if not raw_participants:
        return None

    user = next((p for p in raw_participants if p.get("puuid") == puuid), raw_participants[0])
    user_team = user.get("teamId", 100)

    enemy_jgl = next(
        (p for p in raw_participants if p.get("teamId") != user_team and p.get("teamPosition") == "JUNGLE"),
        None,
    )

    team_kills = sum(p.get("kills", 0) for p in raw_participants if p.get("teamId") == user_team)
    kp = (user.get("kills", 0) + user.get("assists", 0)) / max(team_kills, 1)

    raw_items = [user.get(f"item{i}", 0) for i in range(7)]
    items = [x for x in raw_items[:6] if x]
    trinket = raw_items[6] or None

    enemy_raw = [enemy_jgl.get(f"item{i}", 0) for i in range(6)] if enemy_jgl else []

    participants = sorted(
        [_build_participant(p, puuid) for p in raw_participants],
        key=lambda p: _ROLE_ORDER.get(p.position, 5),
    )

    return MatchEntry(
        match_id=match_id,
        champion=user.get("championName", "Unknown"),
        champion_id=user.get("championId", 0),
        position=user.get("teamPosition") or user.get("individualPosition", ""),
        win=user.get("win", False),
        kills=user.get("kills", 0),
        deaths=user.get("deaths", 0),
        assists=user.get("assists", 0),
        cs=user.get("totalMinionsKilled", 0) + user.get("neutralMinionsKilled", 0),
        vision_score=user.get("visionScore", 0),
        items=items,
        trinket=trinket,
        summoner_spell_1=user.get("summoner1Id", 0),
        summoner_spell_2=user.get("summoner2Id", 0),
        kill_participation=round(kp, 3),
        enemy_jungler=enemy_jgl.get("championName") if enemy_jgl else None,
        enemy_jungler_id=enemy_jgl.get("championId") if enemy_jgl else None,
        enemy_items=[x for x in enemy_raw if x],
        game_duration_seconds=match_data.get("info", {}).get("gameDuration", 0),
        game_start_timestamp=match_data.get("info", {}).get("gameStartTimestamp", 0),
        has_analysis=has_analysis,
        participants=participants,
    )


def _fetch_player_profile(
    summoner_name: str, puuid: str, platform: str
) -> PlayerProfile | None:
    """Fetch summoner level/icon and ranked solo stats. Non-fatal — returns None on any error."""
    try:
        summoner = fetch_summoner_by_puuid(puuid, platform)
        entries = fetch_ranked_entries(summoner["id"], platform)
        solo_entry = next((e for e in entries if e.get("queueType") == "RANKED_SOLO_5x5"), None)
        ranked_solo = None
        if solo_entry:
            ranked_solo = RankedStats(
                tier=solo_entry["tier"],
                rank=solo_entry["rank"],
                lp=solo_entry["leaguePoints"],
                wins=solo_entry["wins"],
                losses=solo_entry["losses"],
            )
        return PlayerProfile(
            summoner_name=summoner_name,
            summoner_level=summoner.get("summonerLevel", 0),
            profile_icon_id=summoner.get("profileIconId", 0),
            ranked_solo=ranked_solo,
        )
    except Exception as exc:
        logger.warning("Could not fetch player profile for %r: %s", summoner_name, exc)
        return None


@router.get(
    "",
    response_model=MatchHistoryResponse,
    summary="Get recent ranked matches for a summoner",
)
def get_match_history(
    current_user: CurrentUser,
    summoner_name: str = Query(..., description="Riot ID (Name#TAG) or legacy summoner name"),
    region: str = Query("europe", description="Match-V5 region: europe, americas, asia, sea"),
    count: int = Query(10, ge=1, le=10, description="Number of matches to return (max 10)"),
) -> MatchHistoryResponse:
    """Return the most recent ranked solo/duo matches for a summoner with full display data.

    Each match includes champion portrait info, items, KDA, CS, vision score,
    kill participation, summoner spells, and the enemy jungler — enough to
    render a rich match card without a second API call.

    Raises:
        400: Unknown region value.
        401: Missing or invalid Bearer token.
        404: Summoner not found.
        503: Riot API unreachable.
    """
    if region not in _VALID_REGIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown region {region!r}. Valid values: {', '.join(sorted(_VALID_REGIONS))}",
        )

    user_id = current_user["id"]
    platform = _REGION_TO_PLATFORM[region]

    try:
        puuid = fetch_puuid_by_summoner_name(summoner_name, platform, region)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    try:
        match_ids = get_recent_match_ids(puuid, region, count=count)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not fetch match history from Riot. Please try again.",
        ) from exc

    analysed = get_analysed_match_ids(user_id, match_ids)
    player_profile = _fetch_player_profile(summoner_name, puuid, platform)

    entries: list[MatchEntry] = []
    for match_id in match_ids:
        try:
            _, match_region = routing_from_match_id(match_id)
            match_data = fetch_match(match_id, match_region)
        except (RuntimeError, ValueError) as exc:
            logger.warning("Skipping match %s — fetch failed: %s", match_id, exc)
            continue

        entry = _extract_entry(match_data, puuid, match_id, match_id in analysed)
        if entry is not None:
            entries.append(entry)

    return MatchHistoryResponse(
        summoner_name=summoner_name,
        ddragon_version=_get_ddragon_version(),
        player_profile=player_profile,
        matches=entries,
    )
