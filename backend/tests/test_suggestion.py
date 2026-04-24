"""Tests for analysis/suggestion.py — orchestration layer."""

from unittest.mock import MagicMock, patch

import pytest

from analysis.ai_client import AIClient
from analysis.suggestion import _fallback_reason, analyse, build_game_state
from capture.live_client import GameSnapshot, PlayerSnapshot
from models import AnalysisResult, GameState, LaneState, ObjectiveTimers


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

# All analyse() tests must patch get_events and compute_objective_timers to
# avoid making HTTP calls to the Riot Live Client API.
_ANALYSE_PATCHES = [
    patch("analysis.suggestion.get_events", return_value=[]),
    patch("analysis.suggestion.compute_objective_timers", return_value=ObjectiveTimers()),
    patch("analysis.suggestion.get_matchup_winrate", return_value=0.55),
    patch("analysis.suggestion.get_phase_strength", return_value=0.7),
]


def _apply_analyse_patches(fn):
    for dec in reversed(_ANALYSE_PATCHES):
        fn = dec(fn)
    return fn


class TestAnalyse:
    @_apply_analyse_patches
    def test_returns_analysis_result(self, *_):
        result = analyse(_snapshot(), _ai_client())
        assert isinstance(result, AnalysisResult)
        assert result.game_detected is True

    @_apply_analyse_patches
    def test_all_three_lanes_in_result(self, *_):
        result = analyse(_snapshot(), _ai_client())
        assert result.lanes is not None
        assert set(result.lanes.keys()) == {"top", "mid", "bot"}

    @_apply_analyse_patches
    def test_each_lane_has_valid_priority(self, *_):
        result = analyse(_snapshot(), _ai_client())
        for lane_name, lane in result.lanes.items():
            assert lane.priority in ("high", "medium", "low"), f"Bad priority on {lane_name}"

    @_apply_analyse_patches
    def test_lane_has_champion_names(self, *_):
        result = analyse(_snapshot(), _ai_client())
        assert result.lanes["top"].ally_champion == "Darius"
        assert result.lanes["top"].enemy_champion == "Garen"

    @_apply_analyse_patches
    def test_lane_reason_from_ai(self, *_):
        ai = _ai_client({"top": "Gank top now.", "mid": "Mid okay.", "bot": "Skip bot."})
        result = analyse(_snapshot(), ai)
        assert result.lanes["top"].reason == "Gank top now."

    @_apply_analyse_patches
    def test_game_minute_in_result(self, *_):
        result = analyse(_snapshot(game_time=600.0), _ai_client())
        assert result.game_minute == 10

    @_apply_analyse_patches
    def test_analysed_at_is_set(self, *_):
        result = analyse(_snapshot(), _ai_client())
        assert result.analysed_at is not None

    @patch("analysis.suggestion.get_matchup_winrate", return_value=0.55)
    @patch("analysis.suggestion.get_phase_strength", return_value=0.7)
    def test_unsupported_mode_returns_no_lanes(self, *_):
        # ARAM exits before get_events is called, so no need to patch it
        ai = _ai_client()
        result = analyse(_snapshot(mode="ARAM"), ai)
        assert result.game_detected is True
        assert result.lanes is None
        ai.get_reasons.assert_not_called()

    @_apply_analyse_patches
    def test_practice_tool_mode_is_supported(self, *_):
        result = analyse(_snapshot(mode="PRACTICETOOL"), _ai_client())
        assert result.lanes is not None

    @_apply_analyse_patches
    def test_ai_failure_falls_back_to_scorer_reasons(self, *_):
        ai = MagicMock(spec=AIClient)
        ai.get_reasons.side_effect = RuntimeError("API down")
        result = analyse(_snapshot(), ai)
        # Result should still work — fallback reasons should mention champions
        assert result.lanes is not None
        for lane_name, lane in result.lanes.items():
            assert lane.ally_champion in lane.reason or lane.enemy_champion in lane.reason

    @_apply_analyse_patches
    def test_lane_score_present(self, *_):
        result = analyse(_snapshot(), _ai_client())
        for lane_name, lane in result.lanes.items():
            assert isinstance(lane.score, float)

    @_apply_analyse_patches
    def test_patch_in_result(self, *_):
        result = analyse(_snapshot(), _ai_client())
        assert result.patch is not None


# ---------------------------------------------------------------------------
# _fallback_reason
# ---------------------------------------------------------------------------

class TestFallbackReason:
    def test_high_priority_mentions_both_champions(self):
        lane = _lane("Darius", "Garen")
        reason = _fallback_reason(lane, "high")
        assert "Darius" in reason
        assert "Garen" in reason

    def test_medium_priority_mentions_both_champions(self):
        lane = _lane("Zed", "Syndra")
        reason = _fallback_reason(lane, "medium")
        assert "Zed" in reason
        assert "Syndra" in reason

    def test_low_priority_mentions_both_champions(self):
        lane = _lane("Jinx", "Caitlyn")
        reason = _fallback_reason(lane, "low")
        assert "Jinx" in reason
        assert "Caitlyn" in reason

    def test_different_text_per_priority(self):
        lane = _lane("Darius", "Garen")
        reasons = {p: _fallback_reason(lane, p) for p in ("high", "medium", "low")}
        assert len(set(reasons.values())) == 3


# ---------------------------------------------------------------------------
# build_game_state — new live signals
# ---------------------------------------------------------------------------

class TestBuildGameStateNewSignals:
    @patch("analysis.suggestion.get_matchup_winrate", return_value=0.55)
    @patch("analysis.suggestion.get_phase_strength", return_value=0.7)
    def test_enemy_flash_false_passed_through(self, *_):
        state = build_game_state(
            ally_roles={"top": "Darius", "mid": "Zed", "bot": "Jinx"},
            enemy_roles={"top": "Garen", "mid": "Syndra", "bot": "Caitlyn"},
            phase="early",
            game_minute=10,
            enemy_flash={"top": False, "mid": True, "bot": True},
        )
        assert state.top.enemy_has_flash is False
        assert state.mid.enemy_has_flash is True

    @patch("analysis.suggestion.get_matchup_winrate", return_value=0.55)
    @patch("analysis.suggestion.get_phase_strength", return_value=0.7)
    def test_level_diffs_passed_through(self, *_):
        state = build_game_state(
            ally_roles={"top": "Darius", "mid": "Zed", "bot": "Jinx"},
            enemy_roles={"top": "Garen", "mid": "Syndra", "bot": "Caitlyn"},
            phase="early",
            game_minute=10,
            level_diffs={"top": 2, "mid": -1, "bot": 0},
        )
        assert state.top.level_diff == 2
        assert state.mid.level_diff == -1

    @patch("analysis.suggestion.get_matchup_winrate", return_value=0.55)
    @patch("analysis.suggestion.get_phase_strength", return_value=0.7)
    def test_dead_laners_passed_through(self, *_):
        state = build_game_state(
            ally_roles={"top": "Darius", "mid": "Zed", "bot": "Jinx"},
            enemy_roles={"top": "Garen", "mid": "Syndra", "bot": "Caitlyn"},
            phase="early",
            game_minute=10,
            dead_laners={"top": (False, True), "mid": (True, False), "bot": (False, False)},
        )
        assert state.top.enemy_is_dead is True
        assert state.top.ally_is_dead is False
        assert state.mid.ally_is_dead is True

    @patch("analysis.suggestion.get_matchup_winrate", return_value=0.55)
    @patch("analysis.suggestion.get_phase_strength", return_value=0.7)
    def test_game_time_seconds_stored(self, *_):
        state = build_game_state(
            ally_roles={"top": "X", "mid": "X", "bot": "X"},
            enemy_roles={"top": "X", "mid": "X", "bot": "X"},
            phase="early",
            game_minute=10,
            game_time_seconds=654.0,
        )
        assert state.game_time_seconds == pytest.approx(654.0)

    @patch("analysis.suggestion.get_matchup_winrate", return_value=0.55)
    @patch("analysis.suggestion.get_phase_strength", return_value=0.7)
    def test_missing_signals_default_safely(self, *_):
        # No live signals passed — all should default to safe values
        state = build_game_state(
            ally_roles={"top": "Darius", "mid": "Zed", "bot": "Jinx"},
            enemy_roles={"top": "Garen", "mid": "Syndra", "bot": "Caitlyn"},
            phase="early",
            game_minute=10,
        )
        assert state.top.enemy_has_flash is True   # default: enemy has flash (conservative)
        assert state.top.level_diff == 0
        assert state.top.ally_is_dead is False
        assert state.top.enemy_is_dead is False


