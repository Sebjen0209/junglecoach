"""Post-game analysis router.

Single endpoint: GET /postgame/{match_id}

Flow:
  1. Validate match ID format (fail fast before any API calls)
  2. Authenticate the request via Supabase JWT
  3. Return cached analysis from Supabase if it exists (free, instant)
  4. Otherwise run the full pipeline (Riot API → Claude → persist → return)
"""

import logging
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status

from analysis.postgame import run_postgame_analysis
from auth import CurrentUser
from db.supabase import (
    count_recent_analyses,
    get_user_plan,
    load_existing_analysis,
    save_analysis,
)
from models import PostGameAnalysis

PLAN_LIMITS: dict[str, dict] = {
    "free":    {"count": 2,  "days": 30},
    "premium": {"count": 15, "days": 7},
    "pro":     {"count": 35, "days": 7},
}

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/postgame", tags=["postgame"])

# Riot match IDs are always PLATFORM_digits, e.g. EUW1_7123456789
_MATCH_ID_RE = re.compile(r"^[A-Z0-9]+_\d+$")


@router.get(
    "/{match_id}",
    response_model=PostGameAnalysis,
    summary="Get post-game jungle coaching for a completed match",
)
def get_postgame_analysis(
    match_id: str,
    current_user: CurrentUser,
    summoner_name: str | None = None,
    puuid: str | None = None,
) -> PostGameAnalysis:
    """Analyse a completed match and return timestamped jungle coaching feedback.

    If this user has already requested analysis for this match, the persisted
    result is returned immediately — no Riot API or Claude API call is made.

    Args (path):
        match_id:      Riot match ID, e.g. ``EUW1_7123456789``.
                       The platform prefix is used to auto-detect region routing.

    Args (query):
        summoner_name: The player's in-game summoner name — used to identify
                       which team's jungler to coach. Triggers one extra Riot
                       API call to resolve the PUUID.
        puuid:         Alternative to summoner_name (preferred, no extra call).
                       If neither is provided, defaults to the blue-team jungler.

    Returns:
        PostGameAnalysis with per-event coaching moments sorted by game time.

    Raises:
        401: Missing or invalid Bearer token.
        422: Malformed match ID or no jungle participant found in the match.
        429: User has exhausted their plan's post-game analysis quota.
        503: Riot API or Anthropic API unreachable.
    """
    if not _MATCH_ID_RE.match(match_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid match ID format: {match_id!r}. "
                "Expected PLATFORM_digits, e.g. EUW1_7123456789."
            ),
        )

    user_id = current_user["id"]

    # --- Cache hit: return persisted result immediately (no quota consumed) ---
    cached = load_existing_analysis(user_id, match_id)
    if cached is not None:
        return cached

    # --- Quota check: enforce per-plan limits before running the pipeline ---
    plan = get_user_plan(user_id)
    limit = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
    since = (datetime.now(timezone.utc) - timedelta(days=limit["days"])).isoformat()
    usage = count_recent_analyses(user_id, since)

    if usage >= limit["count"]:
        window = "month" if limit["days"] == 30 else "week"
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Post-game analysis limit reached: {limit['count']} per {window} "
                f"on the {plan} plan. Upgrade for a higher limit."
            ),
        )

    # --- Cache miss: run full pipeline ---
    logger.info(
        "Running analysis: match=%s user=%.8s summoner=%r",
        match_id,
        user_id,
        summoner_name,
    )
    try:
        analysis = run_postgame_analysis(
            match_id,
            puuid=puuid,
            summoner_name=summoner_name,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        logger.error("Pipeline failure for match %s: %s", match_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analysis service temporarily unavailable. Please try again.",
        ) from exc

    # Persist result — failure here is non-fatal (user still gets the response)
    save_analysis(user_id, analysis)

    return analysis
