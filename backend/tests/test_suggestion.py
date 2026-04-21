"""Tests for analysis/suggestion.py — orchestration layer."""

from unittest.mock import MagicMock, patch

import pytest

from analysis.ai_client import AIClient
from analysis.suggestion import _fallback_reasons, analyse, build_game_state
from capture.live_client import GameSnapshot, PlayerSnapshot
from models import AnalysisResult, GameState, LaneState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _player(
    name: str,
    champion: str,
    team: str,
    position: str,
    kills: int = 0,
    cs: int = 50,
) -> PlayerSnapshot:
    return PlayerSnapshot(
        summoner_name=name,
        champion_name=champion,
        team=team,
        position=position,
        level=6,
        summoner_spells=frozenset(),
        cs=cs,
        kills=kills,
        deaths=0,
        assists=0,
    )


def _snapshot(game_time: float = 600.0, mode: str = "CLASSIC") -> GameSnapshot:
    ally = [
        _player("S1", "Vi",     "ORDER", "jungle"),
        _player("S2", "Darius", "ORDER", "top"),
        _player("S3", "Zed",    "ORDER", "mid"),
        _player("S4", "Jinx",   "ORDER", "bot"),
        _player("S5", "Thresh", "ORDER", "support"),
    ]
    enemy = [
        _player("E1", "Hecarim", "CHAOS", "jungle"),
        _player("E2", "Garen",   "CHAOS", "top"),
        _player("E3", "Syndra",  "CHAOS", "mid"),
        _player("E4", "Caitlyn", "CHAOS", "bot"),
        _player("E5", "Lux",     "CHAOS", "support"),
    ]
    return GameSnapshot(
        ally_team="ORDER",
        ally_players=ally,
        enemy_players=enemy,
        game_time_seconds=game_time,
        game_mode=mode,
    )


def _lane(ally: str = "Darius", enemy: str = "Garen", winrate: float = 0.55) -> LaneState:
    return LaneState(
        ally_champion=ally,
        enemy_champion=enemy,
        matchup_winrate=winrate,
        ally_phase_strength=0.7,
        cs_diff=0,
        ally_kill_pressure=False,
    )


def _game_state() -> GameState:
    return GameState(
        game_minute=10,
        game_phase="early",
        patch="16.8",
        top=_lane("Darius", "Garen"),
        mid=_lane("Zed", "Syndra"),
        bot=_lane("Jinx", "Caitlyn"),
    )


def _ai_client(reasons: dict[str, str] | None = None) -> MagicMock:
    ai = MagicMock(spec=AIClient)
    ai.get_reasons.return_value = reasons or {"top": "Gank top.", "mid": "Gank mid.", "bot": "Gank bot."}
    return ai


# ---------------------------------------------------------------------------
# build_game_state
# ---------------------------------------------------------------------------

class TestBuildGameState:
    @patch("analysis.suggestion.get_matchup_winrate", return_value=0.55)
    @patch("analysis.suggestion.get_phase_strength", return_value=0.7)
    def test_returns_game_state(self, *_):
        state = build_game_state(
            ally_roles={"top": "Darius", "mid": "Zed", "bot": "Jinx"},
            enemy_roles={"top": "Garen", "mid": "Syndra", "bot": "Caitlyn"},
            phase="early",
            game_minute=10,
        )
        assert isinstance(state, GameState)
        assert state.game_phase == "early"
        assert state.game_minute == 10

    @patch("analysis.suggestion.get_matchup_winrate", return_value=0.55)
    @patch("analysis.suggestion.get_phase_strength", return_value=0.7)
    def test_champion_names_populated(self, *_):
        state = build_game_state(
            ally_roles={"top": "Darius", "mid": "Zed", "bot": "Jinx"},
            enemy_roles={"top": "Garen", "mid": "Syndra", "bot": "Caitlyn"},
            phase="early",
            game_minute=10,
        )
        assert state.top.ally_champion == "Darius"
        assert state.top.enemy_champion == "Garen"
        assert state.mid.ally_champion == "Zed"
        assert state.bot.enemy_champion == "Caitlyn"

    @patch("analysis.suggestion.get_matchup_winrate", return_value=0.55)
    @patch("analysis.suggestion.get_phase_strength", return_value=0.7)
    def test_cs_diffs_applied(self, *_):
        state = build_game_state(
            ally_roles={"top": "Darius", "mid": "Zed", "bot": "Jinx"},
            enemy_roles={"top": "Garen", "mid": "Syndra", "bot": "Caitlyn"},
            phase="early",
            game_minute=10,
            cs_diffs={"top": 25, "mid": -10, "bot": 0},
        )
        assert state.top.cs_diff == 25
        assert state.mid.cs_diff == -10
        assert state.bot.cs_diff == 0

    @patch("analysis.suggestion.get_matchup_winrate", return_value=0.55)
    @patch("analysis.suggestion.get_phase_strength", return_value=0.7)
    def test_kill_pressure_applied(self, *_):
        state = build_game_state(
            ally_roles={"top": "Darius", "mid": "Zed", "bot": "Jinx"},
            enemy_roles={"top": "Garen", "mid": "Syndra", "bot": "Caitlyn"},
            phase="early",
            game_minute=10,
            kill_pressure={"top": True, "mid": False, "bot": False},
        )
        assert state.top.ally_kill_pressure is True
        assert state.mid.ally_kill_pressure is False

    @patch("analysis.suggestion.get_matchup_winrate", return_value=None)
    @patch("analysis.suggestion.get_phase_strength", return_value=0.5)
    def test_missing_winrate_defaults_to_50(self, *_):
        state = build_game_state(
            ally_roles={"top": "X", "mid": "X", "bot": "X"},
            enemy_roles={"top": "X", "mid": "X", "bot": "X"},
            phase="early",
            game_minute=5,
        )
        assert state.top.matchup_winrate == 0.50

    @patch("analysis.suggestion.get_matchup_winrate", return_value=0.85)
    @patch("analysis.suggestion.get_phase_strength", return_value=0.9)
    def test_winrate_clamped_at_max(self, *_):
        state = build_game_state(
            ally_roles={"top": "X", "mid": "X", "bot": "X"},
            enemy_roles={"top": "X", "mid": "X", "bot": "X"},
            phase="early",
            game_minute=5,
        )
        assert state.top.matchup_winrate <= 0.70

    @patch("analysis.suggestion.get_matchup_winrate", return_value=0.15)
    @patch("analysis.suggestion.get_phase_strength", return_value=0.3)
    def test_winrate_clamped_at_min(self, *_):
        state = build_game_state(
            ally_roles={"top": "X", "mid": "X", "bot": "X"},
            enemy_roles={"top": "X", "mid": "X", "bot": "X"},
            phase="early",
            game_minute=5,
        )
        assert state.top.matchup_winrate >= 0.30

    @patch("analysis.suggestion.get_matchup_winrate", return_value=0.55)
    @patch("analysis.suggestion.get_phase_strength", return_value=0.7)
    def test_exp_delta_applied(self, *_):
        # A positive exp delta should push winrate above 0.55
        state_no_delta = build_game_state(
            ally_roles={"top": "Darius", "mid": "Zed", "bot": "Jinx"},
            enemy_roles={"top": "Garen", "mid": "Syndra", "bot": "Caitlyn"},
            phase="early",
            game_minute=10,
        )
        state_with_delta = build_game_state(
            ally_roles={"top": "Darius", "mid": "Zed", "bot": "Jinx"},
            enemy_roles={"top": "Garen", "mid": "Syndra", "bot": "Caitlyn"},
            phase="early",
            game_minute=10,
            exp_deltas={"top": 0.05, "mid": 0.0, "bot": -0.05},
        )
        assert state_with_delta.top.matchup_winrate > state_no_delta.top.matchup_winrate
        assert state_with_delta.bot.matchup_winrate < state_no_delta.bot.matchup_winrate


# ---------------------------------------------------------------------------
# analyse
# ---------------------------------------------------------------------------

class TestAnalyse:
    @patch("analysis.suggestion.get_matchup_winrate", return_value=0.55)
    @patch("analysis.suggestion.get_phase_strength", return_value=0.7)
    def test_returns_analysis_result(self, *_):
        result = analyse(_snapshot(), _ai_client())
        assert isinstance(result, AnalysisResult)
        assert result.game_detected is True

    @patch("analysis.suggestion.get_matchup_winrate", return_value=0.55)
    @patch("analysis.suggestion.get_phase_strength", return_value=0.7)
    def test_all_three_lanes_in_result(self, *_):
        result = analyse(_snapshot(), _ai_client())
        assert result.lanes is not None
        assert set(result.lanes.keys()) == {"top", "mid", "bot"}

    @patch("analysis.suggestion.get_matchup_winrate", return_value=0.55)
    @patch("analysis.suggestion.get_phase_strength", return_value=0.7)
    def test_each_lane_has_valid_priority(self, *_):
        result = analyse(_snapshot(), _ai_client())
        for lane_name, lane in result.lanes.items():
            assert lane.priority in ("high", "medium", "low"), f"Bad priority on {lane_name}"

    @patch("analysis.suggestion.get_matchup_winrate", return_value=0.55)
    @patch("analysis.suggestion.get_phase_strength", return_value=0.7)
    def test_lane_has_champion_names(self, *_):
        result = analyse(_snapshot(), _ai_client())
        assert result.lanes["top"].ally_champion == "Darius"
        assert result.lanes["top"].enemy_champion == "Garen"

    @patch("analysis.suggestion.get_matchup_winrate", return_value=0.55)
    @patch("analysis.suggestion.get_phase_strength", return_value=0.7)
    def test_lane_reason_from_ai(self, *_):
        ai = _ai_client({"top": "Gank top now.", "mid": "Mid okay.", "bot": "Skip bot."})
        result = analyse(_snapshot(), ai)
        assert result.lanes["top"].reason == "Gank top now."

    @patch("analysis.suggestion.get_matchup_winrate", return_value=0.55)
    @patch("analysis.suggestion.get_phase_strength", return_value=0.7)
    def test_game_minute_in_result(self, *_):
        result = analyse(_snapshot(game_time=600.0), _ai_client())
        assert result.game_minute == 10

    @patch("analysis.suggestion.get_matchup_winrate", return_value=0.55)
    @patch("analysis.suggestion.get_phase_strength", return_value=0.7)
    def test_analysed_at_is_set(self, *_):
        result = analyse(_snapshot(), _ai_client())
        assert result.analysed_at is not None

    @patch("analysis.suggestion.get_matchup_winrate", return_value=0.55)
    @patch("analysis.suggestion.get_phase_strength", return_value=0.7)
    def test_unsupported_mode_returns_no_lanes(self, *_):
        ai = _ai_client()
        result = analyse(_snapshot(mode="ARAM"), ai)
        assert result.game_detected is True
        assert result.lanes is None
        ai.get_reasons.assert_not_called()

    @patch("analysis.suggestion.get_matchup_winrate", return_value=0.55)
    @patch("analysis.suggestion.get_phase_strength", return_value=0.7)
    def test_practice_tool_mode_is_supported(self, *_):
        result = analyse(_snapshot(mode="PRACTICETOOL"), _ai_client())
        assert result.lanes is not None

    @patch("analysis.suggestion.get_matchup_winrate", return_value=0.55)
    @patch("analysis.suggestion.get_phase_strength", return_value=0.7)
    def test_ai_failure_falls_back_to_scorer_reasons(self, *_):
        ai = MagicMock(spec=AIClient)
        ai.get_reasons.side_effect = RuntimeError("API down")
        result = analyse(_snapshot(), ai)
        # Result should still work — fallback reasons should mention champions
        assert result.lanes is not None
        for lane_name, lane in result.lanes.items():
            assert lane.ally_champion in lane.reason or lane.enemy_champion in lane.reason

    @patch("analysis.suggestion.get_matchup_winrate", return_value=0.55)
    @patch("analysis.suggestion.get_phase_strength", return_value=0.7)
    def test_lane_score_present(self, *_):
        result = analyse(_snapshot(), _ai_client())
        for lane_name, lane in result.lanes.items():
            assert isinstance(lane.score, float)

    @patch("analysis.suggestion.get_matchup_winrate", return_value=0.55)
    @patch("analysis.suggestion.get_phase_strength", return_value=0.7)
    def test_patch_in_result(self, *_):
        result = analyse(_snapshot(), _ai_client())
        assert result.patch is not None


# ---------------------------------------------------------------------------
# _fallback_reasons
# ---------------------------------------------------------------------------

class TestFallbackReasons:
    def test_all_three_lanes_covered(self):
        gs = _game_state()
        lane_scores = {"top": (30.0, "medium"), "mid": (10.0, "low"), "bot": (50.0, "high")}
        reasons = _fallback_reasons(gs, lane_scores)
        assert set(reasons.keys()) == {"top", "mid", "bot"}

    def test_ally_champion_in_reason(self):
        gs = _game_state()
        lane_scores = {"top": (30.0, "medium"), "mid": (10.0, "low"), "bot": (50.0, "high")}
        reasons = _fallback_reasons(gs, lane_scores)
        assert "Darius" in reasons["top"]

    def test_enemy_champion_in_reason(self):
        gs = _game_state()
        lane_scores = {"top": (30.0, "medium"), "mid": (10.0, "low"), "bot": (50.0, "high")}
        reasons = _fallback_reasons(gs, lane_scores)
        assert "Garen" in reasons["top"]

    def test_winrate_percentage_in_reason(self):
        gs = _game_state()
        lane_scores = {"top": (30.0, "medium"), "mid": (10.0, "low"), "bot": (50.0, "high")}
        reasons = _fallback_reasons(gs, lane_scores)
        assert "55%" in reasons["top"]

    def test_all_reasons_are_strings(self):
        gs = _game_state()
        lane_scores = {"top": (30.0, "medium"), "mid": (10.0, "low"), "bot": (50.0, "high")}
        reasons = _fallback_reasons(gs, lane_scores)
        for lane_name, reason in reasons.items():
            assert isinstance(reason, str), f"Reason for {lane_name} is not a string"
