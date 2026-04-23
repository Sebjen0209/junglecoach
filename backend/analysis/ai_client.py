"""Cloud API client for natural language gank reasoning.

POSTs the GameState to the Railway cloud API which holds the Anthropic key
and performs the Claude call. The key never touches the user's machine.

Free users receive None reasons (no Claude call is made server-side).
Premium/Pro users receive full reasoning strings.

Caching: we skip the API call if the game state hasn't changed meaningfully
since the last call (same champions + phase + no kill/CS changes > threshold).
"""

import logging
import time
from dataclasses import dataclass, field

import httpx

from config import settings
from models import GameState, MacroHint

logger = logging.getLogger(__name__)

# Minimum seconds between cloud API calls (even if state changes)
_MIN_CALL_INTERVAL = 45.0

# Macro hints: minimum interval between calls. State-key changes (tower fall,
# dragon kill) always bust the cache regardless of this interval.
_MACRO_MIN_CALL_INTERVAL = 60.0

# CS diff must change by at least this much to trigger a re-call
_CS_DIFF_CHANGE_THRESHOLD = 10

# How long to wait for Railway to respond
_TIMEOUT = 10.0


@dataclass
class _CacheEntry:
    game_state: GameState
    reasons: dict[str, str | None]
    timestamp: float = field(default_factory=time.monotonic)


@dataclass
class _MacroCacheEntry:
    state_key: str
    hints: list[MacroHint]
    timestamp: float = field(default_factory=time.monotonic)


def _state_changed_enough(old: GameState, new: GameState) -> bool:
    """Return True if the game state has changed enough to warrant a new cloud call."""
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
    """Fetches AI reasoning from the cloud API with state-based caching.

    Usage::

        client = AIClient()
        reasons = client.get_reasons(game_state, jwt=user_token)
        # reasons = {"top": "Riven is strong right now...", "mid": None, "bot": "..."}
        # None means free tier or cloud API unreachable — overlay shows upgrade prompt.
    """

    def __init__(self) -> None:
        self._cache: _CacheEntry | None = None
        self._macro_cache: _MacroCacheEntry | None = None

    def get_reasons(
        self,
        game_state: GameState,
        jwt: str | None = None,
    ) -> dict[str, str | None]:
        """Return per-lane reason strings, using cache if state hasn't changed.

        Args:
            game_state: Current game state from the capture pipeline.
            jwt:        User's Supabase access token, forwarded to Railway for
                        subscription checking. None falls back to free tier.

        Returns:
            Dict with keys 'top', 'mid', 'bot'.
            Values are reason strings for premium users, None for free users
            or when the cloud API is unreachable.
        """
        now = time.monotonic()

        if self._cache is not None:
            elapsed = now - self._cache.timestamp
            if elapsed < _MIN_CALL_INTERVAL:
                if not _state_changed_enough(self._cache.game_state, game_state):
                    logger.debug("Using cached AI reasons (%.0fs old)", elapsed)
                    return self._cache.reasons

        reasons = self._call_cloud_api(game_state, jwt)
        self._cache = _CacheEntry(game_state=game_state, reasons=reasons)
        return reasons

    def _call_cloud_api(
        self,
        game_state: GameState,
        jwt: str | None,
    ) -> dict[str, str | None]:
        _null = {"top": None, "mid": None, "bot": None}

        if not settings.cloud_api_url:
            logger.warning("CLOUD_API_URL not set — AI reasons unavailable")
            return _null

        headers: dict[str, str] = {}
        if jwt:
            headers["Authorization"] = f"Bearer {jwt}"

        try:
            resp = httpx.post(
                f"{settings.cloud_api_url.rstrip('/')}/analysis/reasons",
                json=game_state.model_dump(),
                headers=headers,
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            logger.info(
                "Cloud API reasons received (minute=%d top=%s)",
                game_state.game_minute,
                "yes" if data.get("top") else "no",
            )
            return {
                "top": data.get("top"),
                "mid": data.get("mid"),
                "bot": data.get("bot"),
            }
        except Exception as exc:
            logger.error("Cloud API reasons call failed: %s", exc)
            return _null

    # ------------------------------------------------------------------
    # Macro mode
    # ------------------------------------------------------------------

    def get_macro_hints(
        self,
        context: str,
        state_key: str,
        jwt: str | None = None,
    ) -> list[MacroHint]:
        """Return macro awareness hints, using cache when state is unchanged.

        Args:
            context:   Structured game-state string from macro_state.build_macro_context().
            state_key: Change-detection key from macro_state.macro_state_key().
                       When it differs from the cached key a new call is made.
            jwt:       User's Supabase token forwarded to Railway for plan checking.

        Returns:
            List of MacroHint objects. Empty list for free users or on failure.
        """
        now = time.monotonic()

        if self._macro_cache is not None:
            elapsed = now - self._macro_cache.timestamp
            if elapsed < _MACRO_MIN_CALL_INTERVAL and self._macro_cache.state_key == state_key:
                logger.debug("Using cached macro hints (%.0fs old)", elapsed)
                return self._macro_cache.hints

        hints = self._call_macro_api(context, state_key, jwt)
        self._macro_cache = _MacroCacheEntry(state_key=state_key, hints=hints)
        return hints

    def _call_macro_api(
        self,
        context: str,
        state_key: str,
        jwt: str | None,
    ) -> list[MacroHint]:
        if not settings.cloud_api_url:
            logger.warning("CLOUD_API_URL not set — macro hints unavailable")
            return []

        headers: dict[str, str] = {}
        if jwt:
            headers["Authorization"] = f"Bearer {jwt}"

        try:
            resp = httpx.post(
                f"{settings.cloud_api_url.rstrip('/')}/analysis/macro",
                json={"context": context},
                headers=headers,
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            raw_hints = resp.json().get("hints", [])
            hints = [MacroHint(**h) for h in raw_hints]
            logger.info(
                "Cloud API macro hints received (key=%s count=%d)",
                state_key[:40],
                len(hints),
            )
            return hints
        except Exception as exc:
            logger.error("Cloud API macro call failed: %s", exc)
            return []
