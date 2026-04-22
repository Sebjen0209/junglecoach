"""Post-game jungle analysis package.

Top-level entry point: `run_postgame_analysis(match_id, puuid?, summoner_name?)`
"""

import logging
from datetime import datetime, timezone

from analysis.postgame.coach import get_coaching_feedback
from analysis.postgame.events import (
    classify_ganks,
    classify_objectives,
    detect_pathing_issues,
)
from analysis.postgame.riot_client import (
    fetch_match,
    fetch_puuid_by_summoner_name,
    fetch_timeline,
    routing_from_match_id,
)
from analysis.postgame.timeline import extract_jungler_data
from models import PostGameAnalysis

logger = logging.getLogger(__name__)


def run_postgame_analysis(
    match_id: str,
    puuid: str | None = None,
    summoner_name: str | None = None,
) -> PostGameAnalysis:
    """Full post-game pipeline: Riot API → timeline parse → classify → Claude coaching.

    Args:
        match_id:      Riot match ID (e.g. "EUW1_7123456789").
        puuid:         Player PUUID — identifies which team's jungler to analyse.
        summoner_name: Alternative to puuid; triggers a summoner lookup (costs 1 API call).

    Returns:
        PostGameAnalysis with timestamped coaching moments, sorted by game time.

    Raises:
        RuntimeError:  On Riot API failure (caller should surface as HTTP 503).
        ValueError:    If no jungle participant is found in the match.
    """
    platform, region = routing_from_match_id(match_id)
    logger.info("Routing for %s → platform=%s, region=%s", match_id, platform, region)

    if puuid is None and summoner_name:
        puuid = fetch_puuid_by_summoner_name(summoner_name, platform)

    match_data = fetch_match(match_id, region)
    timeline_data = fetch_timeline(match_id, region)

    jungler_data = extract_jungler_data(match_data, timeline_data, target_puuid=puuid)

    ganks = classify_ganks(jungler_data.ganks, jungler_data.participant_id)
    objectives = classify_objectives(
        jungler_data.objectives,
        jungler_data.wards,
        jungler_data.team_id,
        death_timestamps=jungler_data.death_timestamps,
    )
    pathing = detect_pathing_issues(jungler_data)

    logger.info(
        "Coaching %s: %d ganks, %d objectives, %d pathing issues",
        jungler_data.champion_name,
        len(ganks),
        len(objectives),
        len(pathing),
    )

    moments = get_coaching_feedback(
        ganks=ganks,
        objectives=objectives,
        pathing=pathing,
        champion_name=jungler_data.champion_name,
    )

    return PostGameAnalysis(
        match_id=match_id,
        jungler_champion=jungler_data.champion_name,
        analysed_at=datetime.now(timezone.utc).isoformat(),
        gank_count=len(ganks),
        objective_count=len(objectives),
        pathing_issue_count=len(pathing),
        moments=moments,
    )
