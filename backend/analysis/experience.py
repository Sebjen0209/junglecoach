"""Experience modifier for the matchup scoring system.

Adjusts the raw matchup win rate based on relative champion experience
between the ally and enemy laner, and whether either player looks autofilled.

Applied before the win rate enters the scorer — it shifts the baseline rather
than adding a separate bonus term, which keeps the scoring formula clean.

Design decisions:
  - Max total shift is ±0.10 (±10 percentage points on win rate).
    This translates to ±20 in counter_score — meaningful but not dominant.
  - Mastery level difference is the primary signal (1–7 scale).
  - Autofill proxy: ranked player (Platinum+) with very low mastery on their
    current champion is likely not playing their main.
  - If profile data is unavailable, delta = 0 (no change to the base win rate).
"""

import logging

from models import PlayerProfile

logger = logging.getLogger(__name__)

# Each mastery level difference shifts the win rate by this much.
# A Mastery 7 ally vs Mastery 1 enemy = 6 levels × 0.01 = +0.06.
_MASTERY_DIFF_WEIGHT: float = 0.01

# Autofill detection thresholds.
# Signal: a ranked player with essentially no games on their current champion.
_AUTOFILL_PENALTY: float = -0.04
_AUTOFILL_MIN_RANK_TIER: int = 5    # Platinum or above (tier index from models)
_AUTOFILL_MAX_MASTERY_LEVEL: int = 2
_AUTOFILL_MAX_MASTERY_POINTS: int = 10_000

# Hard cap so experience data can never single-handedly flip a matchup.
_MAX_DELTA: float = 0.10


def experience_delta(
    ally: PlayerProfile | None,
    enemy: PlayerProfile | None,
) -> float:
    """Compute the win-rate adjustment based on champion experience.

    Args:
        ally:  Profile of the ally laner. None if data is unavailable.
        enemy: Profile of the enemy laner. None if data is unavailable.

    Returns:
        Float delta to add to the raw matchup win rate before scoring.
        Clamped to [-0.10, +0.10]. Returns 0.0 if both profiles are None.

    Examples:
        Mastery 7 ally vs Mastery 1 enemy → +0.06
        Likely-autofilled ally (Plat+, <10k mastery) → -0.04
        Both Mastery 5, same rank → 0.0
    """
    if ally is None and enemy is None:
        return 0.0

    # Use level 4 (mid-range) as the assumption when one side is unknown.
    ally_mastery = ally.mastery_level if ally is not None else 4
    enemy_mastery = enemy.mastery_level if enemy is not None else 4

    mastery_modifier = (ally_mastery - enemy_mastery) * _MASTERY_DIFF_WEIGHT
    autofill_penalty = _autofill_penalty(ally) if ally is not None else 0.0

    delta = mastery_modifier + autofill_penalty

    clamped = max(-_MAX_DELTA, min(_MAX_DELTA, delta))
    if clamped != 0.0:
        logger.debug(
            "experience_delta: ally_mastery=%d enemy_mastery=%d autofill=%.2f → %.3f",
            ally_mastery,
            enemy_mastery,
            autofill_penalty,
            clamped,
        )
    return clamped


def _autofill_penalty(profile: PlayerProfile) -> float:
    """Return a negative delta if the player looks autofilled.

    A ranked player at Platinum+ with under 10k mastery points on their
    current champion is almost certainly not on their main champion/role.
    """
    if (
        profile.rank_tier >= _AUTOFILL_MIN_RANK_TIER
        and profile.mastery_level <= _AUTOFILL_MAX_MASTERY_LEVEL
        and profile.mastery_points < _AUTOFILL_MAX_MASTERY_POINTS
    ):
        logger.debug(
            "%r looks autofilled (rank_tier=%d mastery_level=%d points=%d)",
            profile.summoner_name,
            profile.rank_tier,
            profile.mastery_level,
            profile.mastery_points,
        )
        return _AUTOFILL_PENALTY
    return 0.0
