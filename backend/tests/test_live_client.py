"""Tests for capture/live_client.py.

httpx is mocked throughout — these tests validate parsing logic, team
identification, CS diff calculation, and kill pressure estimation against
realistic API payloads.
"""

from unittest.mock import MagicMock, patch

import pytest

from capture.live_client import (
    GameSnapshot,
    PlayerSnapshot,
    _has_kill_pressure,
    _identify_ally_team,
    _parse_player,
    _parse_snapshot,
    _parse_summoner_spells,
    compute_objective_timers,
    get_events,
    get_snapshot,
)


# ---------------------------------------------------------------------------
# Fixtures — realistic API response payloads
# ---------------------------------------------------------------------------

def _make_player(
    summoner: str,
    champion: str,
    team: str,
    position: str,
    cs: int = 100,
    kills: int = 2,
    deaths: int = 1,
    assists: int = 3,
    level: int = 7,
    spells: tuple[str, str] = ("SummonerFlash", "SummonerTeleport"),
    is_dead: bool = False,
    respawn_timer: float = 0.0,
) -> dict:
    return {
        "summonerName": summoner,
        "championName": champion,
        "team": team,
        "position": position,
        "level": level,
        "summonerSpells": {
            "summonerSpellOne": {"rawDisplayName": spells[0], "displayName": spells[0]},
            "summonerSpellTwo": {"rawDisplayName": spells[1], "displayName": spells[1]},
        },
        "scores": {
            "creepScore": cs,
            "kills": kills,
            "deaths": deaths,
            "assists": assists,
        },
        "isDead": is_dead,
        "respawnTimer": respawn_timer,
    }


_ALLY_PLAYERS = [
    _make_player("Alice", "Riven",   "ORDER", "TOP",     cs=87,  kills=3, deaths=0),
    _make_player("Bob",   "LeeSin",  "ORDER", "JUNGLE",  cs=52,  kills=1, deaths=1),
    _make_player("Carol", "Zed",     "ORDER", "MIDDLE",  cs=110, kills=2, deaths=1),
    _make_player("Dave",  "Jinx",    "ORDER", "BOTTOM",  cs=130, kills=1, deaths=2),
    _make_player("Eve",   "Thresh",  "ORDER", "UTILITY", cs=20,  kills=0, deaths=1),
]

_ENEMY_PLAYERS = [
    _make_player("P6",  "Gangplank", "CHAOS", "TOP",     cs=70),
    _make_player("P7",  "Graves",    "CHAOS", "JUNGLE",  cs=60),
    _make_player("P8",  "Orianna",   "CHAOS", "MIDDLE",  cs=95),
    _make_player("P9",  "Caitlyn",   "CHAOS", "BOTTOM",  cs=120),
    _make_player("P10", "Lulu",      "CHAOS", "UTILITY", cs=15),
]

_ALL_GAME_DATA = {
    "activePlayer": {"summonerName": "Alice"},
    "allPlayers": _ALLY_PLAYERS + _ENEMY_PLAYERS,
    "gameData": {
        "gameTime": 845.3,
        "gameMode": "CLASSIC",
    },
}


# ---------------------------------------------------------------------------
# _parse_summoner_spells
# ---------------------------------------------------------------------------

class TestParseSummonerSpells:
    def test_parses_both_spells(self):
        raw = {
            "summonerSpellOne": {"rawDisplayName": "SummonerFlash"},
            "summonerSpellTwo": {"rawDisplayName": "SummonerDot"},
        }
        result = _parse_summoner_spells(raw)
        assert result == frozenset({"SummonerFlash", "SummonerDot"})

    def test_empty_spells_returns_empty_frozenset(self):
        assert _parse_summoner_spells({}) == frozenset()

    def test_missing_raw_display_name_is_skipped(self):
        raw = {
            "summonerSpellOne": {"displayName": "Flash"},  # no rawDisplayName
            "summonerSpellTwo": {"rawDisplayName": "SummonerDot"},
        }
        result = _parse_summoner_spells(raw)
        assert result == frozenset({"SummonerDot"})


# ---------------------------------------------------------------------------
# _identify_ally_team
# ---------------------------------------------------------------------------

class TestIdentifyAllyTeam:
    def test_finds_correct_team(self):
        assert _identify_ally_team(_ALLY_PLAYERS + _ENEMY_PLAYERS, "Alice") == "ORDER"

    def test_finds_chaos_team(self):
        assert _identify_ally_team(_ALLY_PLAYERS + _ENEMY_PLAYERS, "P6") == "CHAOS"

    def test_unknown_summoner_defaults_to_order(self):
        assert _identify_ally_team(_ALLY_PLAYERS, "Nobody") == "ORDER"

    def test_empty_player_list_defaults_to_order(self):
        assert _identify_ally_team([], "Alice") == "ORDER"


# ---------------------------------------------------------------------------
# _parse_player
# ---------------------------------------------------------------------------

class TestParsePlayer:
    def test_parses_valid_player(self):
        raw = _make_player("Alice", "Riven", "ORDER", "TOP", cs=87, kills=3, level=8,
                           spells=("SummonerFlash", "SummonerDot"))
        result = _parse_player(raw)
        assert result is not None
        assert result.champion_name == "Riven"
        assert result.team == "ORDER"
        assert result.position == "top"
        assert result.cs == 87
        assert result.kills == 3
        assert result.level == 8
        assert "SummonerDot" in result.summoner_spells

    def test_maps_middle_to_mid(self):
        raw = _make_player("X", "Zed", "ORDER", "MIDDLE")
        assert _parse_player(raw).position == "mid"

    def test_maps_utility_to_support(self):
        raw = _make_player("X", "Thresh", "ORDER", "UTILITY")
        assert _parse_player(raw).position == "support"

    def test_returns_none_for_unknown_position(self):
        raw = _make_player("X", "Lux", "ORDER", "NONE")
        assert _parse_player(raw) is None

    def test_returns_none_for_missing_champion_name(self):
        raw = {"summonerName": "X", "team": "ORDER", "position": "TOP",
               "level": 5, "summonerSpells": {}, "scores": {}}
        assert _parse_player(raw) is None


# ---------------------------------------------------------------------------
# _has_kill_pressure
# ---------------------------------------------------------------------------

class TestHasKillPressure:
    def _player(self, kills=0, deaths=0, level=5, spells=("SummonerFlash", "SummonerTeleport")):
        raw = _make_player("X", "Riven", "ORDER", "TOP",
                           kills=kills, deaths=deaths, level=level, spells=spells)
        return _parse_player(raw)

    def test_ignite_always_gives_kill_pressure(self):
        p = self._player(kills=0, deaths=0, level=1, spells=("SummonerFlash", "SummonerDot"))
        assert _has_kill_pressure(p) is True

    def test_snowballing_2plus_ahead_gives_kill_pressure(self):
        p = self._player(kills=3, deaths=1)  # kill_lead = 2
        assert _has_kill_pressure(p) is True

    def test_ult_available_and_winning_gives_kill_pressure(self):
        p = self._player(kills=2, deaths=1, level=6)
        assert _has_kill_pressure(p) is True

    def test_ult_available_but_behind_no_pressure(self):
        p = self._player(kills=0, deaths=2, level=6)
        assert _has_kill_pressure(p) is False

    def test_pre_6_no_ignite_no_pressure(self):
        p = self._player(kills=1, deaths=0, level=5)
        assert _has_kill_pressure(p) is False

    def test_flash_teleport_no_kills_no_pressure(self):
        p = self._player(kills=0, deaths=0, level=4,
                         spells=("SummonerFlash", "SummonerTeleport"))
        assert _has_kill_pressure(p) is False


# ---------------------------------------------------------------------------
# _parse_snapshot
# ---------------------------------------------------------------------------

class TestParseSnapshot:
    def test_returns_game_snapshot(self):
        assert isinstance(_parse_snapshot(_ALL_GAME_DATA), GameSnapshot)

    def test_ally_team_is_order(self):
        assert _parse_snapshot(_ALL_GAME_DATA).ally_team == "ORDER"

    def test_five_ally_players(self):
        assert len(_parse_snapshot(_ALL_GAME_DATA).ally_players) == 5

    def test_five_enemy_players(self):
        assert len(_parse_snapshot(_ALL_GAME_DATA).enemy_players) == 5

    def test_game_time_parsed(self):
        assert _parse_snapshot(_ALL_GAME_DATA).game_time_seconds == pytest.approx(845.3)

    def test_game_mode_parsed(self):
        assert _parse_snapshot(_ALL_GAME_DATA).game_mode == "CLASSIC"


# ---------------------------------------------------------------------------
# GameSnapshot helper methods
# ---------------------------------------------------------------------------

class TestGameSnapshotHelpers:
    def setup_method(self):
        self.snapshot = _parse_snapshot(_ALL_GAME_DATA)

    def test_ally_roles_keys(self):
        assert set(self.snapshot.ally_roles().keys()) == {"top", "jungle", "mid", "bot", "support"}

    def test_ally_roles_champions(self):
        roles = self.snapshot.ally_roles()
        assert roles["top"] == "Riven"
        assert roles["mid"] == "Zed"

    def test_enemy_roles_champions(self):
        roles = self.snapshot.enemy_roles()
        assert roles["top"] == "Gangplank"
        assert roles["mid"] == "Orianna"

    def test_cs_diff_positive_when_ally_ahead(self):
        # Riven 87 vs Gangplank 70 → +17
        assert self.snapshot.cs_diffs()["top"] == 17

    def test_cs_diff_only_gank_lanes(self):
        assert set(self.snapshot.cs_diffs().keys()) == {"top", "mid", "bot"}

    def test_kill_pressure_top_true(self):
        # Riven: kills=3, deaths=0 → kill_lead=3 ≥ 2 → True
        assert self.snapshot.kill_pressure()["top"] is True

    def test_kill_pressure_bot_false(self):
        # Jinx: kills=1, deaths=2, level=7, no ignite → behind, ult but losing → False
        assert self.snapshot.kill_pressure()["bot"] is False

    def test_kill_pressure_returns_all_gank_lanes(self):
        assert set(self.snapshot.kill_pressure().keys()) == {"top", "mid", "bot"}


# ---------------------------------------------------------------------------
# get_snapshot — mocked HTTP layer
# ---------------------------------------------------------------------------

class TestGetSnapshot:
    @patch("capture.live_client.httpx.Client")
    def test_returns_snapshot_on_200(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = _ALL_GAME_DATA
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
        assert isinstance(get_snapshot(), GameSnapshot)

    @patch("capture.live_client.httpx.Client")
    def test_returns_none_on_non_200(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
        assert get_snapshot() is None

    @patch("capture.live_client.httpx.Client")
    def test_returns_none_on_connection_error(self, mock_client_cls):
        mock_client_cls.return_value.__enter__.return_value.get.side_effect = (
            Exception("Connection refused")
        )
        assert get_snapshot() is None


# ---------------------------------------------------------------------------
# Dead-laner parsing
# ---------------------------------------------------------------------------

class TestDeadPlayerParsing:
    def test_alive_player_is_dead_false(self):
        raw = _make_player("X", "Riven", "ORDER", "TOP", is_dead=False)
        result = _parse_player(raw)
        assert result.is_dead is False
        assert result.respawn_timer == 0.0

    def test_dead_player_is_dead_true(self):
        raw = _make_player("X", "Riven", "ORDER", "TOP", is_dead=True, respawn_timer=12.5)
        result = _parse_player(raw)
        assert result.is_dead is True
        assert result.respawn_timer == pytest.approx(12.5)

    def test_missing_is_dead_defaults_false(self):
        raw = _make_player("X", "Riven", "ORDER", "TOP")
        del raw["isDead"]
        result = _parse_player(raw)
        assert result.is_dead is False

    def test_missing_respawn_timer_defaults_zero(self):
        raw = _make_player("X", "Riven", "ORDER", "TOP")
        del raw["respawnTimer"]
        result = _parse_player(raw)
        assert result.respawn_timer == 0.0


# ---------------------------------------------------------------------------
# enemy_has_flash() / level_diffs() / dead_laners()
# ---------------------------------------------------------------------------

def _snapshot_with_overrides(
    ally_overrides: dict | None = None,
    enemy_overrides: dict | None = None,
) -> GameSnapshot:
    """Build a snapshot with specific per-role overrides for live-signal tests."""
    ally_base = {
        "top":     _make_player("A1", "Riven",   "ORDER", "TOP",     level=8),
        "jungle":  _make_player("A2", "Vi",      "ORDER", "JUNGLE",  level=7),
        "mid":     _make_player("A3", "Zed",     "ORDER", "MIDDLE",  level=7),
        "bot":     _make_player("A4", "Jinx",    "ORDER", "BOTTOM",  level=6),
        "support": _make_player("A5", "Thresh",  "ORDER", "UTILITY", level=5),
    }
    enemy_base = {
        "top":     _make_player("E1", "Gangplank", "CHAOS", "TOP",     level=7),
        "jungle":  _make_player("E2", "Graves",    "CHAOS", "JUNGLE",  level=7),
        "mid":     _make_player("E3", "Orianna",   "CHAOS", "MIDDLE",  level=6),
        "bot":     _make_player("E4", "Caitlyn",   "CHAOS", "BOTTOM",  level=6),
        "support": _make_player("E5", "Lulu",      "CHAOS", "UTILITY", level=4),
    }
    for role, overrides in (ally_overrides or {}).items():
        ally_base[role].update(overrides)
    for role, overrides in (enemy_overrides or {}).items():
        enemy_base[role].update(overrides)

    data = {
        "activePlayer": {"summonerName": "A1"},
        "allPlayers": list(ally_base.values()) + list(enemy_base.values()),
        "gameData": {"gameTime": 600.0, "gameMode": "CLASSIC"},
    }
    return _parse_snapshot(data)


class TestEnemyHasFlash:
    def test_enemy_with_flash_is_true(self):
        snap = _snapshot_with_overrides()
        # All enemies have SummonerFlash by default
        assert snap.enemy_has_flash()["top"] is True
        assert snap.enemy_has_flash()["mid"] is True

    def test_enemy_without_flash_is_false(self):
        snap = _snapshot_with_overrides(
            enemy_overrides={"top": {"summonerSpells": {
                "summonerSpellOne": {"rawDisplayName": "SummonerTeleport"},
                "summonerSpellTwo": {"rawDisplayName": "SummonerDot"},
            }}}
        )
        assert snap.enemy_has_flash()["top"] is False

    def test_only_gank_lanes_returned(self):
        snap = _snapshot_with_overrides()
        assert set(snap.enemy_has_flash().keys()) == {"top", "mid", "bot"}


class TestLevelDiffs:
    def test_ally_ahead_positive_diff(self):
        # A1 (Riven) level=8, E1 (Gangplank) level=7 → +1
        snap = _snapshot_with_overrides()
        assert snap.level_diffs()["top"] == 1

    def test_ally_behind_negative_diff(self):
        # A4 (Jinx) level=6, E4 (Caitlyn) level=6 → 0
        snap = _snapshot_with_overrides()
        assert snap.level_diffs()["bot"] == 0

    def test_large_level_lead(self):
        snap = _snapshot_with_overrides(
            enemy_overrides={"mid": {"level": 3}}
        )
        # A3 (Zed) level=7, E3 level=3 → +4
        assert snap.level_diffs()["mid"] == 4

    def test_only_gank_lanes_returned(self):
        snap = _snapshot_with_overrides()
        assert set(snap.level_diffs().keys()) == {"top", "mid", "bot"}


class TestDeadLaners:
    def test_all_alive_returns_false_pairs(self):
        snap = _snapshot_with_overrides()
        for role in ("top", "mid", "bot"):
            ally_dead, enemy_dead = snap.dead_laners()[role]
            assert ally_dead is False
            assert enemy_dead is False

    def test_enemy_dead_with_enough_timer(self):
        snap = _snapshot_with_overrides(
            enemy_overrides={"top": {"isDead": True, "respawnTimer": 10.0}}
        )
        _, enemy_dead = snap.dead_laners()["top"]
        assert enemy_dead is True

    def test_enemy_dead_but_timer_too_short(self):
        # Timer ≤ 5s — not exploitable
        snap = _snapshot_with_overrides(
            enemy_overrides={"top": {"isDead": True, "respawnTimer": 3.0}}
        )
        _, enemy_dead = snap.dead_laners()["top"]
        assert enemy_dead is False

    def test_ally_dead_detected(self):
        snap = _snapshot_with_overrides(
            ally_overrides={"mid": {"isDead": True, "respawnTimer": 8.0}}
        )
        ally_dead, _ = snap.dead_laners()["mid"]
        assert ally_dead is True

    def test_only_gank_lanes_returned(self):
        snap = _snapshot_with_overrides()
        assert set(snap.dead_laners().keys()) == {"top", "mid", "bot"}


# ---------------------------------------------------------------------------
# compute_objective_timers
# ---------------------------------------------------------------------------

class TestComputeObjectiveTimers:
    def test_dragon_up_at_first_spawn(self):
        timers = compute_objective_timers([], game_time_s=5 * 60)
        assert timers.dragon_up is True

    def test_dragon_not_up_before_first_spawn(self):
        timers = compute_objective_timers([], game_time_s=4 * 60 + 59)
        assert timers.dragon_up is False
        assert timers.dragon_spawns_at == pytest.approx(5 * 60)

    def test_dragon_not_up_after_kill_during_respawn(self):
        # Dragon killed at 5:00, respawn at 10:00; current time is 9:59
        events = [{"EventName": "DragonKill", "EventTime": 5 * 60}]
        timers = compute_objective_timers(events, game_time_s=9 * 60 + 59)
        assert timers.dragon_up is False

    def test_dragon_up_after_respawn_window(self):
        events = [{"EventName": "DragonKill", "EventTime": 5 * 60}]
        timers = compute_objective_timers(events, game_time_s=10 * 60)
        assert timers.dragon_up is True

    def test_baron_not_up_before_20_minutes(self):
        timers = compute_objective_timers([], game_time_s=19 * 60)
        assert timers.baron_up is False

    def test_baron_up_at_20_minutes(self):
        timers = compute_objective_timers([], game_time_s=20 * 60)
        assert timers.baron_up is True

    def test_baron_respawn_after_kill(self):
        events = [{"EventName": "BaronKill", "EventTime": 20 * 60}]
        timers = compute_objective_timers(events, game_time_s=25 * 60 + 59)
        assert timers.baron_up is False

    def test_baron_up_after_kill_respawn(self):
        events = [{"EventName": "BaronKill", "EventTime": 20 * 60}]
        timers = compute_objective_timers(events, game_time_s=26 * 60)
        assert timers.baron_up is True

    def test_herald_available_between_8_and_20_minutes(self):
        timers = compute_objective_timers([], game_time_s=10 * 60)
        assert timers.herald_available is True

    def test_herald_not_available_before_8_minutes(self):
        timers = compute_objective_timers([], game_time_s=7 * 60 + 59)
        assert timers.herald_available is False

    def test_herald_not_available_after_20_minutes(self):
        timers = compute_objective_timers([], game_time_s=20 * 60)
        assert timers.herald_available is False

    def test_herald_gone_after_two_kills(self):
        events = [
            {"EventName": "HeraldKill", "EventTime": 8 * 60},
            {"EventName": "HeraldKill", "EventTime": 12 * 60},
        ]
        timers = compute_objective_timers(events, game_time_s=14 * 60)
        assert timers.herald_available is False

    def test_dragon_alert_shown_within_90s(self):
        # Dragon spawns at 5:00, current time 4:00 → 60s away → should show
        timers = compute_objective_timers([], game_time_s=4 * 60)
        assert "Dragon in" in timers.next_objective_alert

    def test_baron_up_alert(self):
        timers = compute_objective_timers([], game_time_s=20 * 60)
        assert "Baron UP" in timers.next_objective_alert

    def test_dragon_up_alert(self):
        timers = compute_objective_timers([], game_time_s=5 * 60)
        assert "Dragon UP" in timers.next_objective_alert

    def test_herald_available_alert(self):
        timers = compute_objective_timers([], game_time_s=10 * 60)
        assert "Herald available" in timers.next_objective_alert


# ---------------------------------------------------------------------------
# get_events — mocked HTTP layer
# ---------------------------------------------------------------------------

class TestGetEvents:
    @patch("capture.live_client.httpx.Client")
    def test_returns_events_on_200(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"Events": [{"EventName": "DragonKill", "EventTime": 300}]}
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
        events = get_events()
        assert len(events) == 1
        assert events[0]["EventName"] == "DragonKill"

    @patch("capture.live_client.httpx.Client")
    def test_returns_empty_on_non_200(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
        assert get_events() == []

    @patch("capture.live_client.httpx.Client")
    def test_returns_empty_on_connection_error(self, mock_client_cls):
        mock_client_cls.return_value.__enter__.return_value.get.side_effect = (
            Exception("Connection refused")
        )
        assert get_events() == []

    @patch("capture.live_client.httpx.Client")
    def test_returns_empty_list_when_events_key_missing(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
        assert get_events() == []
