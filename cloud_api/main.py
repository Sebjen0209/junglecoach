"""JungleCoach Cloud API — Railway-deployed FastAPI service.

Handles post-game jungle analysis: Riot API → Claude coaching → Supabase persistence.
The live in-game analysis (screen capture, OCR) stays on the local backend only.

Startup validates that all required environment variables are present so Railway
deployment fails loudly on misconfiguration rather than silently at request time.
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from routers import postgame

# ---------------------------------------------------------------------------
# Logging — stdout so Railway log aggregation picks it up
# ---------------------------------------------------------------------------

logging.basicConfig(
    stream=sys.stdout,
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

_VERSION = "0.1.0"


# ---------------------------------------------------------------------------
# Startup validation
# ---------------------------------------------------------------------------

def _validate_config() -> None:
    """Fail fast on missing required secrets rather than erroring at request time."""
    required = {
        "ANTHROPIC_API_KEY": settings.anthropic_api_key,
        "RIOT_API_KEY": settings.riot_api_key,
        "SUPABASE_URL": settings.supabase_url,
        "SUPABASE_SERVICE_ROLE_KEY": settings.supabase_service_role_key,
    }
    missing = [name for name, val in required.items() if not val]
    if missing:
        logger.critical("Missing required environment variables: %s", ", ".join(missing))
        sys.exit(1)

    if settings.is_production and not settings.origins_list:
        logger.critical(
            "ALLOWED_ORIGINS is not set. "
            "Production deployments must explicitly list allowed origins."
        )
        sys.exit(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("JungleCoach Cloud API v%s starting (%s)", _VERSION, settings.environment)
    _validate_config()
    yield
    logger.info("JungleCoach Cloud API shutting down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="JungleCoach Cloud API",
    version=_VERSION,
    lifespan=lifespan,
    # Disable interactive docs in production — reduces attack surface
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
    openapi_url="/openapi.json" if not settings.is_production else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["Authorization", "Content-Type"],
)


# ---------------------------------------------------------------------------
# Global error handler — never leak stack traces to the client
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled exception on %s %s: %s",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again later."},
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

app.include_router(postgame.router)


@app.get("/health", include_in_schema=False)
async def health() -> dict:
    """Railway health check endpoint."""
    return {"status": "ok", "version": _VERSION}
