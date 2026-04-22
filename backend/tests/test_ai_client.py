"""Tests for analysis/ai_client.py.

The httpx client is mocked throughout — these tests validate caching logic,
JWT forwarding, and graceful degradation when the cloud API is unreachable.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from analysis.ai_client import AIClient, _state_changed_enough
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


_VALID_CLOUD_RESPONSE = {
    "top": "Riven hard counters Gangplank pre-6.",
    "mid": "Zed can kill Azir at level 6.",
    "bot": "Even lane, spend time elsewhere.",
}


def _mock_httpx_response(data: dict) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


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
# AIClient.get_reasons() — mocked httpx + Railway cloud API
# ---------------------------------------------------------------------------

class TestAIClientGetReasons:
    def test_returns_reason_dict(self):
        client = AIClient()
        with patch("analysis.ai_client.httpx.post", return_value=_mock_httpx_response(_VALID_CLOUD_RESPONSE)):
            with patch("analysis.ai_client.settings") as mock_settings:
                mock_settings.cloud_api_url = "https://example.railway.app"
                reasons = client.get_reasons(_make_game_state(), jwt="fake-jwt")
        assert set(reasons.keys()) == {"top", "mid", "bot"}

    def test_jwt_forwarded_in_header(self):
        client = AIClient()
        with patch("analysis.ai_client.httpx.post", return_value=_mock_httpx_response(_VALID_CLOUD_RESPONSE)) as mock_post:
            with patch("analysis.ai_client.settings") as mock_settings:
                mock_settings.cloud_api_url = "https://example.railway.app"
                client.get_reasons(_make_game_state(), jwt="user-token")
        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer user-token"

    def test_no_jwt_sends_no_auth_header(self):
        client = AIClient()
        with patch("analysis.ai_client.httpx.post", return_value=_mock_httpx_response(_VALID_CLOUD_RESPONSE)) as mock_post:
            with patch("analysis.ai_client.settings") as mock_settings:
                mock_settings.cloud_api_url = "https://example.railway.app"
                client.get_reasons(_make_game_state(), jwt=None)
        _, kwargs = mock_post.call_args
        assert "Authorization" not in kwargs.get("headers", {})

    def test_cache_prevents_second_cloud_call(self):
        client = AIClient()
        gs = _make_game_state()
        with patch("analysis.ai_client.httpx.post", return_value=_mock_httpx_response(_VALID_CLOUD_RESPONSE)) as mock_post:
            with patch("analysis.ai_client.settings") as mock_settings:
                mock_settings.cloud_api_url = "https://example.railway.app"
                client.get_reasons(gs)
                client.get_reasons(gs)  # same state, within cache window
        assert mock_post.call_count == 1

    def test_cache_busted_on_phase_change(self):
        client = AIClient()
        with patch("analysis.ai_client.httpx.post", return_value=_mock_httpx_response(_VALID_CLOUD_RESPONSE)) as mock_post:
            with patch("analysis.ai_client.settings") as mock_settings:
                mock_settings.cloud_api_url = "https://example.railway.app"
                client.get_reasons(_make_game_state(game_phase="early"))
                client.get_reasons(_make_game_state(game_phase="mid"))
        assert mock_post.call_count == 2

    def test_returns_null_reasons_when_cloud_api_unreachable(self):
        client = AIClient()
        with patch("analysis.ai_client.httpx.post", side_effect=Exception("Connection refused")):
            with patch("analysis.ai_client.settings") as mock_settings:
                mock_settings.cloud_api_url = "https://example.railway.app"
                reasons = client.get_reasons(_make_game_state())
        assert reasons == {"top": None, "mid": None, "bot": None}

    def test_returns_null_reasons_when_cloud_api_url_not_set(self):
        client = AIClient()
        with patch("analysis.ai_client.settings") as mock_settings:
            mock_settings.cloud_api_url = ""
            reasons = client.get_reasons(_make_game_state())
        assert reasons == {"top": None, "mid": None, "bot": None}
