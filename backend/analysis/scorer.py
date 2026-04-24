"""Matchup scoring algorithm.

Takes a GameState and produces a per-lane float score that drives
the priority classification (high / medium / low).

Scoring formula (from person1.md):
  counter_score  = (matchup_winrate - 0.50) * 200     → range -100 to +100
  phase_weight   = ally's strength rating for current phase (0.0–1.0)
  pressure_bonus = +15 if ally has kill pressure
  cs_bonus       = min(cs_diff * 0.5, 20)             → capped at +20

  score = counter_score * phase_weight + pressure_bonus + cs_bonus

Thresholds:
  score > 40  → HIGH   (red)
  score 15–40 → MEDIUM (yellow)
  score < 15  → LOW    (grey)
"""

import logging
from typing import Literal

from models import GameState, LaneState, LaneSuggestion

logger = logging.getLogger(__name__)

Priority = Literal["high", "medium", "low"]

_HIGH_THRESHOLD = 40.0
_MEDIUM_THRESHOLD = 15.0

# New live-signal bonuses / penalties
_NO_FLASH_BONUS = 20.0      # enemy without Flash can't escape — huge kill window
_LEVEL_DIFF_WEIGHT = 4.0    # each level ahead is a meaningful damage advantage
_LEVEL_DIFF_CAP = 12.0      # cap so level 6 vs 1 doesn't dominate everything
_ENEMY_DEAD_BONUS = 25.0    # free map pressure / dive setup while enemy respawns
_ALLY_DEAD_PENALTY = 60.0   # no point going to a lane with no one to follow up


def score_lane(lane: LaneState) -> float:
    """Compute a numeric gank-priority score for a single lane.

    Args:
        lane: LaneState containing ally/enemy info and phase-adjusted strength.

    Returns:
        Float score. Higher = more worth ganking.
    """
    counter_score = (lane.matchup_winrate - 0.50) * 200
    phase_score = counter_score * lane.ally_phase_strength
    pressure_bonus = 15.0 if lane.ally_kill_pressure else 0.0
    cs_bonus = min(lane.cs_diff * 0.5, 20.0)

    # Live-game signals (all default to 0 when data is unavailable)
    flash_bonus = _NO_FLASH_BONUS if not lane.enemy_has_flash else 0.0
    level_bonus = max(
        -_LEVEL_DIFF_CAP,
        min(_LEVEL_DIFF_CAP, lane.level_diff * _LEVEL_DIFF_WEIGHT),
    )
    # Dead-laner logic: ally dead overrides everything; enemy dead only helps if ally is alive
    if lane.ally_is_dead:
        dead_modifier = -_ALLY_DEAD_PENALTY
    elif lane.enemy_is_dead:
        dead_modifier = _ENEMY_DEAD_BONUS
    else:
        dead_modifier = 0.0

    total = phase_score + pressure_bonus + cs_bonus + flash_bonus + level_bonus + dead_modifier
    logger.debug(
        "score_lane %s vs %s → counter=%.1f phase_w=%.2f pressure=%.1f cs=%.1f "
        "flash=%.1f level=%.1f dead=%.1f total=%.1f",
        lane.ally_champion,
        lane.enemy_champion,
        counter_score,
        lane.ally_phase_strength,
        pressure_bonus,
        cs_bonus,
        flash_bonus,
        level_bonus,
        dead_modifier,
        total,
    )
    return round(total, 2)


def score_to_priority(score: float) -> Priority:
    """Convert a numeric score to a priority label."""
    if score > _HIGH_THRESHOLD:
        return "high"
    if score > _MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def score_all_lanes(game_state: GameState) -> dict[str, tuple[float, Priority]]:
    """Score all three lanes.

    Returns:
        Dict mapping lane name ('top'/'mid'/'bot') to (score, priority).
    """
    lanes = {"top": game_state.top, "mid": game_state.mid, "bot": game_state.bot}
    results: dict[str, tuple[float, Priority]] = {}
    for name, lane in lanes.items():
        s = score_lane(lane)
        results[name] = (s, score_to_priority(s))
    return results
