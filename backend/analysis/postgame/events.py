"""Classifies raw timeline data into coaching-relevant jungler events.

Takes JunglerTimelineData from timeline.py and produces:
  - GankEvent  — a gank/kill in a named lane with outcome
  - ObjectiveEvent — an objective fight with vision + proximity flags
  - PathingIssue   — a minute where the jungler was in base or idle

All timestamps are in mm:ss string format for display and for the Claude prompt.
"""

import logging
from dataclasses import dataclass, field

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

# Lane boundaries (Summoner's Rift 14820×14820, blue base = low x/y)
_TOP_X_MAX = 3800    # top lane hard zone: low x AND high y
_TOP_Y_MIN = 9500
_BOT_X_MIN = 10500   # bot lane hard zone: high x AND low y
_BOT_Y_MAX = 5000
_MID_TOLERANCE = 2000  # |x - y| < this → kill is on the mid-lane diagonal

# Wider "near lane" zones for kills on the jungle/lane border
_TOP_NEAR_X_MAX = 5500
_TOP_NEAR_Y_MIN = 8500
_BOT_NEAR_X_MIN = 8500
_BOT_NEAR_Y_MAX = 6000

# 90 seconds covers the maximum respawn timer for most of the game
_DEAD_WINDOW_MS = 90_000

# Less than this many units of movement in a minute → flag as idle
_IDLE_MOVEMENT_THRESHOLD = 800

# Objectives taken within this window are considered a simultaneous trade
_TRADE_WINDOW_MS = 60_000

# Expected first-spawn timestamps in milliseconds
_FIRST_SPAWN_MS: dict[str, int] = {
    "DRAGON": 5 * 60 * 1_000,       # 5:00
    "BARON_NASHOR": 20 * 60 * 1_000, # 20:00
    "RIFTHERALD": 8 * 60 * 1_000,   # 8:00
}

# Tolerance for matching actual kill time to expected spawn (ms)
_SPAWN_MATCH_WINDOW_MS = 90_000

# Objective respawn timers (ms after death)
_RESPAWN_MS: dict[str, int] = {
    "DRAGON": 5 * 60 * 1_000,
    "BARON_NASHOR": 6 * 60 * 1_000,
}

# Rift Herald: spawns 8:00, two total (Season 14+), both gone when Baron spawns at 20:00
_HERALD_SPAWN_MS = 8 * 60 * 1_000
_HERALD_BARON_MS = 20 * 60 * 1_000
_HERALD_MAX_KILLS = 2

# Void Grubs: 6 total, first camp spawns at 5:00, gone when Baron spawns at 20:00
_VOID_GRUB_SPAWN_MS = 5 * 60 * 1_000
_VOID_GRUB_DESPAWN_MS = 20 * 60 * 1_000
_VOID_GRUB_TOTAL = 6


# ---------------------------------------------------------------------------
# Output dataclasses (consumed by coach.py and serialised into Pydantic models)
# ---------------------------------------------------------------------------

@dataclass
class GankEvent:
    timestamp_ms: int
    timestamp_str: str
    lane: str            # "top" | "mid" | "bot" | "jungle"
    outcome: str         # "kill" | "assist"
    position_x: int
    position_y: int
    was_jungler_killer: bool
    killer_champion: str = ""   # champion that got the kill (may not be the jungler)
    killer_role: str = ""       # their team position
    victim_champion: str = ""   # champion that died
    victim_role: str = ""


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
    jungler_was_dead: bool = False
    jungler_killed_objective: bool = False  # True when the jungler got the killing blow
    is_trade: bool = False  # True when the other team took a different objective concurrently
    trade_with: str | None = None  # the concurrent enemy/ally objective type
    available_for_trade: list[str] = field(default_factory=list)  # other objectives alive on the map right now


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
    # Hard lane zones (clearly in the lane)
    if x < _TOP_X_MAX and y > _TOP_Y_MIN:
        return "top"
    if x > _BOT_X_MIN and y < _BOT_Y_MAX:
        return "bot"
    if abs(x - y) < _MID_TOLERANCE:
        return "mid"
    # Near-lane jungle zones (on the lane/jungle border)
    if x < _TOP_NEAR_X_MAX and y > _TOP_NEAR_Y_MIN:
        return "jungle/top"
    if x > _BOT_NEAR_X_MIN and y < _BOT_NEAR_Y_MAX:
        return "jungle/bot"
    return "jungle"


def _was_jungler_dead(death_timestamps: list[int], event_ms: int) -> bool:
    """Return True if the jungler died within _DEAD_WINDOW_MS before event_ms."""
    return any(d <= event_ms <= d + _DEAD_WINDOW_MS for d in death_timestamps)


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


_OBJ_DISPLAY_LOCAL: dict[str, str] = {
    "DRAGON": "Dragon",
    "BARON_NASHOR": "Baron Nashor",
    "RIFTHERALD": "Rift Herald",
}


def _available_objectives_at(
    timestamp_ms: int,
    events: list,  # list[ObjectiveEvent] — avoid forward-ref
    void_grub_kills: list[tuple[int, int]],
) -> list[str]:
    """Return display names of major objectives alive at timestamp_ms."""
    available: list[str] = []

    # Dragon
    dragon_kills = [e for e in events if e.objective_type == "DRAGON" and e.timestamp_ms < timestamp_ms]
    if timestamp_ms >= _FIRST_SPAWN_MS["DRAGON"]:
        if not dragon_kills:
            available.append("Dragon")
        else:
            last_ms = max(e.timestamp_ms for e in dragon_kills)
            if timestamp_ms >= last_ms + _RESPAWN_MS["DRAGON"]:
                available.append("Dragon")

    # Rift Herald (2 kills max, gone at 20:00)
    herald_kills = [e for e in events if e.objective_type == "RIFTHERALD" and e.timestamp_ms < timestamp_ms]
    if _HERALD_SPAWN_MS <= timestamp_ms < _HERALD_BARON_MS and len(herald_kills) < _HERALD_MAX_KILLS:
        available.append("Rift Herald")

    # Baron Nashor
    baron_kills = [e for e in events if e.objective_type == "BARON_NASHOR" and e.timestamp_ms < timestamp_ms]
    if timestamp_ms >= _FIRST_SPAWN_MS["BARON_NASHOR"]:
        if not baron_kills:
            available.append("Baron Nashor")
        else:
            last_ms = max(e.timestamp_ms for e in baron_kills)
            if timestamp_ms >= last_ms + _RESPAWN_MS["BARON_NASHOR"]:
                available.append("Baron Nashor")

    # Void Grubs (6 total, gone at 20:00)
    if _VOID_GRUB_SPAWN_MS <= timestamp_ms < _VOID_GRUB_DESPAWN_MS:
        killed_before = sum(1 for ts, _ in void_grub_kills if ts < timestamp_ms)
        remaining = _VOID_GRUB_TOTAL - killed_before
        if remaining > 0:
            available.append(f"Void Grubs ({remaining} remaining)")

    return available


def _add_available_objectives(
    events: list,  # list[ObjectiveEvent]
    void_grub_kills: list[tuple[int, int]],
) -> None:
    """Populate available_for_trade on each event (excludes the event's own type)."""
    for ev in events:
        other = [e for e in events if e is not ev]
        all_available = _available_objectives_at(ev.timestamp_ms, other, void_grub_kills)
        current_display = _OBJ_DISPLAY_LOCAL.get(ev.objective_type, "")
        ev.available_for_trade = [a for a in all_available if not a.startswith(current_display)]


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
            killer_champion=g.killer_champion,
            killer_role=g.killer_role,
            victim_champion=g.victim_champion,
            victim_role=g.victim_role,
        ))
    return sorted(events, key=lambda e: e.timestamp_ms)


def classify_objectives(
    raw_objectives: list[RawObjective],
    wards: list[RawWard],
    jungler_team_id: int,
    death_timestamps: list[int] | None = None,
    void_grub_kills: list[tuple[int, int]] | None = None,
) -> list[ObjectiveEvent]:
    """Convert raw ELITE_MONSTER_KILL events into labelled ObjectiveEvents.

    Args:
        raw_objectives:  RawObjective list from JunglerTimelineData.
        wards:           All RawWard events (used for vision-before check).
        jungler_team_id: teamId of the jungler's team.
        void_grub_kills: (timestamp_ms, killer_team_id) pairs for each Void Grub kill.

    Returns:
        List of ObjectiveEvent, sorted by timestamp.
    """
    deaths = death_timestamps or []
    events: list[ObjectiveEvent] = []
    for obj in raw_objectives:
        jungler_was_dead = _was_jungler_dead(deaths, obj.timestamp_ms)
        pit = _pit_for(obj.monster_type)

        # When the jungler got the kill, they must have been at the pit —
        # don't trust the per-minute position frame which may lag by up to 60s.
        if obj.jungler_was_killer:
            d = 0.0
            near_pit = True
        else:
            d = dist(obj.jungler_x, obj.jungler_y, pit[0], pit[1])
            near_pit = (d <= NEAR_OBJECTIVE_RADIUS)

        had_vision = _had_vision_near(wards, pit, obj.timestamp_ms)
        events.append(ObjectiveEvent(
            timestamp_ms=obj.timestamp_ms,
            timestamp_str=_ms_to_str(obj.timestamp_ms),
            objective_type=obj.monster_type,
            secured_by_ally=(obj.killer_team_id == jungler_team_id),
            jungler_distance_from_pit=round(d),
            was_near_pit=near_pit,
            had_vision_before=had_vision,
            is_first_spawn=_is_first_spawn(obj.monster_type, obj.timestamp_ms),
            jungler_was_dead=jungler_was_dead,
            jungler_killed_objective=obj.jungler_was_killer,
        ))

    _detect_trades(events)
    _add_available_objectives(events, void_grub_kills or [])
    return sorted(events, key=lambda e: e.timestamp_ms)


def _detect_trades(events: list[ObjectiveEvent]) -> None:
    """Mark objectives that happened concurrently with an opposite-team objective."""
    for ev in events:
        for other in events:
            if ev is other:
                continue
            if ev.secured_by_ally == other.secured_by_ally:
                continue  # same team took both — not a trade
            if abs(ev.timestamp_ms - other.timestamp_ms) <= _TRADE_WINDOW_MS:
                ev.is_trade = True
                ev.trade_with = other.objective_type
                break


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
