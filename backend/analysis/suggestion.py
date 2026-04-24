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
from capture.live_client import (
    GameSnapshot,
    PlayerSnapshot,
    compute_objective_timers,
    get_events,
)
from config import settings
from data.db import get_matchup_winrate, get_phase_strength
from models import (
    AnalysisResult,
    GameState,
    LaneSuggestion,
    LaneState,
    ObjectiveTimers,
    PlayerProfile,
)

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
    enemy_has_flash: bool = True,
    level_diff: int = 0,
    ally_is_dead: bool = False,
    enemy_is_dead: bool = False,
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
        enemy_has_flash=enemy_has_flash,
        level_diff=level_diff,
        ally_is_dead=ally_is_dead,
        enemy_is_dead=enemy_is_dead,
    )


def build_game_state(
    ally_roles: dict[str, str],
    enemy_roles: dict[str, str],
    phase: str,
    game_minute: int,
    cs_diffs: dict[str, int] | None = None,
    kill_pressure: dict[str, bool] | None = None,
    exp_deltas: dict[str, float] | None = None,
    enemy_flash: dict[str, bool] | None = None,
    level_diffs: dict[str, int] | None = None,
    dead_laners: dict[str, tuple[bool, bool]] | None = None,
    game_time_seconds: float = 0.0,
    objective_timers: ObjectiveTimers | None = None,
) -> GameState:
    """Construct a GameState from role maps, DB lookups, and experience data.

    Args:
        ally_roles:       {role: champion_name} for the ally team
        enemy_roles:      {role: champion_name} for the enemy team
        phase:            'early' | 'mid' | 'late'
        game_minute:      current game minute
        cs_diffs:         {role: int} CS differences (positive = ally ahead)
        kill_pressure:    {role: bool} whether ally has kill pressure
        exp_deltas:       {role: float} experience win-rate adjustments per lane
        enemy_flash:      {role: bool} whether the enemy laner has Flash
        level_diffs:      {role: int} ally level minus enemy level
        dead_laners:      {role: (ally_dead, enemy_dead)} respawn state
        game_time_seconds: raw game clock for objective timers
        objective_timers: pre-computed objective spawn state

    Returns:
        A fully populated GameState ready for scoring and AI analysis.
    """
    cs_diffs = cs_diffs or {}
    kill_pressure = kill_pressure or {}
    exp_deltas = exp_deltas or {}
    enemy_flash = enemy_flash or {}
    level_diffs = level_diffs or {}
    dead_laners = dead_laners or {}

    lane_states = {
        role: _build_lane_state(
            ally=ally_roles.get(role, "Unknown"),
            enemy=enemy_roles.get(role, "Unknown"),
            role=role,
            phase=phase,
            cs_diff=cs_diffs.get(role, 0),
            ally_kill_pressure=kill_pressure.get(role, False),
            exp_delta=exp_deltas.get(role, 0.0),
            enemy_has_flash=enemy_flash.get(role, True),
            level_diff=level_diffs.get(role, 0),
            ally_is_dead=dead_laners.get(role, (False, False))[0],
            enemy_is_dead=dead_laners.get(role, (False, False))[1],
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
        game_time_seconds=game_time_seconds,
        objective_timers=objective_timers,
    )


def analyse(
    snapshot: GameSnapshot,
    ai_client: AIClient,
    player_profiles: dict[str, PlayerProfile] | None = None,
    jwt: str | None = None,
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

    # Fetch live objective timers from the event history endpoint.
    events = get_events()
    objective_timers = compute_objective_timers(events, snapshot.game_time_seconds)

    game_state = build_game_state(
        ally_roles=snapshot.ally_roles(),
        enemy_roles=snapshot.enemy_roles(),
        phase=phase,
        game_minute=game_minute,
        cs_diffs=snapshot.cs_diffs(),
        kill_pressure=snapshot.kill_pressure(),
        exp_deltas=exp_deltas,
        enemy_flash=snapshot.enemy_has_flash(),
        level_diffs=snapshot.level_diffs(),
        dead_laners=snapshot.dead_laners(),
        game_time_seconds=snapshot.game_time_seconds,
        objective_timers=objective_timers,
    )

    # Score all lanes
    lane_scores: dict[str, tuple[float, str]] = {}
    for lane_name in _GANK_LANES:
        lane: LaneState = getattr(game_state, lane_name)
        score = score_lane(lane)
        priority = score_to_priority(score)
        lane_scores[lane_name] = (score, priority)

    # Get AI reasons from cloud API (cached if state is unchanged).
    # Fall back to scorer-derived reasons if the AI call fails.
    try:
        reasons = ai_client.get_reasons(game_state, jwt=jwt)
    except Exception:
        logger.warning("AI client failed — using fallback reasons", exc_info=True)
        reasons = {}

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
            reason=reasons.get(lane_name) or _fallback_reason(lane, priority),
            score=score,
            enemy_has_flash=lane.enemy_has_flash,
            enemy_is_dead=lane.enemy_is_dead,
            ally_is_dead=lane.ally_is_dead,
        )

    alert = objective_timers.next_objective_alert if objective_timers else ""

    return AnalysisResult(
        game_detected=True,
        game_minute=game_minute,
        game_time_seconds=snapshot.game_time_seconds,
        patch=settings.current_patch,
        analysed_at=datetime.now(timezone.utc).isoformat(),
        lanes=lanes,
        objective_alert=alert,
    )


def _fallback_reason(lane: LaneState, priority: str) -> str:
    """Generate a brief reason when the AI is unavailable."""
    ally = lane.ally_champion
    enemy = lane.enemy_champion
    if priority == "high":
        return f"{ally} vs {enemy} — strong gank opportunity."
    if priority == "medium":
        return f"{ally} vs {enemy} — worth ganking if ahead."
    return f"{ally} vs {enemy} — low priority this rotation."


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
