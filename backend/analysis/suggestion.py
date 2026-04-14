"""Assembles the final AnalysisResult from OCR output + DB data + AI reasons.

This is the orchestration layer that wires together:
  1. OCR output (champion names, roles)
  2. DB lookups (matchup win rates, power spike ratings)
  3. Scorer (numeric scores + priority labels)
  4. AI client (natural language reasons)
  5. Final packaging into AnalysisResult (served by server.py)
"""

import logging
from datetime import datetime, timezone

from analysis.ai_client import AIClient
from analysis.scorer import score_lane, score_to_priority
from capture.champion_parser import ScoreboardOCRResult, parse_scoreboard_row
from capture.ocr import ScoreboardOCRResult  # re-export for type clarity
from config import settings
from data.db import get_matchup_winrate, get_phase_strength
from models import AnalysisResult, GameState, LaneSuggestion, LaneState

logger = logging.getLogger(__name__)

# Lane roles we care about for gank suggestions (jungle and support are not ganked)
_GANK_LANES = ("top", "mid", "bot")


def _build_lane_state(
    ally: str,
    enemy: str,
    role: str,
    phase: str,
    cs_diff: int = 0,
    ally_kill_pressure: bool = False,
) -> LaneState:
    """Build a LaneState by looking up win rate and phase strength from DB."""
    winrate = get_matchup_winrate(ally, enemy, role) or 0.50
    phase_strength = get_phase_strength(ally, phase)
    return LaneState(
        ally_champion=ally,
        enemy_champion=enemy,
        matchup_winrate=winrate,
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
) -> GameState:
    """Construct a GameState from parsed OCR data and DB lookups.

    Args:
        ally_roles:    {role: champion_name} for the ally team
        enemy_roles:   {role: champion_name} for the enemy team
        phase:         'early'|'mid'|'late'
        game_minute:   current game minute
        cs_diffs:      optional {role: int} CS differences (positive = ally ahead)
        kill_pressure: optional {role: bool} whether ally has kill pressure

    Returns:
        A fully populated GameState ready for scoring and AI analysis.
    """
    cs_diffs = cs_diffs or {}
    kill_pressure = kill_pressure or {}

    lane_states = {}
    for role in ("top", "mid", "bot"):
        ally = ally_roles.get(role, "Unknown")
        enemy = enemy_roles.get(role, "Unknown")
        lane_states[role] = _build_lane_state(
            ally=ally,
            enemy=enemy,
            role=role,
            phase=phase,
            cs_diff=cs_diffs.get(role, 0),
            ally_kill_pressure=kill_pressure.get(role, False),
        )

    return GameState(
        game_minute=game_minute,
        game_phase=phase,
        patch=settings.current_patch,
        top=lane_states["top"],
        mid=lane_states["mid"],
        bot=lane_states["bot"],
    )


def analyse(
    ocr_result: ScoreboardOCRResult,
    phase: str,
    game_minute: int,
    ai_client: AIClient,
) -> AnalysisResult:
    """Full analysis pipeline: OCR → DB → scorer → AI → AnalysisResult.

    Args:
        ocr_result:  Raw OCR output from capture/ocr.py
        phase:       Game phase string from analysis/game_phase.py
        game_minute: Game minute from game_phase.py
        ai_client:   Shared AIClient instance (handles caching)

    Returns:
        AnalysisResult ready to be serialised and served via GET /analysis.
    """
    # Parse OCR names into role maps
    try:
        ally_roles = parse_scoreboard_row(ocr_result.ally_raw)
        enemy_roles = parse_scoreboard_row(ocr_result.enemy_raw)
    except ValueError as exc:
        logger.error("Champion parsing failed: %s", exc)
        return AnalysisResult(game_detected=True)

    game_state = build_game_state(
        ally_roles=ally_roles,
        enemy_roles=enemy_roles,
        phase=phase,
        game_minute=game_minute,
    )

    # Score all lanes
    lane_scores: dict[str, tuple[float, str]] = {}
    for lane_name in _GANK_LANES:
        lane: LaneState = getattr(game_state, lane_name)
        score = score_lane(lane)
        priority = score_to_priority(score)
        lane_scores[lane_name] = (score, priority)

    # Get AI reasons (cached if state unchanged)
    try:
        reasons = ai_client.get_reasons(game_state)
    except Exception as exc:
        logger.error("AI client failed: %s — using score-based fallbacks", exc)
        reasons = _fallback_reasons(game_state, lane_scores)

    # Assemble final result
    lanes: dict[str, LaneSuggestion] = {}
    for lane_name in _GANK_LANES:
        lane: LaneState = getattr(game_state, lane_name)
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


def _fallback_reasons(
    game_state: GameState,
    lane_scores: dict[str, tuple[float, str]],
) -> dict[str, str]:
    """Generate minimal reason strings from score data when the AI call fails."""
    reasons: dict[str, str] = {}
    for lane_name in _GANK_LANES:
        lane: LaneState = getattr(game_state, lane_name)
        score, priority = lane_scores[lane_name]
        winrate_pct = int(lane.matchup_winrate * 100)
        reasons[lane_name] = (
            f"{lane.ally_champion} has a {winrate_pct}% win rate vs "
            f"{lane.enemy_champion} in this matchup. "
            f"Phase strength: {lane.ally_phase_strength:.0%}."
        )
    return reasons
