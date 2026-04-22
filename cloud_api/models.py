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
