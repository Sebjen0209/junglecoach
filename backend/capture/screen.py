"""Background phase monitor for the League of Legends client lifecycle.

Runs a lightweight background thread that polls the LoL client processes and
the Riot Live Client Data API every few seconds to track which lifecycle phase
the user is in. The FastAPI server reads this state to decide whether to fetch
a new GameSnapshot from the Live Client API.

Screen capture and OCR have been replaced by the Riot Live Client Data API
(see capture/live_client.py). This module is now only responsible for phase
tracking and the /status endpoint state.
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Event, Thread
from typing import Optional

from capture.lol_phase import LoLPhase, detect_lol_phase

logger = logging.getLogger(__name__)

# How often the background thread polls for phase changes (seconds).
_POLL_INTERVAL = 3.0


@dataclass
class CaptureState:
    """Thread-safe snapshot of the current client lifecycle state."""

    lol_phase: str = "idle"           # LoLPhase.value
    lol_running: bool = False
    game_detected: bool = False
    capture_active: bool = False
    last_capture_at: Optional[datetime] = None
    error: Optional[str] = None


class CaptureLoop:
    """Background thread that tracks the LoL client lifecycle phase.

    Usage::

        loop = CaptureLoop()
        loop.start()
        state = loop.get_state()   # safe to call from any thread
        loop.stop()
    """

    def __init__(self, interval: float = _POLL_INTERVAL) -> None:
        self._interval = interval
        self._stop_event = Event()
        self._state = CaptureState()
        self._thread: Optional[Thread] = None

    def start(self) -> None:
        """Start the background phase-polling thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(target=self._run, daemon=True, name="capture-loop")
        self._thread.start()
        logger.info("Phase monitor started (poll interval=%.1fs)", self._interval)

    def stop(self) -> None:
        """Signal the thread to stop and wait for it to finish."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("Phase monitor stopped")

    def get_state(self) -> CaptureState:
        """Return the current captured state (snapshot — safe across threads)."""
        return self._state

    def _run(self) -> None:
        self._state.capture_active = True
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as exc:
                logger.error("Phase monitor error: %s", exc, exc_info=True)
                self._state.error = str(exc)
            time.sleep(self._interval)
        self._state.capture_active = False

    def _tick(self) -> None:
        phase = detect_lol_phase()
        self._state.lol_phase = phase.value
        self._state.lol_running = phase != LoLPhase.IDLE
        self._state.game_detected = phase == LoLPhase.IN_GAME

        if phase == LoLPhase.IN_GAME:
            self._state.last_capture_at = datetime.now(timezone.utc)
            self._state.error = None
