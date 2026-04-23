"""Shared Pydantic data models for the JungleCoach backend."""

from dataclasses import dataclass
from typing import Literal
from pydantic import BaseModel, Field, field_validator


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


class LaneState(BaseModel):
    """Input data for a single lane, used by the scorer."""

    ally_champion: str
    enemy_champion: str
    matchup_winrate: float = Field(ge=0.0, le=1.0)
    ally_phase_strength: float = Field(ge=0.0, le=1.0)
    cs_diff: int
    ally_kill_pressure: bool


class GameState(BaseModel):
    """Full game state passed to the analysis engine."""

    game_minute: int = Field(ge=0)
    game_phase: Literal["early", "mid", "late"]
    patch: str
    top: LaneState
    mid: LaneState
    bot: LaneState


class LaneSuggestion(BaseModel):
    """Output for a single lane — served via the API."""

    ally_champion: str
    enemy_champion: str
    matchup_winrate: float
    priority: Literal["high", "medium", "low"]
    reason: str | None = None
    score: float


class MacroHint(BaseModel):
    """A single macro awareness point shown during mid/late game."""

    type: Literal["objective", "lane", "trade", "state"]
    urgency: Literal["critical", "high", "medium"]
    headline: str   # Short — rendered bold in the overlay (max ~8 words)
    detail: str     # 2 sentences of context — what it means and why it matters

    @field_validator("headline")
    @classmethod
    def headline_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("headline must not be empty")
        return v


class AnalysisResult(BaseModel):
    """Full response payload for GET /analysis."""

    game_detected: bool
    game_minute: int | None = None
    patch: str | None = None
    analysed_at: str | None = None
    # Laning mode (all outer towers up)
    lanes: dict[str, LaneSuggestion] | None = None
    # Macro mode (any outer tower down or 20+ min)
    analysis_mode: Literal["laning", "macro"] | None = None
    macro_hints: list[MacroHint] | None = None


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
