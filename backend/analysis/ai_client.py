"""Cloud API client for natural language gank reasoning.

POSTs the GameState to the Railway cloud API which holds the Anthropic key
and performs the Claude call. The key never touches the user's machine.

Free users receive None reasons (no Claude call is made server-side).
Premium/Pro users receive full reasoning strings.

Per-lane caching — only lanes that have changed meaningfully trigger a new
cloud API call, preserving cached reasons for stable lanes.

Trigger events (per lane):
  - Death (ally or enemy just died)       → immediate, then 2-min cooldown
  - Flash lost (enemy)                    → immediate, then 5-min cooldown
  - CS diff moved by ≥ 15                 → trigger if not in cooldown
  - Level diff crossed ±2                 → trigger if not in cooldown
  - Kill pressure toggled                 → trigger if not in cooldown
  - Game phase changed                    → all lanes trigger
  - ≥ 60s elapsed + any small change      → catch-all fallback
"""

import logging
import time
from dataclasses import dataclass, field

import httpx

from config import settings
from models import GameState, LaneState

logger = logging.getLogger(__name__)

_LANES = ("top", "mid", "bot")

# Minimum seconds between re-calls for the same lane (non-hot-event path)
_MIN_CALL_INTERVAL = 60.0

# CS diff must change by at least this much to trigger a re-call
_CS_DIFF_CHANGE_THRESHOLD = 15

# Level diff (ally − enemy) crossing this absolute value triggers a re-call
_LEVEL_DIFF_THRESHOLD = 2

# After a death event, suppress re-triggering for this long (typical respawn)
_DEATH_COOLDOWN = 120.0  # 2 minutes

# After enemy Flash is lost, suppress re-triggering for this long (Flash CD)
_FLASH_COOLDOWN = 300.0  # 5 minutes

# Cloud API timeout
_TIMEOUT = 10.0


@dataclass
class _LaneCacheEntry:
    """Cached state and reason for a single lane."""

    lane_state: LaneState
    reason: str | None
    timestamp: float = field(default_factory=time.monotonic)
    # Monotonic time before which this lane should not re-trigger (hot cooldown)
    hot_until: float = 0.0


def _hot_event_just_occurred(old: LaneState, new: LaneState) -> tuple[bool, float]:
    """Return (occurred, cooldown_seconds) if a high-priority event just fired."""
    # Someone just died this cycle
    if (not old.ally_is_dead and new.ally_is_dead) or \
       (not old.enemy_is_dead and new.enemy_is_dead):
        return True, _DEATH_COOLDOWN
    # Enemy just burned Flash
    if old.enemy_has_flash and not new.enemy_has_flash:
        return True, _FLASH_COOLDOWN
    return False, 0.0


def _lane_changed_enough(old: LaneState, new: LaneState) -> bool:
    """Return True if a lane changed enough to warrant a new AI call."""
    if abs(old.cs_diff - new.cs_diff) >= _CS_DIFF_CHANGE_THRESHOLD:
        return True
    if old.ally_kill_pressure != new.ally_kill_pressure:
        return True
    # Level lead just crossed the ±2 significance threshold (either direction)
    if (abs(old.level_diff) >= _LEVEL_DIFF_THRESHOLD) != \
       (abs(new.level_diff) >= _LEVEL_DIFF_THRESHOLD):
        return True
    return False


class AIClient:
    """Fetches AI reasoning from the cloud API with per-lane state-based caching.

    Usage::

        client = AIClient()
        reasons = client.get_reasons(game_state, jwt=user_token)
        # {"top": "Riven is strong...", "mid": None, "bot": "..."}
        # None means free tier or cloud API unreachable.
    """

    def __init__(self) -> None:
        self._cache: dict[str, _LaneCacheEntry] = {}
        self._last_phase: str | None = None

    def get_reasons(
        self,
        game_state: GameState,
        jwt: str | None = None,
    ) -> dict[str, str | None]:
        """Return per-lane reason strings, using cache for unchanged lanes.

        Args:
            game_state: Current game state from the capture pipeline.
            jwt:        User's Supabase JWT forwarded to Railway for subscription
                        checking. None falls back to free tier.

        Returns:
            Dict with keys 'top', 'mid', 'bot'.
            Values are reason strings for premium users, None for free users
            or when the cloud API is unreachable.
        """
        now = time.monotonic()
        phase_changed = (
            self._last_phase is not None
            and self._last_phase != game_state.game_phase
        )
        self._last_phase = game_state.game_phase

        lanes_to_update: list[str] = []
        new_hot_until: dict[str, float] = {}

        for lane_name in _LANES:
            new_lane: LaneState = getattr(game_state, lane_name)
            entry = self._cache.get(lane_name)

            if entry is None or phase_changed:
                lanes_to_update.append(lane_name)
                continue

            # Hot events fire immediately and set a cooldown
            hot_occurred, cooldown_duration = _hot_event_just_occurred(entry.lane_state, new_lane)
            if hot_occurred:
                lanes_to_update.append(lane_name)
                new_hot_until[lane_name] = now + cooldown_duration
                continue

            # Respect active hot cooldown — no re-trigger until it expires
            if now < entry.hot_until:
                logger.debug(
                    "%s lane in hot cooldown (%.0fs remaining)",
                    lane_name,
                    entry.hot_until - now,
                )
                continue

            # Normal interval + meaningful-change check
            elapsed = now - entry.timestamp
            if elapsed >= _MIN_CALL_INTERVAL and _lane_changed_enough(entry.lane_state, new_lane):
                lanes_to_update.append(lane_name)

        if not lanes_to_update:
            logger.debug("All lanes cached — skipping cloud API call")
            return {
                lane: self._cache[lane].reason if lane in self._cache else None
                for lane in _LANES
            }

        logger.info(
            "Cloud API call for lanes=%s (game minute=%d)",
            lanes_to_update,
            game_state.game_minute,
        )
        new_reasons = self._call_cloud_api(game_state, lanes_to_update, jwt)

        for lane_name in lanes_to_update:
            new_lane = getattr(game_state, lane_name)
            self._cache[lane_name] = _LaneCacheEntry(
                lane_state=new_lane,
                reason=new_reasons.get(lane_name),
                hot_until=new_hot_until.get(lane_name, 0.0),
            )

        return {
            lane: self._cache[lane].reason if lane in self._cache else None
            for lane in _LANES
        }

    def _call_cloud_api(
        self,
        game_state: GameState,
        lanes_to_update: list[str],
        jwt: str | None,
    ) -> dict[str, str | None]:
        null: dict[str, str | None] = {lane: None for lane in _LANES}

        if not settings.cloud_api_url:
            logger.warning("CLOUD_API_URL not set — AI reasons unavailable")
            return null

        headers: dict[str, str] = {}
        if jwt:
            headers["Authorization"] = f"Bearer {jwt}"

        payload = {**game_state.model_dump(), "lanes_to_update": lanes_to_update}

        try:
            resp = httpx.post(
                f"{settings.cloud_api_url.rstrip('/')}/analysis/reasons",
                json=payload,
                headers=headers,
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            logger.info(
                "Cloud API reasons received for %s (minute=%d)",
                lanes_to_update,
                game_state.game_minute,
            )
            return {lane: data.get(lane) for lane in _LANES}
        except Exception as exc:
            logger.error("Cloud API reasons call failed: %s", exc)
            return null
