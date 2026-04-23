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

# Must complete well within one capture cycle. The API is local so 2s is generous.
_TIMEOUT = 2.0

# Lane letter → internal lane name (used when parsing tower kill event names).
_LANE_MAP: dict[str, str] = {"L": "top", "C": "mid", "R": "bot"}

# Objective timing constants (seconds, patch-stable values).
_HERALD_DESPAWN_TIME = 19 * 60 + 45   # Herald disappears at 19:45 if not killed
_FIRST_DRAGON_SPAWN  = 5 * 60         # Dragon first appears at 5:00
_DRAGON_RESPAWN      = 5 * 60         # Dragon respawns 5 min after each kill
_FIRST_BARON_SPAWN   = 20 * 60        # Baron first appears at 20:00
_BARON_RESPAWN       = 6 * 60         # Baron respawns 6 min after kill

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
class MacroSnapshot:
    """Objective and tower state derived from the Live Client events array.

    Drives macro-mode analysis once the laning phase has broken down.
    All data comes from public game events — no fog-of-war information.

    dragon_spawn_in / baron_spawn_in semantics:
      None  → objective is currently alive on the map (or baron not yet spawned
              and past spawn time)
      float → seconds until the objective spawns / respawns
    """

    ally_outer_down: dict[str, bool]    # {"top": T/F, "mid": T/F, "bot": T/F}
    enemy_outer_down: dict[str, bool]
    ally_dragon_stacks: int
    enemy_dragon_stacks: int
    dragon_spawn_in: float | None
    baron_spawn_in: float | None
    herald_available: bool


def _default_macro() -> MacroSnapshot:
    """Return a clean MacroSnapshot used as the default when events cannot be parsed."""
    return MacroSnapshot(
        ally_outer_down={"top": False, "mid": False, "bot": False},
        enemy_outer_down={"top": False, "mid": False, "bot": False},
        ally_dragon_stacks=0,
        enemy_dragon_stacks=0,
        dragon_spawn_in=None,
        baron_spawn_in=None,
        herald_available=True,
    )


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
    macro: MacroSnapshot = field(default_factory=_default_macro)

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

    # Build summoner→team map so dragon kills can be attributed to the right team.
    summoner_team_map: dict[str, str] = {
        p["summonerName"]: str(p.get("team", ""))
        for p in all_players
        if "summonerName" in p
    }

    events: list[dict] = data.get("events", {}).get("Events", [])
    macro = _parse_macro_snapshot(events, game_time, ally_team, summoner_team_map)

    return GameSnapshot(
        ally_team=ally_team,
        ally_players=ally_players,
        enemy_players=enemy_players,
        game_time_seconds=game_time,
        game_mode=game_mode,
        macro=macro,
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
        )
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning(
            "Could not parse player entry for %r: %s",
            raw.get("summonerName", "unknown"),
            exc,
        )
        return None


def _parse_macro_snapshot(
    events: list[dict],
    game_time: float,
    ally_team: str,
    summoner_team_map: dict[str, str],
) -> MacroSnapshot:
    """Build MacroSnapshot from the raw events array and current game clock.

    Tower names follow the pattern ``Turret_T{team}_{lane}_{tier}_A`` where
    team is T1 (ORDER/blue) or T2 (CHAOS/red), lane is L/C/R, and tier
    increases toward the base (outer towers are typically the first to fall
    per lane, so we treat the first kill per (team, lane) as the outer).
    """
    ally_t = "T1" if ally_team == "ORDER" else "T2"
    enemy_t = "T2" if ally_team == "ORDER" else "T1"

    ally_tower_kills:  dict[str, int] = {"top": 0, "mid": 0, "bot": 0}
    enemy_tower_kills: dict[str, int] = {"top": 0, "mid": 0, "bot": 0}

    dragon_kills: list[tuple[float, str]] = []   # (timestamp, killer_team)
    baron_kills:  list[float] = []
    herald_killed = False

    for event in events:
        ename = event.get("EventName", "")

        if ename == "TurretKilled":
            turret = event.get("TurretKilled", "")
            parts = turret.split("_")
            # ["Turret", "T1", "L", "03", "A"] — lane is index 2
            if len(parts) >= 4:
                team_part = parts[1]
                lane = _LANE_MAP.get(parts[2])
                if lane is not None:
                    if team_part == ally_t:
                        ally_tower_kills[lane] += 1
                    elif team_part == enemy_t:
                        enemy_tower_kills[lane] += 1

        elif ename == "DragonKill":
            kill_time = float(event.get("EventTime", 0))
            killer_team = summoner_team_map.get(event.get("KillerName", ""), "")
            dragon_kills.append((kill_time, killer_team))

        elif ename == "HeraldKill":
            herald_killed = True

        elif ename == "BaronKill":
            baron_kills.append(float(event.get("EventTime", 0)))

    ally_outer_down  = {lane: count > 0 for lane, count in ally_tower_kills.items()}
    enemy_outer_down = {lane: count > 0 for lane, count in enemy_tower_kills.items()}

    ally_dragon_stacks  = sum(1 for _, team in dragon_kills if team == ally_team)
    enemy_dragon_stacks = sum(1 for _, team in dragon_kills if team and team != ally_team)

    return MacroSnapshot(
        ally_outer_down=ally_outer_down,
        enemy_outer_down=enemy_outer_down,
        ally_dragon_stacks=ally_dragon_stacks,
        enemy_dragon_stacks=enemy_dragon_stacks,
        dragon_spawn_in=_calc_dragon_spawn(dragon_kills, game_time),
        baron_spawn_in=_calc_baron_spawn(baron_kills, game_time),
        herald_available=not herald_killed and game_time < _HERALD_DESPAWN_TIME,
    )


def _calc_dragon_spawn(
    dragon_kills: list[tuple[float, str]], game_time: float
) -> float | None:
    """Return seconds until next dragon is available, or None if it is alive now."""
    if not dragon_kills:
        remaining = _FIRST_DRAGON_SPAWN - game_time
        return max(0.0, remaining) if remaining > 0 else None
    last_kill_time = max(t for t, _ in dragon_kills)
    remaining = (last_kill_time + _DRAGON_RESPAWN) - game_time
    return max(0.0, remaining) if remaining > 0 else None


def _calc_baron_spawn(baron_kills: list[float], game_time: float) -> float | None:
    """Return seconds until baron spawns/respawns, or None if it is alive now."""
    if not baron_kills:
        # Baron not yet killed — is it spawned?
        if game_time < _FIRST_BARON_SPAWN:
            return _FIRST_BARON_SPAWN - game_time   # counting down to first spawn
        return None  # baron is alive and has never been killed
    last_kill_time = max(baron_kills)
    remaining = (last_kill_time + _BARON_RESPAWN) - game_time
    return max(0.0, remaining) if remaining > 0 else None


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
