"""Tests for analysis/ai_client.py.

The Anthropic client is mocked throughout — these tests validate prompt
building, JSON parsing, caching logic, and error handling.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from analysis.ai_client import AIClient, _build_user_prompt, _parse_reasons, _state_changed_enough
from models import GameState, LaneState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_lane(
    ally="Riven", enemy="Gangplank", winrate=0.58,
    phase_strength=0.8, cs_diff=0, kill_pressure=False,
) -> LaneState:
    return LaneState(
        ally_champion=ally, enemy_champion=enemy,
        matchup_winrate=winrate, ally_phase_strength=phase_strength,
        cs_diff=cs_diff, ally_kill_pressure=kill_pressure,
    )


def _make_game_state(**overrides) -> GameState:
    defaults = dict(
        game_minute=12,
        game_phase="early",
        patch="14.6",
        top=_make_lane("Riven", "Gangplank"),
        mid=_make_lane("Zed", "Azir", winrate=0.54),
        bot=_make_lane("Jinx", "Caitlyn", winrate=0.50),
    )
    defaults.update(overrides)
    return GameState(**defaults)


_VALID_AI_RESPONSE = """\
{
  "top": {"priority": "high", "reason": "Riven hard counters Gangplank pre-6."},
  "mid": {"priority": "medium", "reason": "Zed can kill Azir at level 6."},
  "bot": {"priority": "low", "reason": "Even lane, spend time elsewhere."}
}"""


# ---------------------------------------------------------------------------
# _build_user_prompt()
# ---------------------------------------------------------------------------

class TestBuildUserPrompt:
    def test_contains_all_three_lanes(self):
        gs = _make_game_state()
        prompt = _build_user_prompt(gs)
        assert "TOP:" in prompt
        assert "MID:" in prompt
        assert "BOT:" in prompt

    def test_contains_champion_names(self):
        gs = _make_game_state()
        prompt = _build_user_prompt(gs)
        assert "Riven" in prompt
        assert "Gangplank" in prompt

    def test_contains_game_minute(self):
        gs = _make_game_state(game_minute=17)
        prompt = _build_user_prompt(gs)
        assert "17" in prompt

    def test_contains_winrate_percentage(self):
        gs = _make_game_state()
        prompt = _build_user_prompt(gs)
        assert "58%" in prompt


# ---------------------------------------------------------------------------
# _parse_reasons()
# ---------------------------------------------------------------------------

class TestParseReasons:
    def test_valid_response_parsed_correctly(self):
        reasons = _parse_reasons(_VALID_AI_RESPONSE)
        assert reasons["top"] == "Riven hard counters Gangplank pre-6."
        assert reasons["mid"] == "Zed can kill Azir at level 6."
        assert reasons["bot"] == "Even lane, spend time elsewhere."

    def test_missing_lane_raises(self):
        partial = '{"top": {"priority": "high", "reason": "ok"}, "mid": {"priority": "low", "reason": "ok"}}'
        with pytest.raises(ValueError, match="Missing lane"):
            _parse_reasons(partial)

    def test_missing_reason_key_raises(self):
        bad = '{"top": {"priority": "high"}, "mid": {"priority": "low", "reason": "ok"}, "bot": {"priority": "low", "reason": "ok"}}'
        with pytest.raises(ValueError, match="Missing 'reason'"):
            _parse_reasons(bad)

    def test_non_json_raises(self):
        with pytest.raises(ValueError, match="non-JSON"):
            _parse_reasons("Sorry, I cannot help with that.")


# ---------------------------------------------------------------------------
# _state_changed_enough()
# ---------------------------------------------------------------------------

class TestStateChangedEnough:
    def test_identical_states_not_changed(self):
        gs = _make_game_state()
        assert _state_changed_enough(gs, gs) is False

    def test_phase_change_triggers(self):
        old = _make_game_state(game_phase="early")
        new = _make_game_state(game_phase="mid")
        assert _state_changed_enough(old, new) is True

    def test_champion_swap_triggers(self):
        old = _make_game_state(top=_make_lane("Riven", "Gangplank"))
        new = _make_game_state(top=_make_lane("Darius", "Gangplank"))
        assert _state_changed_enough(old, new) is True

    def test_small_cs_change_ignored(self):
        old = _make_game_state(top=_make_lane(cs_diff=0))
        new = _make_game_state(top=_make_lane(cs_diff=5))
        assert _state_changed_enough(old, new) is False

    def test_large_cs_change_triggers(self):
        old = _make_game_state(top=_make_lane(cs_diff=0))
        new = _make_game_state(top=_make_lane(cs_diff=15))
        assert _state_changed_enough(old, new) is True

    def test_kill_pressure_change_triggers(self):
        old = _make_game_state(top=_make_lane(kill_pressure=False))
        new = _make_game_state(top=_make_lane(kill_pressure=True))
        assert _state_changed_enough(old, new) is True


# ---------------------------------------------------------------------------
# AIClient.get_reasons() — mocked Anthropic client
# ---------------------------------------------------------------------------

def _mock_anthropic_response(text: str) -> MagicMock:
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    return response


class TestAIClientGetReasons:
    def _make_client(self) -> AIClient:
        with patch("analysis.ai_client.anthropic.Anthropic"):
            client = AIClient()
        return client

    def test_returns_reason_dict(self):
        client = self._make_client()
        client._client.messages.create.return_value = _mock_anthropic_response(_VALID_AI_RESPONSE)
        reasons = client.get_reasons(_make_game_state())
        assert set(reasons.keys()) == {"top", "mid", "bot"}

    def test_api_called_once_on_first_call(self):
        client = self._make_client()
        client._client.messages.create.return_value = _mock_anthropic_response(_VALID_AI_RESPONSE)
        client.get_reasons(_make_game_state())
        assert client._client.messages.create.call_count == 1

    def test_cache_prevents_second_api_call(self):
        client = self._make_client()
        client._client.messages.create.return_value = _mock_anthropic_response(_VALID_AI_RESPONSE)
        gs = _make_game_state()
        client.get_reasons(gs)
        client.get_reasons(gs)  # same state, within cache window
        assert client._client.messages.create.call_count == 1

    def test_cache_busted_on_phase_change(self):
        client = self._make_client()
        client._client.messages.create.return_value = _mock_anthropic_response(_VALID_AI_RESPONSE)
        client.get_reasons(_make_game_state(game_phase="early"))
        client.get_reasons(_make_game_state(game_phase="mid"))
        assert client._client.messages.create.call_count == 2
