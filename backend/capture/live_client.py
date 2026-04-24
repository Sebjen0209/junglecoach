"""Riot Live Client Data API reader.

Polls https://127.0.0.1:2999 — Riot's official local in-game data API — to
extract structured game state without screen capture or OCR.

The API runs on the player's machine and is only active during a live game.
It exposes only data that is already visible to the player (champion names,
scores, CS, summoner spells) — Riot explicitly permits third-party tools to
consume it.

Reference: https://developer.riotgames.com/docs/lol#game-client-api
"""

import logging
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

_ALL_GAME_DATA_URL = "https://127.0.0.1:2999/liveclientdata/allgamedata"
_EVENT_DATA_URL = "https://127.0.0.1:2999/liveclientdata/eventdata"

# Must complete well within one capture cycle. The API is local so 2s is generous.
_TIMEOUT = 2.0

# Objective spawn / respawn timers in game-seconds
_DRAGON_FIRST_SPAWN_S: float = 5 * 60
_DRAGON_RESPAWN_S: float = 5 * 60
_BARON_FIRST_SPAWN_S: float = 20 * 60
_BARON_RESPAWN_S: float = 6 * 60
_HERALD_SPAWN_S: float = 8 * 60
_HERALD_DESPAWN_S: float = 20 * 60  # gone when Baron spawns
_HERALD_MAX_KILLS: int = 2           # max 2 per game

# Only count a laner as exploitably dead if they have this many seconds left on respawn
_MIN_RESPAWN_TO_EXPLOIT_S: float = 5.0

# Maps the API's position strings to our internal role names.
# Riot uses "UTILITY" for the support role.
_POSITION_MAP: dict[str, str] = {
    "TOP": "top",
    "JUNGLE": "jungle",
    "MIDDLE": "mid",
    "BOTTOM": "bot",
    "UTILITY": "support",
    "SUPPORT": "support",  # seen in some older API payloads
}

# Summoner spell internal names that indicate kill pressure on the laner.
# These are stable across patches (unlike display names which can be localised).
_KILL_PRESSURE_SPELLS = frozenset({"SummonerDot"})  # Ignite

# Ult is available for most champions from level 6.
_ULT_AVAILABLE_LEVEL = 6


@dataclass
class PlayerSnapshot:
    """One player's live state extracted from the Live Client API."""

    champion_name: str
    team: str               # "ORDER" (blue side) | "CHAOS" (red side)
    position: str           # "top" | "jungle" | "mid" | "bot" | "support"
    level: int
    summoner_spells: frozenset[str]  # raw internal names, e.g. {"SummonerFlash", "SummonerDot"}
    cs: int
    kills: int
    deaths: int
    assists: int
    summoner_name: str
    is_dead: bool = False           # True while the player is on the respawn screen
    respawn_timer: float = 0.0      # seconds remaining until respawn (0 when alive)


@dataclass
class GameSnapshot:
    """Full game state from a single Live Client API call.

    All data here is already visible to the local player — the API does not
    expose fog-of-war information such as enemy positions when out of vision.
    """

    ally_team: str                       # "ORDER" | "CHAOS"
    ally_players: list[PlayerSnapshot]   # 5 players on our team
    enemy_players: list[PlayerSnapshot]  # 5 players on the enemy team
    game_time_seconds: float             # raw game clock, e.g. 845.3
    game_mode: str                       # "CLASSIC" | "ARAM" | "PRACTICETOOL" | etc.

    def ally_roles(self) -> dict[str, str]:
        """Return {role: champion_name} for the ally team."""
        return {p.position: p.champion_name for p in self.ally_players}

    def enemy_roles(self) -> dict[str, str]:
        """Return {role: champion_name} for the enemy team."""
        return {p.position: p.champion_name for p in self.enemy_players}

    def cs_diffs(self) -> dict[str, int]:
        """Return {role: cs_diff} for the three gank lanes (positive = ally ahead)."""
        ally_cs = {p.position: p.cs for p in self.ally_players}
        enemy_cs = {p.position: p.cs for p in self.enemy_players}
        return {
            role: ally_cs.get(role, 0) - enemy_cs.get(role, 0)
            for role in ("top", "mid", "bot")
        }

    def enemy_has_flash(self) -> dict[str, bool]:
        """Return {role: bool} — True if the enemy laner has Flash equipped.

        Flash is visible on the TAB scoreboard and in the Live Client API.
        An enemy without Flash is significantly easier to kill on a gank.
        """
        return {
            p.position: ("SummonerFlash" in p.summoner_spells)
            for p in self.enemy_players
            if p.position in ("top", "mid", "bot")
        }

    def level_diffs(self) -> dict[str, int]:
        """Return {role: int} — positive when ally is higher level than enemy."""
        ally_levels = {p.position: p.level for p in self.ally_players}
        enemy_levels = {p.position: p.level for p in self.enemy_players}
        return {
            role: ally_levels.get(role, 1) - enemy_levels.get(role, 1)
            for role in ("top", "mid", "bot")
        }

    def dead_laners(self) -> dict[str, tuple[bool, bool]]:
        """Return {role: (ally_is_dead, enemy_is_dead)} for gank lanes.

        Only flags players as dead when they have enough respawn time remaining
        to make the dead-laner information tactically relevant (>5 seconds).
        """
        ally_dead = {
            p.position: (p.is_dead and p.respawn_timer > _MIN_RESPAWN_TO_EXPLOIT_S)
            for p in self.ally_players
        }
        enemy_dead = {
            p.position: (p.is_dead and p.respawn_timer > _MIN_RESPAWN_TO_EXPLOIT_S)
            for p in self.enemy_players
        }
        return {
            role: (ally_dead.get(role, False), enemy_dead.get(role, False))
            for role in ("top", "mid", "bot")
        }

    def kill_pressure(self) -> dict[str, bool]:
        """Return {role: bool} — True if the ally laner currently has kill pressure.

        Kill pressure is estimated from three signals we already have for free:

        1. Has Ignite equipped — designed for kill threat, dominates trades.
        2. Snowballing hard — 2+ kills ahead of deaths, likely items/gold lead.
        3. Ult available (level 6+) AND winning or even in lane — can combo for a kill.

        This is intentionally conservative. False negatives (missing pressure) are
        safer than false positives (suggesting a gank that goes wrong).
        """
        ally_by_pos = {p.position: p for p in self.ally_players}
        result: dict[str, bool] = {}
        for role in ("top", "mid", "bot"):
            ally = ally_by_pos.get(role)
            result[role] = _has_kill_pressure(ally) if ally else False
        return result


def _has_kill_pressure(ally: PlayerSnapshot) -> bool:
    """Estimate whether a single laner currently has kill pressure."""
    # Ignite equipped — direct kill pressure spell
    if ally.summoner_spells & _KILL_PRESSURE_SPELLS:
        return True

    # Snowballing: meaningfully ahead in kills, not dying
    kill_lead = ally.kills - ally.deaths
    if kill_lead >= 2:
        return True

    # Ult available AND at least breaking even in lane
    if ally.level >= _ULT_AVAILABLE_LEVEL and ally.kills >= ally.deaths:
        return True

    return False


def get_snapshot() -> "GameSnapshot | None":
    """Fetch current game state from the Riot Live Client Data API.

    Returns:
        A GameSnapshot if a live game is in progress and the API is reachable,
        otherwise None.
    """
    try:
        # verify=False is intentional: the API runs on 127.0.0.1 using a
        # Riot-issued self-signed certificate. There is no MitM risk on loopback.
        with httpx.Client(verify=False, timeout=_TIMEOUT) as client:
            resp = client.get(_ALL_GAME_DATA_URL)
    except Exception as exc:
        logger.debug("Live Client API not reachable: %s", exc)
        return None

    if resp.status_code != 200:
        logger.debug("Live Client API returned HTTP %d", resp.status_code)
        return None

    try:
        return _parse_snapshot(resp.json())
    except Exception as exc:
        logger.error("Failed to parse Live Client API response: %s", exc, exc_info=True)
        return None


def _parse_snapshot(data: dict) -> "GameSnapshot | None":
    """Parse the raw allgamedata JSON into a GameSnapshot."""
    game_data = data.get("gameData", {})
    game_time = float(game_data.get("gameTime", 0.0))
    game_mode = str(game_data.get("gameMode", "UNKNOWN"))

    # activePlayer identifies whose machine this tool is running on, so we
    # can determine which team is ours.
    active_summoner: str = data.get("activePlayer", {}).get("summonerName", "")

    all_players: list[dict] = data.get("allPlayers", [])
    ally_team = _identify_ally_team(all_players, active_summoner)

    ally_players: list[PlayerSnapshot] = []
    enemy_players: list[PlayerSnapshot] = []

    for raw_player in all_players:
        player = _parse_player(raw_player)
        if player is None:
            continue
        if player.team == ally_team:
            ally_players.append(player)
        else:
            enemy_players.append(player)

    if len(ally_players) != 5 or len(enemy_players) != 5:
        logger.warning(
            "Unexpected player counts — ally=%d enemy=%d "
            "(custom game, bot game, or spectator?)",
            len(ally_players),
            len(enemy_players),
        )

    return GameSnapshot(
        ally_team=ally_team,
        ally_players=ally_players,
        enemy_players=enemy_players,
        game_time_seconds=game_time,
        game_mode=game_mode,
    )


def _identify_ally_team(all_players: list[dict], active_summoner: str) -> str:
    """Return 'ORDER' or 'CHAOS' for the active player's team."""
    for player in all_players:
        if player.get("summonerName") == active_summoner:
            return str(player.get("team", "ORDER"))
    logger.warning(
        "Active summoner %r not found in player list — defaulting to ORDER",
        active_summoner,
    )
    return "ORDER"


def _parse_player(raw: dict) -> "PlayerSnapshot | None":
    """Parse a single player entry from the allPlayers list.

    Returns None if the player's position cannot be mapped (e.g. bots in
    Practice Tool, or ARAM where positions are 'NONE').
    """
    position_raw = str(raw.get("position", "NONE")).upper()
    position = _POSITION_MAP.get(position_raw)
    if position is None:
        logger.debug("Skipping player with unmapped position %r", position_raw)
        return None

    try:
        scores = raw.get("scores", {})
        return PlayerSnapshot(
            champion_name=str(raw["championName"]),
            team=str(raw.get("team", "ORDER")),
            position=position,
            level=int(raw.get("level", 1)),
            summoner_spells=_parse_summoner_spells(raw.get("summonerSpells", {})),
            cs=int(scores.get("creepScore", 0)),
            kills=int(scores.get("kills", 0)),
            deaths=int(scores.get("deaths", 0)),
            assists=int(scores.get("assists", 0)),
            summoner_name=str(raw.get("summonerName", "")),
            is_dead=bool(raw.get("isDead", False)),
            respawn_timer=float(raw.get("respawnTimer", 0.0)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning(
            "Could not parse player entry for %r: %s",
            raw.get("summonerName", "unknown"),
            exc,
        )
        return None


def get_events() -> list[dict]:
    """Fetch the full event history from the Riot Live Client eventdata endpoint.

    Returns an empty list if the game is not running or the API is unreachable.
    The list accumulates all events from game start, so it grows over the game.
    """
    try:
        with httpx.Client(verify=False, timeout=_TIMEOUT) as client:
            resp = client.get(_EVENT_DATA_URL)
    except Exception as exc:
        logger.debug("Live Client eventdata not reachable: %s", exc)
        return []

    if resp.status_code != 200:
        logger.debug("Live Client eventdata returned HTTP %d", resp.status_code)
        return []

    try:
        return resp.json().get("Events", [])
    except Exception as exc:
        logger.error("Failed to parse eventdata response: %s", exc)
        return []


def compute_objective_timers(events: list[dict], game_time_s: float) -> "ObjectiveTimers":
    """Compute current objective spawn state from accumulated event history.

    Args:
        events:       Event list from get_events() or an empty list.
        game_time_s:  Current game time in seconds (from the allgamedata response).

    Returns:
        ObjectiveTimers describing which objectives are up and when the next spawn is.
    """
    from models import ObjectiveTimers  # local import avoids top-level circular risk

    dragon_kill_times: list[float] = []
    baron_kill_times: list[float] = []
    herald_kill_count: int = 0

    for evt in events:
        name = evt.get("EventName", "")
        etime = float(evt.get("EventTime", 0.0))
        if name == "DragonKill":
            dragon_kill_times.append(etime)
        elif name == "BaronKill":
            baron_kill_times.append(etime)
        elif name == "HeraldKill":
            herald_kill_count += 1

    # --- Dragon ---
    if dragon_kill_times:
        next_dragon = max(dragon_kill_times) + _DRAGON_RESPAWN_S
        dragon_up = game_time_s >= next_dragon
        dragon_spawns_at: float | None = None if dragon_up else next_dragon
    else:
        dragon_up = game_time_s >= _DRAGON_FIRST_SPAWN_S
        dragon_spawns_at = None if dragon_up else _DRAGON_FIRST_SPAWN_S

    # --- Baron ---
    if baron_kill_times:
        next_baron = max(baron_kill_times) + _BARON_RESPAWN_S
        baron_up = game_time_s >= next_baron
        baron_spawns_at: float | None = None if baron_up else next_baron
    else:
        baron_up = game_time_s >= _BARON_FIRST_SPAWN_S
        baron_spawns_at = None if baron_up else _BARON_FIRST_SPAWN_S

    # --- Rift Herald (max 2, present 8:00–20:00) ---
    herald_available = (
        _HERALD_SPAWN_S <= game_time_s < _HERALD_DESPAWN_S
        and herald_kill_count < _HERALD_MAX_KILLS
    )

    # --- Human-readable alert for the overlay ---
    next_objective_alert = _build_objective_alert(
        game_time_s,
        dragon_up, dragon_spawns_at,
        baron_up, baron_spawns_at,
        herald_available,
    )

    return ObjectiveTimers(
        dragon_up=dragon_up,
        dragon_spawns_at=dragon_spawns_at,
        baron_up=baron_up,
        baron_spawns_at=baron_spawns_at,
        herald_available=herald_available,
        next_objective_alert=next_objective_alert,
    )


def _build_objective_alert(
    game_time_s: float,
    dragon_up: bool,
    dragon_spawns_at: float | None,
    baron_up: bool,
    baron_spawns_at: float | None,
    herald_available: bool,
) -> str:
    """Return a short overlay-ready string summarising imminent objective windows."""
    parts: list[str] = []

    if baron_up:
        parts.append("Baron UP")
    elif baron_spawns_at is not None:
        secs = int(baron_spawns_at - game_time_s)
        if secs <= 90:
            parts.append(f"Baron in {secs}s")

    if dragon_up:
        parts.append("Dragon UP")
    elif dragon_spawns_at is not None:
        secs = int(dragon_spawns_at - game_time_s)
        if secs <= 90:
            parts.append(f"Dragon in {secs}s")

    if herald_available:
        parts.append("Herald available")

    return " | ".join(parts)


def _parse_summoner_spells(raw_spells: dict) -> frozenset[str]:
    """Extract the set of summoner spell internal names from a player entry.

    The API returns summonerSpellOne / summonerSpellTwo, each with a
    rawDisplayName field that is stable across patches (e.g. 'SummonerDot').
    We use raw names rather than display names to avoid localisation issues.
    """
    names = set()
    for slot in ("summonerSpellOne", "summonerSpellTwo"):
        raw_name = raw_spells.get(slot, {}).get("rawDisplayName", "")
        if raw_name:
            names.add(raw_name)
    return frozenset(names)
