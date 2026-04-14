"""FastAPI local server — exposes the analysis results to the Electron overlay.

Binds to 127.0.0.1:7429 only (never accessible from the network).
Endpoints match the API contract in .claude/api-contract.md exactly.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from analysis.ai_client import AIClient
from analysis.game_phase import detect_game_phase
from analysis.suggestion import analyse
from capture.ocr import extract_scoreboard
from capture.screen import CaptureLoop
from config import settings
from data.db import init_db, seed_power_spikes
from models import AnalysisResult

logger = logging.getLogger(__name__)

_VERSION = "0.1.0"

# ---------------------------------------------------------------------------
# Application state (shared across requests)
# ---------------------------------------------------------------------------

_capture_loop: CaptureLoop | None = None
_ai_client: AIClient | None = None
_last_analysis: AnalysisResult = AnalysisResult(game_detected=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start capture loop and AI client on startup; stop on shutdown."""
    global _capture_loop, _ai_client

    logger.info("JungleCoach backend starting up (v%s)", _VERSION)
    init_db()
    seed_power_spikes()

    _ai_client = AIClient()
    _capture_loop = CaptureLoop()
    _capture_loop.start()

    yield

    logger.info("Shutting down capture loop...")
    if _capture_loop:
        _capture_loop.stop()


app = FastAPI(title="JungleCoach", version=_VERSION, lifespan=lifespan)

# Allow the Electron overlay (file:// origin) to call the local API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local only — binding to 127.0.0.1 keeps this safe
    allow_methods=["GET"],
    allow_headers=["Authorization"],
)


# ---------------------------------------------------------------------------
# Response models (inline — small enough not to warrant a separate file)
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    version: str


class StatusResponse(BaseModel):
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
async def health():
    return HealthResponse(status="ok", version=_VERSION)


@app.get("/status", response_model=StatusResponse)
async def status():
    if _capture_loop is None:
        return StatusResponse(
            lol_running=False, game_detected=False,
            capture_active=False, last_capture_at=None,
        )
    state = _capture_loop.get_state()
    return StatusResponse(
        lol_running=state.lol_running,
        game_detected=state.game_detected,
        capture_active=state.capture_active,
        last_capture_at=state.last_capture_at.isoformat() if state.last_capture_at else None,
    )


@app.get("/analysis", response_model=AnalysisResult)
async def analysis():
    global _last_analysis

    if _capture_loop is None:
        return AnalysisResult(game_detected=False)

    state = _capture_loop.get_state()

    if not state.game_detected or state.last_scoreboard is None:
        return AnalysisResult(game_detected=False)

    try:
        ocr_result = extract_scoreboard(state.last_scoreboard)
        phase, minute = detect_game_phase(state.last_timer) if state.last_timer else ("early", 0)
        _last_analysis = analyse(ocr_result, phase, minute, _ai_client)
    except Exception as exc:
        logger.error("Analysis pipeline error: %s", exc, exc_info=True)
        # Return last known good result rather than an error
        return _last_analysis

    return _last_analysis


@app.get("/subscription", response_model=SubscriptionResponse)
async def subscription():
    """Stub endpoint — full implementation is in the Railway API (Person 2 side)."""
    return SubscriptionResponse(plan="free", valid=True, expires_at=None)
