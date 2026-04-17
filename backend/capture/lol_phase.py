"""League of Legends client lifecycle phase detection.

Detects which phase the user is currently in:
  IDLE    — no LoL processes running
  CLIENT  — League client open (lobby, champion select, post-game results)
  LOADING — game process running but not yet in a live game (loading screen)
  IN_GAME — active live game (Riot Live Client Data API responding)

Uses psutil for process detection and a quick probe of Riot's local live client
API (127.0.0.1:2999) to distinguish the loading screen from an active game.
The API only responds during a live game, making it a reliable signal.
"""

import logging
from enum import Enum

import httpx
import psutil

logger = logging.getLogger(__name__)

_CLIENT_PROCESS = "LeagueClient.exe"
_GAME_PROCESS = "League of Legends.exe"

# Riot's local live client data API — only responds during an active game.
# Uses a self-signed TLS cert; verify=False is safe because this is loopback only.
_LIVE_CLIENT_URL = "https://127.0.0.1:2999/liveclientdata/gamestats"
_LIVE_CLIENT_TIMEOUT = 0.5  # seconds — must be fast, called every capture cycle


class LoLPhase(str, Enum):
    """Lifecycle phase of the League of Legends client."""

    IDLE = "idle"          # No LoL processes running
    CLIENT = "client"      # Client open: lobby, champion select, post-game lobby
    LOADING = "loading"    # Game process running, loading screen in progress
    IN_GAME = "in_game"    # Active live game — analysis should run


def _process_running(name: str) -> bool:
    """Return True if a process with the given name is currently running."""
    try:
        for proc in psutil.process_iter(["name"]):
            if proc.info["name"] == name:
                return True
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return False


def _live_game_api_responding() -> bool:
    """Return True if Riot's local live client data API is up.

    The API is only available during an active live game. Checking it is the
    most reliable way to distinguish the loading screen from an in-game state.
    """
    try:
        with httpx.Client(verify=False, timeout=_LIVE_CLIENT_TIMEOUT) as client:
            resp = client.get(_LIVE_CLIENT_URL)
            return resp.status_code == 200
    except Exception:
        return False


def detect_lol_phase() -> LoLPhase:
    """Detect the current League of Legends client lifecycle phase.

    Returns:
        LoLPhase representing where the user currently is in the LoL lifecycle.
    """
    client_running = _process_running(_CLIENT_PROCESS)
    game_running = _process_running(_GAME_PROCESS)

    if not client_running and not game_running:
        return LoLPhase.IDLE

    if client_running and not game_running:
        return LoLPhase.CLIENT

    # Game process is running — probe the live client API to tell if we're
    # still on the loading screen or already in a live game.
    if _live_game_api_responding():
        return LoLPhase.IN_GAME

    return LoLPhase.LOADING
