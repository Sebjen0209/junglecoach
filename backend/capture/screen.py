"""Screen capture loop and League of Legends window detection.

Uses mss for fast screenshot capture. Detects LoL by process name so it
works regardless of window title localisation or multi-monitor setups.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Event, Thread

import mss
import mss.tools
from PIL import Image

logger = logging.getLogger(__name__)

# LoL process names across platforms
_LOL_PROCESS_NAMES = {"League of Legends.exe", "LeagueOfLegends.exe", "LeagueClient.exe"}

# How often to take a full screenshot (seconds)
_CAPTURE_INTERVAL = 3.0

# Scoreboard region: approximate bounding box of the TAB overlay on a
# 1920×1080 screen. The overlay fills most of the screen; we crop to the
# champion-name columns to reduce OCR noise.
# Format: {"top": y, "left": x, "width": w, "height": h}
_SCOREBOARD_REGION_1080P = {"top": 130, "left": 290, "width": 1340, "height": 760}

# Timer region: top-centre of screen where the game clock is shown
_TIMER_REGION_1080P = {"top": 10, "left": 870, "width": 180, "height": 40}


@dataclass
class CaptureState:
    """Thread-safe snapshot of the capture loop's current state."""

    lol_running: bool = False
    game_detected: bool = False
    capture_active: bool = False
    last_capture_at: datetime | None = None
    last_scoreboard: Image.Image | None = None
    last_timer: Image.Image | None = None
    error: str | None = None


def _is_lol_running() -> bool:
    """Return True if a LoL game process is currently running."""
    try:
        import psutil  # optional dependency — graceful fallback if missing

        for proc in psutil.process_iter(["name"]):
            if proc.info["name"] in _LOL_PROCESS_NAMES:
                return True
        return False
    except ImportError:
        logger.warning("psutil not installed — cannot detect LoL process. Assuming running.")
        return True
    except Exception as exc:
        logger.warning("Process detection failed: %s", exc)
        return False


def _scale_region(region: dict, screen_width: int, screen_height: int) -> dict:
    """Scale a 1080p region dict to the actual screen resolution."""
    sx = screen_width / 1920
    sy = screen_height / 1080
    return {
        "top": int(region["top"] * sy),
        "left": int(region["left"] * sx),
        "width": int(region["width"] * sx),
        "height": int(region["height"] * sy),
    }


def _capture_regions(sct: mss.base.MSSBase) -> tuple[Image.Image, Image.Image]:
    """Capture the scoreboard and timer regions from the primary monitor.

    Returns:
        (scoreboard_image, timer_image) as PIL Images.
    """
    monitor = sct.monitors[1]  # primary monitor
    w, h = monitor["width"], monitor["height"]

    scoreboard_region = _scale_region(_SCOREBOARD_REGION_1080P, w, h)
    timer_region = _scale_region(_TIMER_REGION_1080P, w, h)

    scoreboard_img = Image.frombytes(
        "RGB",
        (scoreboard_region["width"], scoreboard_region["height"]),
        sct.grab(scoreboard_region).rgb,
    )
    timer_img = Image.frombytes(
        "RGB",
        (timer_region["width"], timer_region["height"]),
        sct.grab(timer_region).rgb,
    )

    return scoreboard_img, timer_img


class CaptureLoop:
    """Background thread that takes periodic screenshots while LoL is running.

    Usage::

        loop = CaptureLoop()
        loop.start()
        # ... later ...
        state = loop.get_state()
        loop.stop()
    """

    def __init__(self, interval: float = _CAPTURE_INTERVAL) -> None:
        self._interval = interval
        self._stop_event = Event()
        self._state = CaptureState()
        self._thread: Thread | None = None

    def start(self) -> None:
        """Start the background capture thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(target=self._run, daemon=True, name="capture-loop")
        self._thread.start()
        logger.info("Capture loop started (interval=%.1fs)", self._interval)

    def stop(self) -> None:
        """Signal the capture thread to stop and wait for it."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("Capture loop stopped")

    def get_state(self) -> CaptureState:
        """Return a snapshot of the current capture state."""
        return self._state

    def _run(self) -> None:
        self._state.capture_active = True
        with mss.mss() as sct:
            while not self._stop_event.is_set():
                try:
                    self._tick(sct)
                except Exception as exc:
                    logger.error("Capture error: %s", exc, exc_info=True)
                    self._state.error = str(exc)
                time.sleep(self._interval)
        self._state.capture_active = False

    def _tick(self, sct: mss.base.MSSBase) -> None:
        lol_running = _is_lol_running()
        self._state.lol_running = lol_running

        if not lol_running:
            self._state.game_detected = False
            return

        scoreboard, timer = _capture_regions(sct)

        # Heuristic game detection: if the timer region contains mostly
        # dark pixels it's likely the loading screen or lobby — not a live game.
        self._state.game_detected = _looks_like_live_game(timer)
        self._state.last_capture_at = datetime.now(timezone.utc)
        self._state.last_scoreboard = scoreboard
        self._state.last_timer = timer
        self._state.error = None


def _looks_like_live_game(timer_img: Image.Image) -> bool:
    """Rough heuristic: does the timer region look like an in-game clock?

    The in-game timer is white text on a semi-transparent dark background.
    We check whether the image has enough bright pixels to suggest text is
    present, which rules out the loading screen (fully black) and the lobby.

    This is intentionally conservative — false negatives (missing a capture)
    are less harmful than false positives (trying to OCR a non-game screen).
    """
    grayscale = timer_img.convert("L")
    pixels = list(grayscale.getdata())
    bright = sum(1 for p in pixels if p > 180)
    ratio = bright / len(pixels) if pixels else 0
    # Expect at least 5% bright pixels (clock digits) but not >60% (white screen)
    return 0.05 < ratio < 0.60
