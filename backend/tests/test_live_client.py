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
