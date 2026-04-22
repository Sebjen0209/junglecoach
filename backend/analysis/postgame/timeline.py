"""Parses Riot Match-V5 timeline + summary into structured jungler data.

Identifies the jungler participant, then extracts:
  - Per-minute position frames (from participantFrames)
  - Raw gank events (CHAMPION_KILL where jungler is killer/assister)
  - Raw objective events (ELITE_MONSTER_KILL for dragon/baron/herald)
  - All ward placements (used later for vision checks)

Coordinate system: Summoner's Rift is 0–14820 on both axes.
  Top lane  → high y (~11000+)
  Bot lane  → low y (~3000-)
  Blue base → (~540, 490)
  Red base  → (~14340, 14390)
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Map constants (public — imported by events.py)
MAP_SIZE = 14820

BLUE_TEAM = 100
RED_TEAM = 200

# Objective pit centres
BARON_PIT: tuple[int, int] = (5007, 10471)
DRAGON_PIT: tuple[int, int] = (9866, 4414)

# Fountain positions
BLUE_BASE: tuple[int, int] = (540, 490)
RED_BASE: tuple[int, int] = (14340, 14390)

# Distance thresholds
NEAR_OBJECTIVE_RADIUS = 3000       # within this → jungler is "near" the pit
NEAR_BASE_RADIUS = 2500            # within this → jungler is in base
WARD_NEAR_OBJECTIVE_RADIUS = 2000  # ward counts as covering the pit


def dist(ax: int, ay: int, bx: int, by: int) -> float:
    """Euclidean distance between two map points."""
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


# ---------------------------------------------------------------------------
# Raw event containers (dataclasses, not Pydantic — internal only)
# ---------------------------------------------------------------------------

@dataclass
class PositionFrame:
    minute: int
    x: int
    y: int


@dataclass
class RawGank:
    timestamp_ms: int
    killer_id: int
    victim_id: int
    assisting_ids: list[int]
    position_x: int
    position_y: int
    killer_champion: str = ""
    killer_role: str = ""
    victim_champion: str = ""
    victim_role: str = ""


@dataclass
class RawObjective:
    timestamp_ms: int
    monster_type: str    # "DRAGON" | "BARON_NASHOR" | "RIFTHERALD"
    killer_id: int
    killer_team_id: int
    jungler_x: int
    jungler_y: int


@dataclass
class RawWard:
    timestamp_ms: int
    placer_id: int
    x: int
    y: int


@dataclass
class JunglerTimelineData:
    """All extracted data for the jungler participant."""

    participant_id: int
    team_id: int
    champion_name: str
    puuid: str
    position_frames: list[PositionFrame] = field(default_factory=list)
    ganks: list[RawGank] = field(default_factory=list)
    objectives: list[RawObjective] = field(default_factory=list)
    wards: list[RawWard] = field(default_factory=list)
    death_timestamps: list[int] = field(default_factory=list)
    # participantId → {champion, role, team_id} — built at extraction time
    participant_info: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Main extraction logic
# ---------------------------------------------------------------------------

def extract_jungler_data(
    match_data: dict,
    timeline_data: dict,
    target_puuid: str | None = None,
) -> JunglerTimelineData:
    """Parse match summary + timeline into structured JunglerTimelineData.

    Args:
        match_data:    Response from GET /matches/{matchId}
        timeline_data: Response from GET /matches/{matchId}/timeline
        target_puuid:  PUUID of the player we're coaching. If given, we find
                       the jungler on that player's team. Otherwise falls back
                       to the blue-team jungler.

    Returns:
        JunglerTimelineData ready for event classification.

    Raises:
        ValueError: If no jungle participant is found.
    """
    jungler = _find_jungler(match_data, target_puuid)
    jungler_id = jungler["participantId"]

    data = JunglerTimelineData(
        participant_id=jungler_id,
        team_id=jungler["teamId"],
        champion_name=jungler.get("championName", "Unknown"),
        puuid=jungler.get("puuid", ""),
    )

    # Build participant lookup before processing frames so kill events can resolve names/roles
    data.participant_info = {
        p["participantId"]: {
            "champion": p.get("championName", "Unknown"),
            "role": p.get("teamPosition", "UNKNOWN"),
            "team_id": p["teamId"],
        }
        for p in match_data["info"]["participants"]
    }

    for frame in timeline_data["info"]["frames"]:
        _process_frame(frame, data, match_data)

    logger.info(
        "Parsed %s (id=%d): %d frames, %d ganks, %d objectives, %d wards",
        data.champion_name,
        jungler_id,
        len(data.position_frames),
        len(data.ganks),
        len(data.objectives),
        len(data.wards),
    )
    return data


def _find_jungler(match_data: dict, target_puuid: str | None) -> dict:
    """Identify the jungle participant to analyse."""
    participants = match_data["info"]["participants"]

    if target_puuid:
        # Find the target player's team, then their team's jungler
        target_team: int | None = None
        for p in participants:
            if p["puuid"] == target_puuid:
                if p.get("teamPosition") == "JUNGLE":
                    return p
                target_team = p["teamId"]
                break

        if target_team is not None:
            for p in participants:
                if p["teamId"] == target_team and p.get("teamPosition") == "JUNGLE":
                    return p

    # Fallback: blue-team jungler first, then any jungler
    for preferred_team in (BLUE_TEAM, RED_TEAM):
        for p in participants:
            if p.get("teamPosition") == "JUNGLE" and p["teamId"] == preferred_team:
                return p

    raise ValueError("No JUNGLE participant found in match data")


def _process_frame(frame: dict, data: JunglerTimelineData, match_data: dict) -> None:
    """Extract position and events from a single timeline frame."""
    ts = frame["timestamp"]
    minute = round(ts / 60_000)

    # Position snapshot
    p_frame = frame["participantFrames"].get(str(data.participant_id))
    if p_frame and "position" in p_frame:
        pos = p_frame["position"]
        data.position_frames.append(PositionFrame(minute=minute, x=pos["x"], y=pos["y"]))

    for event in frame.get("events", []):
        etype = event.get("type")

        if etype == "CHAMPION_KILL":
            _handle_champion_kill(event, data)

        elif etype == "ELITE_MONSTER_KILL":
            _handle_objective(event, data, match_data)

        elif etype == "WARD_PLACED":
            pos = event.get("position", {})
            data.wards.append(RawWard(
                timestamp_ms=event["timestamp"],
                placer_id=event.get("creatorId", 0),
                x=pos.get("x", 0),
                y=pos.get("y", 0),
            ))


def _handle_champion_kill(event: dict, data: JunglerTimelineData) -> None:
    assisting = event.get("assistingParticipantIds", [])
    killer = event.get("killerId", 0)
    victim = event.get("victimId", 0)

    # Track when the jungler dies so objectives can check if they were dead
    if victim == data.participant_id:
        data.death_timestamps.append(event["timestamp"])

    if killer == data.participant_id or data.participant_id in assisting:
        pos = event.get("position", {})
        killer_info = data.participant_info.get(killer, {})
        victim_info = data.participant_info.get(victim, {})
        data.ganks.append(RawGank(
            timestamp_ms=event["timestamp"],
            killer_id=killer,
            victim_id=victim,
            assisting_ids=assisting,
            position_x=pos.get("x", 0),
            position_y=pos.get("y", 0),
            killer_champion=killer_info.get("champion", "Unknown"),
            killer_role=killer_info.get("role", "UNKNOWN"),
            victim_champion=victim_info.get("champion", "Unknown"),
            victim_role=victim_info.get("role", "UNKNOWN"),
        ))


def _handle_objective(event: dict, data: JunglerTimelineData, match_data: dict) -> None:
    monster = event.get("monsterType", "")
    if monster not in ("DRAGON", "BARON_NASHOR", "RIFTHERALD"):
        return

    ts = event["timestamp"]
    j_pos = _position_at(data.position_frames, ts)
    killer_id = event.get("killerId", 0)
    killer_team = _team_of(match_data, killer_id)

    data.objectives.append(RawObjective(
        timestamp_ms=ts,
        monster_type=monster,
        killer_id=killer_id,
        killer_team_id=killer_team,
        jungler_x=j_pos[0],
        jungler_y=j_pos[1],
    ))


def _position_at(frames: list[PositionFrame], timestamp_ms: int) -> tuple[int, int]:
    """Return the jungler's position from the frame closest to timestamp_ms."""
    if not frames:
        return 0, 0
    target = timestamp_ms / 60_000
    closest = min(frames, key=lambda f: abs(f.minute - target))
    return closest.x, closest.y


def _team_of(match_data: dict, participant_id: int) -> int:
    """Look up a participant's teamId by their participantId."""
    for p in match_data["info"]["participants"]:
        if p["participantId"] == participant_id:
            return p["teamId"]
    return 0
