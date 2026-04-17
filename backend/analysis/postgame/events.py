"""Classifies raw timeline data into coaching-relevant jungler events.

Takes JunglerTimelineData from timeline.py and produces:
  - GankEvent  — a gank/kill in a named lane with outcome
  - ObjectiveEvent — an objective fight with vision + proximity flags
  - PathingIssue   — a minute where the jungler was in base or idle

All timestamps are in mm:ss string format for display and for the Claude prompt.
"""

import logging
from dataclasses import dataclass

from analysis.postgame.timeline import (
    BARON_PIT,
    BLUE_BASE,
    DRAGON_PIT,
    NEAR_BASE_RADIUS,
    NEAR_OBJECTIVE_RADIUS,
    RED_BASE,
    WARD_NEAR_OBJECTIVE_RADIUS,
    JunglerTimelineData,
    PositionFrame,
    RawGank,
    RawObjective,
    RawWard,
    dist,
)

logger = logging.getLogger(__name__)

# Lane boundaries by y-coordinate (blue-side perspective)
_BOT_Y_MAX = 5000
_TOP_Y_MIN = 10000

# Less than this many units of movement in a minute → flag as idle
_IDLE_MOVEMENT_THRESHOLD = 800

# Expected first-spawn timestamps in milliseconds
_FIRST_SPAWN_MS: dict[str, int] = {
    "DRAGON": 5 * 60 * 1_000,       # 5:00
    "BARON_NASHOR": 20 * 60 * 1_000, # 20:00
    "RIFTHERALD": 8 * 60 * 1_000,   # 8:00
}

# Tolerance for matching actual kill time to expected spawn (ms)
_SPAWN_MATCH_WINDOW_MS = 90_000


# ---------------------------------------------------------------------------
# Output dataclasses (consumed by coach.py and serialised into Pydantic models)
# ---------------------------------------------------------------------------

@dataclass
class GankEvent:
    timestamp_ms: int
    timestamp_str: str
    lane: str           # "top" | "mid" | "bot" | "unknown"
    outcome: str        # "kill" | "assist"
    position_x: int
    position_y: int
    was_jungler_killer: bool


@dataclass
class ObjectiveEvent:
    timestamp_ms: int
    timestamp_str: str
    objective_type: str  # "DRAGON" | "BARON_NASHOR" | "RIFTHERALD"
    secured_by_ally: bool
    jungler_distance_from_pit: float
    was_near_pit: bool
    had_vision_before: bool
    is_first_spawn: bool  # False for respawns (less critical to flag)


@dataclass
class PathingIssue:
    minute: int
    timestamp_str: str
    x: int
    y: int
    issue: str          # "in_base" | "idle"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ms_to_str(ms: int) -> str:
    total_s = ms // 1_000
    return f"{total_s // 60:02d}:{total_s % 60:02d}"


def _classify_lane(x: int, y: int) -> str:
    if y < _BOT_Y_MAX:
        return "bot"
    if y > _TOP_Y_MIN:
        return "top"
    return "mid"


def _pit_for(monster_type: str) -> tuple[int, int]:
    if monster_type in ("BARON_NASHOR", "RIFTHERALD"):
        return BARON_PIT
    return DRAGON_PIT


def _had_vision_near(
    wards: list[RawWard],
    pit: tuple[int, int],
    kill_ms: int,
    window_ms: int = 60_000,
) -> bool:
    """Return True if any ward was placed within `window_ms` before `kill_ms` near `pit`."""
    earliest = kill_ms - window_ms
    for w in wards:
        if earliest <= w.timestamp_ms <= kill_ms:
            if dist(w.x, w.y, pit[0], pit[1]) <= WARD_NEAR_OBJECTIVE_RADIUS:
                return True
    return False


def _is_first_spawn(monster_type: str, actual_ms: int) -> bool:
    expected = _FIRST_SPAWN_MS.get(monster_type)
    if expected is None:
        return False
    return abs(actual_ms - expected) <= _SPAWN_MATCH_WINDOW_MS


# ---------------------------------------------------------------------------
# Public classification functions
# ---------------------------------------------------------------------------

def classify_ganks(raw_ganks: list[RawGank], jungler_id: int) -> list[GankEvent]:
    """Convert raw CHAMPION_KILL events into labelled GankEvents.

    Args:
        raw_ganks:  RawGank list from JunglerTimelineData.
        jungler_id: participantId of the jungler.

    Returns:
        List of GankEvent, sorted by timestamp.
    """
    events: list[GankEvent] = []
    for g in raw_ganks:
        was_killer = g.killer_id == jungler_id
        outcome = "kill" if was_killer else "assist"
        events.append(GankEvent(
            timestamp_ms=g.timestamp_ms,
            timestamp_str=_ms_to_str(g.timestamp_ms),
            lane=_classify_lane(g.position_x, g.position_y),
            outcome=outcome,
            position_x=g.position_x,
            position_y=g.position_y,
            was_jungler_killer=was_killer,
        ))
    return sorted(events, key=lambda e: e.timestamp_ms)


def classify_objectives(
    raw_objectives: list[RawObjective],
    wards: list[RawWard],
    jungler_team_id: int,
) -> list[ObjectiveEvent]:
    """Convert raw ELITE_MONSTER_KILL events into labelled ObjectiveEvents.

    Args:
        raw_objectives: RawObjective list from JunglerTimelineData.
        wards:          All RawWard events (used for vision-before check).
        jungler_team_id: teamId of the jungler's team.

    Returns:
        List of ObjectiveEvent, sorted by timestamp.
    """
    events: list[ObjectiveEvent] = []
    for obj in raw_objectives:
        pit = _pit_for(obj.monster_type)
        d = dist(obj.jungler_x, obj.jungler_y, pit[0], pit[1])
        had_vision = _had_vision_near(wards, pit, obj.timestamp_ms)
        events.append(ObjectiveEvent(
            timestamp_ms=obj.timestamp_ms,
            timestamp_str=_ms_to_str(obj.timestamp_ms),
            objective_type=obj.monster_type,
            secured_by_ally=(obj.killer_team_id == jungler_team_id),
            jungler_distance_from_pit=round(d),
            was_near_pit=(d <= NEAR_OBJECTIVE_RADIUS),
            had_vision_before=had_vision,
            is_first_spawn=_is_first_spawn(obj.monster_type, obj.timestamp_ms),
        ))
    return sorted(events, key=lambda e: e.timestamp_ms)


def detect_pathing_issues(data: JunglerTimelineData) -> list[PathingIssue]:
    """Flag minutes where the jungler was sitting in base or barely moving.

    Args:
        data: JunglerTimelineData with position_frames populated.

    Returns:
        List of PathingIssue, sorted by minute.
    """
    issues: list[PathingIssue] = []
    base_pos = BLUE_BASE if data.team_id == 100 else RED_BASE

    prev: PositionFrame | None = None
    for frame in data.position_frames:
        if frame.minute == 0:
            prev = frame
            continue

        in_base = dist(frame.x, frame.y, base_pos[0], base_pos[1]) < NEAR_BASE_RADIUS

        if in_base:
            issues.append(PathingIssue(
                minute=frame.minute,
                timestamp_str=_ms_to_str(frame.minute * 60_000),
                x=frame.x,
                y=frame.y,
                issue="in_base",
            ))
        elif prev is not None:
            movement = dist(frame.x, frame.y, prev.x, prev.y)
            if movement < _IDLE_MOVEMENT_THRESHOLD:
                issues.append(PathingIssue(
                    minute=frame.minute,
                    timestamp_str=_ms_to_str(frame.minute * 60_000),
                    x=frame.x,
                    y=frame.y,
                    issue="idle",
                ))

        prev = frame

    return sorted(issues, key=lambda i: i.minute)
