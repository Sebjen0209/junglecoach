"""Tests for analysis/postgame/coach.py — Claude coaching feedback."""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from analysis.postgame.coach import (
    _build_event_list,
    _build_prompt,
    _parse_response,
    get_coaching_feedback,
)
from analysis.postgame.events import GankEvent, ObjectiveEvent, PathingIssue
from models import CoachingMoment


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _gank(ts_ms: int, lane: str = "mid", kill: bool = True) -> GankEvent:
    return GankEvent(
        timestamp_ms=ts_ms,
        timestamp_str=f"{ts_ms // 60_000:02d}:00",
        lane=lane,
        outcome="kill" if kill else "assist",
        position_x=7000,
        position_y=7000,
        was_jungler_killer=kill,
    )


def _objective(ts_ms: int, monster: str = "DRAGON", ally: bool = True) -> ObjectiveEvent:
    return ObjectiveEvent(
        timestamp_ms=ts_ms,
        timestamp_str=f"{ts_ms // 60_000:02d}:00",
        objective_type=monster,
        secured_by_ally=ally,
        jungler_distance_from_pit=0,
        was_near_pit=True,
        had_vision_before=True,
        is_first_spawn=True,
    )


def _pathing(minute: int, issue: str = "idle") -> PathingIssue:
    return PathingIssue(
        minute=minute,
        timestamp_str=f"{minute:02d}:00",
        x=500,
        y=500,
        issue=issue,
    )


def _claude_json(events: list[dict]) -> str:
    return json.dumps([
        {
            "index": e["index"],
            "timestamp": e["timestamp"],
            "what_happened": "Something happened.",
            "was_good_decision": True,
            "reasoning": "The jungler made a reasonable play.",
            "suggestion": None,
        }
        for e in events
    ])


# ---------------------------------------------------------------------------
# _build_event_list
# ---------------------------------------------------------------------------

class TestBuildEventList:
    def test_gank_type_included(self):
        events = _build_event_list([_gank(90_000)], [], [], "Vi")
        assert any(e["type"] == "gank" for e in events)

    def test_objective_type_included(self):
        events = _build_event_list([], [_objective(5 * 60_000)], [], "Vi")
        assert any(e["type"] == "objective" for e in events)

    def test_pathing_type_included(self):
        events = _build_event_list([], [], [_pathing(3)], "Vi")
        assert any(e["type"] == "pathing" for e in events)

    def test_sorted_by_timestamp(self):
        events = _build_event_list(
            [_gank(10 * 60_000)],
            [_objective(5 * 60_000)],
            [],
            "Vi",
        )
        assert events[0]["timestamp"] < events[1]["timestamp"]

    def test_all_events_have_index(self):
        events = _build_event_list([_gank(90_000), _gank(120_000)], [_objective(5 * 60_000)], [], "Vi")
        assert all("index" in e for e in events)

    def test_all_events_have_timestamp(self):
        events = _build_event_list([_gank(90_000)], [], [_pathing(2)], "Vi")
        assert all("timestamp" in e for e in events)

    def test_empty_returns_empty(self):
        assert _build_event_list([], [], [], "Vi") == []

    def test_gank_kill_description_contains_lane(self):
        events = _build_event_list([_gank(90_000, lane="top", kill=True)], [], [], "Vi")
        gank = next(e for e in events if e["type"] == "gank")
        assert "top" in gank["description"]
        assert "got the kill" in gank["description"]

    def test_gank_assist_description(self):
        events = _build_event_list([_gank(90_000, kill=False)], [], [], "Vi")
        gank = next(e for e in events if e["type"] == "gank")
        assert "Vi assisted" in gank["description"]

    def test_jungle_top_gank_location_description(self):
        events = _build_event_list([_gank(90_000, lane="jungle/top", kill=True)], [], [], "Vi")
        gank = next(e for e in events if e["type"] == "gank")
        assert "top side jungle" in gank["description"]

    def test_objective_jungler_solo_kill_description(self):
        obj = ObjectiveEvent(
            timestamp_ms=5 * 60_000,
            timestamp_str="05:00",
            objective_type="DRAGON",
            secured_by_ally=True,
            jungler_distance_from_pit=0,
            was_near_pit=True,
            had_vision_before=True,
            is_first_spawn=True,
            jungler_killed_objective=True,
        )
        events = _build_event_list([], [obj], [], "Vi")
        desc = next(e for e in events if e["type"] == "objective")["description"]
        assert "solo kill" in desc
        assert "jungler" in desc.lower()

    def test_objective_trade_description_ally_secured(self):
        obj = ObjectiveEvent(
            timestamp_ms=8 * 60_000,
            timestamp_str="08:00",
            objective_type="DRAGON",
            secured_by_ally=True,
            jungler_distance_from_pit=0,
            was_near_pit=True,
            had_vision_before=True,
            is_first_spawn=False,
            is_trade=True,
            trade_with="RIFTHERALD",
        )
        events = _build_event_list([], [obj], [], "Vi")
        desc = next(e for e in events if e["type"] == "objective")["description"]
        assert "objective trade" in desc
        assert "Rift Herald" in desc

    def test_objective_available_for_trade_description(self):
        obj = ObjectiveEvent(
            timestamp_ms=8 * 60_000,
            timestamp_str="08:00",
            objective_type="DRAGON",
            secured_by_ally=False,
            jungler_distance_from_pit=3000,
            was_near_pit=False,
            had_vision_before=False,
            is_first_spawn=False,
            available_for_trade=["Rift Herald"],
        )
        events = _build_event_list([], [obj], [], "Vi")
        desc = next(e for e in events if e["type"] == "objective")["description"]
        assert "Alternative objectives" in desc
        assert "Rift Herald" in desc

    def test_pathing_in_base_description(self):
        events = _build_event_list([], [], [_pathing(3, issue="in_base")], "Vi")
        pathing = next(e for e in events if e["type"] == "pathing")
        assert "sitting in base" in pathing["description"]

    def test_pathing_idle_description(self):
        events = _build_event_list([], [], [_pathing(3, issue="idle")], "Vi")
        pathing = next(e for e in events if e["type"] == "pathing")
        assert "idle" in pathing["description"].lower() or "less than" in pathing["description"]

    def test_objective_description_mentions_name(self):
        events = _build_event_list([], [_objective(5 * 60_000, "DRAGON")], [], "Vi")
        obj = next(e for e in events if e["type"] == "objective")
        assert "Dragon" in obj["description"]

    def test_objective_description_first_spawn(self):
        events = _build_event_list([], [_objective(5 * 60_000)], [], "Vi")
        obj = next(e for e in events if e["type"] == "objective")
        assert "first spawn" in obj["description"]

    def test_champion_name_in_gank_description(self):
        events = _build_event_list([_gank(90_000)], [], [], "Hecarim")
        gank = next(e for e in events if e["type"] == "gank")
        assert "Hecarim" in gank["description"]


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def test_contains_champion_name(self):
        events = _build_event_list([_gank(90_000)], [], [], "Vi")
        assert "Vi" in _build_prompt(events, "Vi")

    def test_contains_event_count(self):
        events = _build_event_list([_gank(90_000), _gank(120_000)], [], [], "Vi")
        prompt = _build_prompt(events, "Vi")
        assert "2" in prompt

    def test_events_embedded_as_valid_json(self):
        events = _build_event_list([_gank(90_000)], [], [], "Vi")
        prompt = _build_prompt(events, "Vi")
        json_part = prompt.split("Events (JSON):")[1].split("For each event")[0].strip()
        parsed = json.loads(json_part)
        assert isinstance(parsed, list)
        assert len(parsed) == 1

    def test_prompt_specifies_output_keys(self):
        events = _build_event_list([_gank(90_000)], [], [], "Vi")
        prompt = _build_prompt(events, "Vi")
        for key in ("what_happened", "was_good_decision", "reasoning", "suggestion"):
            assert key in prompt


# ---------------------------------------------------------------------------
# _parse_response
# ---------------------------------------------------------------------------

class TestParseResponse:
    def test_valid_response(self):
        raw = json.dumps([{
            "index": 0,
            "timestamp": "01:30",
            "what_happened": "Vi ganked mid.",
            "was_good_decision": True,
            "reasoning": "Good position.",
            "suggestion": None,
        }])
        moments = _parse_response(raw)
        assert len(moments) == 1
        assert isinstance(moments[0], CoachingMoment)

    def test_good_decision_true(self):
        raw = json.dumps([{"index": 0, "timestamp": "01:00", "what_happened": "...",
                           "was_good_decision": True, "reasoning": "...", "suggestion": None}])
        assert _parse_response(raw)[0].was_good_decision is True

    def test_good_decision_false(self):
        raw = json.dumps([{"index": 0, "timestamp": "01:00", "what_happened": "...",
                           "was_good_decision": False, "reasoning": "...", "suggestion": None}])
        assert _parse_response(raw)[0].was_good_decision is False

    def test_suggestion_none(self):
        raw = json.dumps([{"index": 0, "timestamp": "01:00", "what_happened": "...",
                           "was_good_decision": True, "reasoning": "...", "suggestion": None}])
        assert _parse_response(raw)[0].suggestion is None

    def test_suggestion_string(self):
        raw = json.dumps([{"index": 0, "timestamp": "01:00", "what_happened": "...",
                           "was_good_decision": False, "reasoning": "...",
                           "suggestion": "Gank bot instead."}])
        assert _parse_response(raw)[0].suggestion == "Gank bot instead."

    def test_sorted_by_timestamp_str(self):
        raw = json.dumps([
            {"index": 1, "timestamp": "10:00", "what_happened": "...", "was_good_decision": True,
             "reasoning": "...", "suggestion": None},
            {"index": 0, "timestamp": "02:00", "what_happened": "...", "was_good_decision": False,
             "reasoning": "...", "suggestion": None},
        ])
        moments = _parse_response(raw)
        assert moments[0].timestamp_str == "02:00"
        assert moments[1].timestamp_str == "10:00"

    def test_non_json_raises(self):
        with pytest.raises(ValueError, match="non-JSON"):
            _parse_response("not json at all")

    def test_json_object_not_array_raises(self):
        with pytest.raises(ValueError, match="Expected JSON array"):
            _parse_response('{"key": "value"}')

    def test_empty_array_returns_empty(self):
        assert _parse_response("[]") == []


# ---------------------------------------------------------------------------
# get_coaching_feedback (integration, mocked Claude)
# ---------------------------------------------------------------------------

class TestGetCoachingFeedback:
    # anthropic is imported lazily inside get_coaching_feedback() and the function
    # also checks for an API key before using it.  We must patch both sys.modules
    # and analysis.postgame.coach.settings to make the function run in tests.

    _FAKE_MODEL = "claude-sonnet-4-6"

    def _mock_anthropic(self, response_text: str):
        mock_mod = MagicMock()
        mock_client = MagicMock()
        mock_mod.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value.content = [MagicMock(text=response_text)]
        return mock_mod, mock_client

    def _call(self, mock_mod, mock_settings, *args, **kwargs):
        with patch.dict(sys.modules, {"anthropic": mock_mod}), \
             patch("analysis.postgame.coach.settings", mock_settings):
            return get_coaching_feedback(*args, **kwargs)

    def _settings(self, model: str = _FAKE_MODEL):
        s = MagicMock()
        s.anthropic_api_key = "test-key"
        s.ai_model = model
        return s

    def test_returns_coaching_moments(self):
        events_input = _build_event_list([_gank(90_000)], [], [], "Vi")
        mock_mod, _ = self._mock_anthropic(_claude_json(events_input))
        result = self._call(mock_mod, self._settings(), [_gank(90_000)], [], [], "Vi")
        assert len(result) == 1
        assert isinstance(result[0], CoachingMoment)

    def test_empty_events_skips_api(self):
        mock_mod = MagicMock()
        result = self._call(mock_mod, self._settings(), [], [], [], "Vi")
        assert result == []
        mock_mod.Anthropic.return_value.messages.create.assert_not_called()

    def test_api_called_once(self):
        ganks = [_gank(90_000), _gank(120_000)]
        events_input = _build_event_list(ganks, [], [], "Vi")
        mock_mod, mock_client = self._mock_anthropic(_claude_json(events_input))
        self._call(mock_mod, self._settings(), ganks, [], [], "Vi")
        assert mock_client.messages.create.call_count == 1

    def test_api_called_with_configured_model(self):
        events_input = _build_event_list([_gank(90_000)], [], [], "Vi")
        mock_mod, mock_client = self._mock_anthropic(_claude_json(events_input))
        self._call(mock_mod, self._settings(self._FAKE_MODEL), [_gank(90_000)], [], [], "Vi")
        kwargs = mock_client.messages.create.call_args[1]
        assert kwargs["model"] == self._FAKE_MODEL

    def test_multiple_events_all_returned(self):
        ganks = [_gank(90_000, "top"), _gank(120_000, "bot")]
        events_input = _build_event_list(ganks, [], [], "Vi")
        mock_mod, _ = self._mock_anthropic(_claude_json(events_input))
        result = self._call(mock_mod, self._settings(), ganks, [], [], "Vi")
        assert len(result) == 2

    def test_mixed_events_all_types(self):
        ganks = [_gank(90_000)]
        objectives = [_objective(5 * 60_000)]
        pathing = [_pathing(3)]
        events_input = _build_event_list(ganks, objectives, pathing, "Vi")
        mock_mod, _ = self._mock_anthropic(_claude_json(events_input))
        result = self._call(mock_mod, self._settings(), ganks, objectives, pathing, "Vi")
        assert len(result) == 3
