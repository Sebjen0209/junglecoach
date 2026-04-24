"""Shared Pydantic data models for the JungleCoach backend."""

from dataclasses import dataclass
from typing import Literal
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Player profile (fetched from Riot API once per game)
# ---------------------------------------------------------------------------

@dataclass
class PlayerProfile:
    """Champion mastery and rank data for one player in the current game."""

    summoner_name: str
    champion_name: str
    mastery_level: int      # 1–7 per Riot's mastery system
    mastery_points: int     # raw mastery XP (hundreds of games = millions of points)
    rank_tier: int          # 0 = unranked, 1 = Iron … 10 = Challenger
    rank_name: str          # e.g. "GOLD", "PLATINUM", "UNRANKED"


class ObjectiveTimers(BaseModel):
    """Live spawn state for major objectives, derived from /liveclientdata/eventdata."""

    dragon_up: bool = True
    dragon_spawns_at: float | None = None    # game-seconds when dragon next spawns
    baron_up: bool = False
    baron_spawns_at: float | None = None
    herald_available: bool = False
    next_objective_alert: str = ""           # e.g. "Dragon UP" | "Baron in 45s" | ""


class LaneState(BaseModel):
    """Input data for a single lane, used by the scorer."""

    ally_champion: str
    enemy_champion: str
    matchup_winrate: float = Field(ge=0.0, le=1.0)
    ally_phase_strength: float = Field(ge=0.0, le=1.0)
    cs_diff: int
    ally_kill_pressure: bool
    # Live-game signals — all optional with safe defaults so offline/test code needs no changes
    enemy_has_flash: bool = True       # False → enemy cannot escape a gank
    level_diff: int = 0                # ally level minus enemy level
    ally_is_dead: bool = False         # gank pointless while ally is dead
    enemy_is_dead: bool = False        # free pressure window while enemy respawns


class GameState(BaseModel):
    """Full game state passed to the analysis engine."""

    game_minute: int = Field(ge=0)
    game_phase: Literal["early", "mid", "late"]
    patch: str
    top: LaneState
    mid: LaneState
    bot: LaneState
    game_time_seconds: float = 0.0
    objective_timers: ObjectiveTimers | None = None


class LaneSuggestion(BaseModel):
    """Output for a single lane — served via the API."""

    ally_champion: str
    enemy_champion: str
    matchup_winrate: float
    priority: Literal["high", "medium", "low"]
    reason: str | None = None
    score: float
    # Live-signal badges shown in the overlay
    enemy_has_flash: bool = True
    enemy_is_dead: bool = False
    ally_is_dead: bool = False


class AnalysisResult(BaseModel):
    """Full response payload for GET /analysis."""

    game_detected: bool
    game_minute: int | None = None
    patch: str | None = None
    analysed_at: str | None = None
    lanes: dict[str, LaneSuggestion] | None = None
    objective_alert: str = ""  # e.g. "Dragon UP | Baron in 45s"


class CoachingMoment(BaseModel):
    """A single timestamped coaching feedback item from post-game analysis."""

    timestamp_str: str
    what_happened: str
    was_good_decision: bool
    reasoning: str
    suggestion: str | None = None


class PostGameAnalysis(BaseModel):
    """Full response payload for GET /postgame/{match_id}."""

    match_id: str
    jungler_champion: str
    analysed_at: str
    gank_count: int
    objective_count: int
    pathing_issue_count: int
    moments: list[CoachingMoment]
