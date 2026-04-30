"""Pydantic response models for the JungleCoach cloud API.

Only post-game models live here — live-game models stay in backend/models.py.
"""

from pydantic import BaseModel


class DataVersion(BaseModel):
    """Response for GET /data/latest — tells desktop clients what patch is current."""

    patch: str
    db_url: str
    row_count: int
    scraped_at: str


class CoachingMoment(BaseModel):
    """A single timestamped coaching feedback item."""

    timestamp_str: str
    what_happened: str
    was_good_decision: bool
    reasoning: str
    suggestion: str | None = None


class PostGameAnalysis(BaseModel):
    """Full response for GET /postgame/{match_id}."""

    match_id: str
    jungler_champion: str
    analysed_at: str
    gank_count: int
    objective_count: int
    pathing_issue_count: int
    moments: list[CoachingMoment]


class RankedStats(BaseModel):
    """Solo/Duo ranked stats for the player profile card."""

    tier: str
    rank: str
    lp: int
    wins: int
    losses: int


class PlayerProfile(BaseModel):
    """Profile data shown above the match list after a summoner lookup."""

    summoner_name: str
    summoner_level: int
    profile_icon_id: int
    ranked_solo: RankedStats | None


class ParticipantSummary(BaseModel):
    """One player's stats for the scoreboard inside an expanded match card."""

    champion: str
    champion_id: int
    summoner_name: str
    position: str
    team_id: int
    kills: int
    deaths: int
    assists: int
    cs: int
    damage_dealt: int
    gold_earned: int
    vision_score: int
    items: list[int]
    trinket: int | None
    summoner_spell_1: int
    summoner_spell_2: int
    is_self: bool


class MatchEntry(BaseModel):
    """Single ranked match entry in a summoner's recent history."""

    match_id: str
    champion: str
    champion_id: int
    position: str
    win: bool
    kills: int
    deaths: int
    assists: int
    cs: int
    vision_score: int
    items: list[int]
    trinket: int | None
    summoner_spell_1: int
    summoner_spell_2: int
    kill_participation: float
    enemy_jungler: str | None
    enemy_jungler_id: int | None
    enemy_items: list[int]
    game_duration_seconds: int
    game_start_timestamp: int
    has_analysis: bool
    participants: list[ParticipantSummary]


class MatchHistoryResponse(BaseModel):
    """Response for GET /match-history."""

    summoner_name: str
    ddragon_version: str
    player_profile: PlayerProfile | None
    matches: list[MatchEntry]
