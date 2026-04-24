"""FastAPI local server — exposes the analysis results to the Electron overlay.

Binds to 127.0.0.1:7429 only (never accessible from the network).
Endpoints match the API contract in .claude/api-contract.md exactly.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from analysis.ai_client import AIClient
from analysis.postgame import run_postgame_analysis
from data.supabase_client import (
    count_postgame_usage,
    get_plan_limit,
    get_user_plan,
    record_postgame_usage,
    verify_and_get_user_id,
)
from analysis.suggestion import analyse
from capture.live_client import get_snapshot
from capture.screen import CaptureLoop
from config import settings
from data.db import init_db, seed_power_spikes
from data.riot_api import fetch_champion_id_map, fetch_profiles
from data.updater import check_and_update
from models import AnalysisResult, PlayerProfile, PostGameAnalysis

logger = logging.getLogger(__name__)

_VERSION = "0.4.0"

# ---------------------------------------------------------------------------
# Application state (shared across requests)
# ---------------------------------------------------------------------------

_capture_loop: CaptureLoop | None = None
_ai_client: AIClient | None = None
_last_analysis: AnalysisResult = AnalysisResult(game_detected=False)

# Champion name → Riot champion ID (fetched from Data Dragon once at startup).
# Used to resolve champion names to IDs for the mastery API endpoint.
_champion_id_map: dict[str, int] = {}

# Player profiles for the current game, keyed by summoner name.
# Fetched once when a game is first detected, cleared when the game ends.
_player_profiles: dict[str, PlayerProfile] = {}
_profiles_loaded_for_current_game: bool = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start services on startup; stop cleanly on shutdown."""
    global _capture_loop, _ai_client, _champion_id_map

    logger.info("JungleCoach backend starting up (v%s)", _VERSION)
    init_db()

    # Check for a newer matchup DB from the cloud API before seeding power spikes.
    # If updated, the new DB already contains up-to-date matchup rows; we then
    # re-seed power spikes so phase ratings are consistent with the new patch.
    updated = await asyncio.to_thread(check_and_update)
    if updated:
        logger.info("Matchup DB replaced — re-running DB init and power spike seed")
        init_db()

    seed_power_spikes()

    _ai_client = AIClient()
    _capture_loop = CaptureLoop()
    _capture_loop.start()

    # Pre-fetch the champion ID map so it's ready when a game starts.
    # This is a one-time call to Data Dragon CDN — fast and non-blocking startup.
    _champion_id_map = await fetch_champion_id_map()
    logger.info("Loaded %d champion IDs from Data Dragon", len(_champion_id_map))

    yield

    logger.info("Shutting down phase monitor...")
    if _capture_loop:
        _capture_loop.stop()


app = FastAPI(title="JungleCoach", version=_VERSION, lifespan=lifespan)

# Allow the Electron overlay (file:// origin) to call the local API.
# Binding to 127.0.0.1 means this is only reachable from the same machine.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["Authorization", "Content-Type"],
)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    version: str


class StatusResponse(BaseModel):
    lol_phase: str          # "idle" | "client" | "loading" | "in_game"
    lol_running: bool
    game_detected: bool
    capture_active: bool
    last_capture_at: str | None


class SubscriptionResponse(BaseModel):
    plan: str
    valid: bool
    expires_at: str | None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=_VERSION)


@app.get("/status", response_model=StatusResponse)
async def status() -> StatusResponse:
    if _capture_loop is None:
        return StatusResponse(
            lol_phase="idle",
            lol_running=False,
            game_detected=False,
            capture_active=False,
            last_capture_at=None,
        )
    state = _capture_loop.get_state()
    return StatusResponse(
        lol_phase=state.lol_phase,
        lol_running=state.lol_running,
        game_detected=state.game_detected,
        capture_active=state.capture_active,
        last_capture_at=(
            state.last_capture_at.isoformat() if state.last_capture_at else None
        ),
    )


@app.get("/analysis", response_model=AnalysisResult)
async def analysis(
    authorization: str | None = Header(default=None),
) -> AnalysisResult:
    global _last_analysis, _player_profiles, _profiles_loaded_for_current_game
    jwt = authorization[len("Bearer "):] if authorization and authorization.startswith("Bearer ") else None

    # Fast-path: phase monitor says no game is running.
    if _capture_loop is not None and not _capture_loop.get_state().game_detected:
        # Clear stale profiles from the previous game.
        if _profiles_loaded_for_current_game:
            _player_profiles = {}
            _profiles_loaded_for_current_game = False
        return AnalysisResult(game_detected=False)

    snapshot = get_snapshot()
    if snapshot is None:
        return AnalysisResult(game_detected=False)

    # Fetch player profiles once when the game is first detected.
    # We skip this if RIOT_API_KEY is not configured (graceful degradation).
    if not _profiles_loaded_for_current_game and settings.riot_api_key:
        players = [
            (p.summoner_name, p.champion_name)
            for p in snapshot.ally_players + snapshot.enemy_players
        ]
        _player_profiles = await fetch_profiles(
            players, _champion_id_map, settings.riot_region, settings.riot_api_key
        )
        _profiles_loaded_for_current_game = True

    try:
        _last_analysis = analyse(snapshot, _ai_client, _player_profiles or None, jwt=jwt)
    except Exception as exc:
        logger.error("Analysis pipeline error: %s", exc, exc_info=True)
        return _last_analysis

    return _last_analysis


@app.get("/subscription", response_model=SubscriptionResponse)
async def subscription() -> SubscriptionResponse:
    """Stub endpoint — full implementation is in the Railway API (Person 2 side)."""
    return SubscriptionResponse(plan="free", valid=True, expires_at=None)


@app.get("/postgame/{match_id}", response_model=PostGameAnalysis)
def postgame(
    match_id: str,
    puuid: str | None = None,
    summoner_name: str | None = None,
    authorization: str | None = Header(default=None),
):
    """Fetch and analyse a completed match, returning timestamped coaching feedback.

    Requires a valid Supabase bearer token when SUPABASE_URL is configured.
    Returns 401 if the token is missing or invalid.
    Returns 429 if the user has exhausted their plan's monthly/weekly limit.
    Returns 422 if the match has no jungle participant.
    Returns 503 if the Riot API is unreachable or the key is invalid.
    """
    user_id: str | None = None
    plan = "free"
    token: str | None = authorization[7:] if authorization and authorization.startswith("Bearer ") else None

    supabase_enabled = bool(settings.supabase_url and settings.supabase_anon_key)

    if supabase_enabled:
        if not token:
            raise HTTPException(status_code=401, detail="Authentication required")
        user_id = verify_and_get_user_id(token)
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        plan = get_user_plan(user_id, token)
        limit = get_plan_limit(plan)
        usage = count_postgame_usage(user_id, token, plan)

        if usage >= limit["count"]:
            window = "month" if limit["days"] == 30 else "week"
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Post-game limit reached: {limit['count']} per {window} on the {plan} plan. "
                    "Upgrade for a higher limit."
                ),
            )

    try:
        result = run_postgame_analysis(match_id, puuid=puuid, summoner_name=summoner_name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.error("Post-game analysis failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if supabase_enabled and user_id and token:
        record_postgame_usage(user_id, match_id, token)

    return result
