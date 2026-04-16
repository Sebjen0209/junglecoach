"""Assembles the final AnalysisResult from Live Client data + DB + AI.

This is the orchestration layer that wires together:
  1. GameSnapshot      — champion names, CS diffs, kill pressure (Riot local API)
  2. PlayerProfiles    — mastery + rank per player (Riot remote API, fetched once)
  3. DB lookups        — matchup win rates, power spike ratings
  4. Experience delta  — adjusts win rates based on mastery/autofill signals
  5. Scorer            — numeric scores + priority labels
  6. AI client         — natural language reasons
  7. AnalysisResult    — final payload served via GET /analysis
"""

import logging
from datetime import datetime, timezone

from analysis.ai_client import AIClient
from analysis.experience import experience_delta
from analysis.game_phase import game_time_to_phase
from analysis.scorer import score_lane, score_to_priority
from capture.live_client import GameSnapshot, PlayerSnapshot
from config import settings
from data.db import get_matchup_winrate, get_phase_strength
from models import AnalysisResult, GameState, LaneSuggestion, LaneState, PlayerProfile

logger = logging.getLogger(__name__)

# Gank suggestions are only meaningful in standard 5v5 Summoner's Rift games.
# PRACTICETOOL is included so the pipeline can be tested without a live match.
_SUPPORTED_GAME_MODES = {"CLASSIC", "PRACTICETOOL"}

# The three lanes the jungler can gank (jungle and support are excluded).
_GANK_LANES = ("top", "mid", "bot")

# Win rate is clamped after applying experience delta to avoid absurd values.
_MIN_WINRATE: float = 0.30
_MAX_WINRATE: float = 0.70


def _build_lane_state(
    ally: str,
    enemy: str,
    role: str,
    phase: str,
    cs_diff: int = 0,
    ally_kill_pressure: bool = False,
    exp_delta: float = 0.0,
) -> LaneState:
    """Build a LaneState by looking up win rate and phase strength from the DB."""
    raw_winrate = get_matchup_winrate(ally, enemy, role) or 0.50
    adjusted_winrate = max(_MIN_WINRATE, min(_MAX_WINRATE, raw_winrate + exp_delta))
    phase_strength = get_phase_strength(ally, phase)
    return LaneState(
        ally_champion=ally,
        enemy_champion=enemy,
        matchup_winrate=adjusted_winrate,
        ally_phase_strength=phase_strength,
        cs_diff=cs_diff,
        ally_kill_pressure=ally_kill_pressure,
    )


def build_game_state(
    ally_roles: dict[str, str],
    enemy_roles: dict[str, str],
    phase: str,
    game_minute: int,
    cs_diffs: dict[str, int] | None = None,
    kill_pressure: dict[str, bool] | None = None,
    exp_deltas: dict[str, float] | None = None,
) -> GameState:
    """Construct a GameState from role maps, DB lookups, and experience data.

    Args:
        ally_roles:    {role: champion_name} for the ally team
        enemy_roles:   {role: champion_name} for the enemy team
        phase:         'early' | 'mid' | 'late'
        game_minute:   current game minute
        cs_diffs:      {role: int} CS differences (positive = ally ahead)
        kill_pressure: {role: bool} whether ally has kill pressure
        exp_deltas:    {role: float} experience win-rate adjustments per lane

    Returns:
        A fully populated GameState ready for scoring and AI analysis.
    """
    cs_diffs = cs_diffs or {}
    kill_pressure = kill_pressure or {}
    exp_deltas = exp_deltas or {}

    lane_states = {
        role: _build_lane_state(
            ally=ally_roles.get(role, "Unknown"),
            enemy=enemy_roles.get(role, "Unknown"),
            role=role,
            phase=phase,
            cs_diff=cs_diffs.get(role, 0),
            ally_kill_pressure=kill_pressure.get(role, False),
            exp_delta=exp_deltas.get(role, 0.0),
        )
        for role in _GANK_LANES
    }

    return GameState(
        game_minute=game_minute,
        game_phase=phase,
        patch=settings.current_patch,
        top=lane_states["top"],
        mid=lane_states["mid"],
        bot=lane_states["bot"],
    )


def analyse(
    snapshot: GameSnapshot,
    ai_client: AIClient,
    player_profiles: dict[str, PlayerProfile] | None = None,
) -> AnalysisResult:
    """Full analysis pipeline: snapshot → experience → DB → scorer → AI → result.

    Args:
        snapshot:        GameSnapshot from capture/live_client.py
        ai_client:       Shared AIClient instance (handles API caching)
        player_profiles: {summoner_name: PlayerProfile} fetched at game start.
                         None if Riot API is not configured — analysis still
                         runs without experience adjustments.

    Returns:
        AnalysisResult ready to be serialised and served via GET /analysis.
    """
    if snapshot.game_mode not in _SUPPORTED_GAME_MODES:
        logger.info(
            "Skipping analysis — game mode %r is not supported (only CLASSIC)",
            snapshot.game_mode,
        )
        phase, game_minute = game_time_to_phase(snapshot.game_time_seconds)
        return AnalysisResult(game_detected=True, game_minute=game_minute)

    phase, game_minute = game_time_to_phase(snapshot.game_time_seconds)

    # Map profiles from summoner_name → role for experience delta calculation.
    exp_deltas = _compute_experience_deltas(snapshot, player_profiles or {})

    game_state = build_game_state(
        ally_roles=snapshot.ally_roles(),
        enemy_roles=snapshot.enemy_roles(),
        phase=phase,
        game_minute=game_minute,
        cs_diffs=snapshot.cs_diffs(),
        kill_pressure=snapshot.kill_pressure(),
        exp_deltas=exp_deltas,
    )

    # Score all lanes
    lane_scores: dict[str, tuple[float, str]] = {}
    for lane_name in _GANK_LANES:
        lane: LaneState = getattr(game_state, lane_name)
        score = score_lane(lane)
        priority = score_to_priority(score)
        lane_scores[lane_name] = (score, priority)

    # Get AI reasons (cached by ai_client if state is unchanged)
    try:
        reasons = ai_client.get_reasons(game_state)
    except Exception as exc:
        logger.error("AI client failed: %s — using score-based fallbacks", exc)
        reasons = _fallback_reasons(game_state, lane_scores)

    # Assemble final result
    lanes: dict[str, LaneSuggestion] = {}
    for lane_name in _GANK_LANES:
        lane = getattr(game_state, lane_name)
        score, priority = lane_scores[lane_name]
        lanes[lane_name] = LaneSuggestion(
            ally_champion=lane.ally_champion,
            enemy_champion=lane.enemy_champion,
            matchup_winrate=lane.matchup_winrate,
            priority=priority,
            reason=reasons.get(lane_name, ""),
            score=score,
        )

    return AnalysisResult(
        game_detected=True,
        game_minute=game_minute,
        patch=settings.current_patch,
        analysed_at=datetime.now(timezone.utc).isoformat(),
        lanes=lanes,
    )


def _compute_experience_deltas(
    snapshot: GameSnapshot,
    player_profiles: dict[str, PlayerProfile],
) -> dict[str, float]:
    """Compute per-lane experience win-rate delta using fetched player profiles."""
    ally_by_role: dict[str, PlayerProfile] = {
        p.position: player_profiles[p.summoner_name]
        for p in snapshot.ally_players
        if p.summoner_name in player_profiles
    }
    enemy_by_role: dict[str, PlayerProfile] = {
        p.position: player_profiles[p.summoner_name]
        for p in snapshot.enemy_players
        if p.summoner_name in player_profiles
    }
    return {
        role: experience_delta(ally_by_role.get(role), enemy_by_role.get(role))
        for role in _GANK_LANES
    }


def _fallback_reasons(
    game_state: GameState,
    lane_scores: dict[str, tuple[float, str]],
) -> dict[str, str]:
    """Generate minimal reason strings from score data when the AI call fails."""
    reasons: dict[str, str] = {}
    for lane_name in _GANK_LANES:
        lane: LaneState = getattr(game_state, lane_name)
        _, priority = lane_scores[lane_name]
        winrate_pct = int(lane.matchup_winrate * 100)
        reasons[lane_name] = (
            f"{lane.ally_champion} has a {winrate_pct}% win rate vs "
            f"{lane.enemy_champion} in this matchup. "
            f"Phase strength: {lane.ally_phase_strength:.0%}."
        )
    return reasons
