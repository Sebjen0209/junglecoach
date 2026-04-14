"""Claude API integration for natural language gank suggestions.

Builds the prompt from a GameState, calls the Anthropic API, and parses
the JSON response into per-lane reason strings.

Caching: we skip the API call if the game state hasn't changed meaningfully
since the last call (same champions + phase + no kill/CS changes > threshold).
"""

import json
import logging
import time
from dataclasses import dataclass, field

import anthropic

from config import settings
from models import GameState

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a League of Legends jungle coaching assistant.
You receive structured data about all 3 lanes and must output gank priority advice.
Be concise. Maximum 2 sentences per lane. Focus on WHY, not just the priority.
Output valid JSON only — no markdown, no explanation outside the JSON.\
"""

# Minimum seconds between API calls (even if state changes)
_MIN_CALL_INTERVAL = 45.0

# CS diff must change by at least this much to trigger a re-call
_CS_DIFF_CHANGE_THRESHOLD = 10


@dataclass
class _CacheEntry:
    game_state: GameState
    reasons: dict[str, str]
    timestamp: float = field(default_factory=time.monotonic)


def _build_user_prompt(game_state: GameState) -> str:
    top, mid, bot = game_state.top, game_state.mid, game_state.bot
    return f"""\
Current game state (minute {game_state.game_minute}):

TOP: {top.ally_champion} vs {top.enemy_champion}
  - Matchup win rate for ally: {top.matchup_winrate:.0%}
  - Lane phase power: ally is {top.ally_phase_strength:.1f}/1.0 this phase
  - CS diff: {top.cs_diff:+d}

MID: {mid.ally_champion} vs {mid.enemy_champion}
  - Matchup win rate for ally: {mid.matchup_winrate:.0%}
  - Lane phase power: ally is {mid.ally_phase_strength:.1f}/1.0 this phase
  - CS diff: {mid.cs_diff:+d}

BOT: {bot.ally_champion} vs {bot.enemy_champion}
  - Matchup win rate for ally: {bot.matchup_winrate:.0%}
  - Lane phase power: ally is {bot.ally_phase_strength:.1f}/1.0 this phase
  - CS diff: {bot.cs_diff:+d}

Return JSON in exactly this format:
{{
  "top": {{"priority": "high|medium|low", "reason": "..."}},
  "mid": {{"priority": "high|medium|low", "reason": "..."}},
  "bot": {{"priority": "high|medium|low", "reason": "..."}}
}}\
"""


def _state_changed_enough(old: GameState, new: GameState) -> bool:
    """Return True if the game state has changed enough to warrant a new AI call."""
    if old.game_phase != new.game_phase:
        return True
    for old_lane, new_lane in [
        (old.top, new.top),
        (old.mid, new.mid),
        (old.bot, new.bot),
    ]:
        if old_lane.ally_champion != new_lane.ally_champion:
            return True
        if old_lane.enemy_champion != new_lane.enemy_champion:
            return True
        if abs(old_lane.cs_diff - new_lane.cs_diff) >= _CS_DIFF_CHANGE_THRESHOLD:
            return True
        if old_lane.ally_kill_pressure != new_lane.ally_kill_pressure:
            return True
    return False


class AIClient:
    """Wrapper around the Anthropic client with state-based caching.

    Usage::

        client = AIClient()
        reasons = client.get_reasons(game_state)
        # reasons = {"top": "Riven is strong right now...", "mid": "...", "bot": "..."}
    """

    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._cache: _CacheEntry | None = None

    def get_reasons(self, game_state: GameState) -> dict[str, str]:
        """Return per-lane reason strings, using cache if state hasn't changed.

        Args:
            game_state: Current game state from the capture pipeline.

        Returns:
            Dict with keys 'top', 'mid', 'bot' — each a 1–2 sentence reason string.

        Raises:
            anthropic.APIError: On API failure (caller should handle).
            ValueError: If API returns malformed JSON.
        """
        now = time.monotonic()

        # Return cached result if state unchanged and within time window
        if self._cache is not None:
            elapsed = now - self._cache.timestamp
            if elapsed < _MIN_CALL_INTERVAL:
                if not _state_changed_enough(self._cache.game_state, game_state):
                    logger.debug("Using cached AI reasons (%.0fs old)", elapsed)
                    return self._cache.reasons

        reasons = self._call_api(game_state)
        self._cache = _CacheEntry(game_state=game_state, reasons=reasons)
        return reasons

    def _call_api(self, game_state: GameState) -> dict[str, str]:
        logger.info(
            "Calling Claude API (model=%s, minute=%d)",
            settings.ai_model,
            game_state.game_minute,
        )
        response = self._client.messages.create(
            model=settings.ai_model,
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_user_prompt(game_state)}],
        )
        raw = response.content[0].text
        return _parse_reasons(raw)


def _parse_reasons(raw: str) -> dict[str, str]:
    """Parse the JSON response from Claude into a reason-per-lane dict.

    Raises:
        ValueError: If the JSON is missing required keys or is malformed.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Claude returned non-JSON: {raw!r}") from exc

    reasons: dict[str, str] = {}
    for lane in ("top", "mid", "bot"):
        if lane not in data:
            raise ValueError(f"Missing lane {lane!r} in Claude response: {data}")
        entry = data[lane]
        if "reason" not in entry:
            raise ValueError(f"Missing 'reason' for lane {lane!r}: {entry}")
        reasons[lane] = entry["reason"]

    return reasons
