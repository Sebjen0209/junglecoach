"""Live analysis reasoning endpoint.

POST /analysis/reasons — called by the local backend during a live game.

The local backend builds the GameState (champion matchups, CS diffs, game phase)
and POSTs it here. We check the user's subscription tier and either:
  - Return null reasons (free tier — no Claude call is made)
  - Call Claude and return per-lane reasoning (premium / pro)

The Anthropic API key lives only in Railway environment variables and is never
sent to or stored on the user's machine.
"""

import json
import logging
from typing import Literal

import anthropic
from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from config import settings
from db.supabase import get_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis"])
_bearer = HTTPBearer(auto_error=False)

_SYSTEM_PROMPT = """\
You are a League of Legends jungle coaching assistant.
You receive structured data about all 3 lanes and must output gank priority advice.
Be concise. Maximum 2 sentences per lane. Focus on WHY, not just the priority.
Output valid JSON only — no markdown, no explanation outside the JSON.\
"""

_MACRO_SYSTEM_PROMPT = """\
You are a League of Legends game-awareness assistant for a jungler.

Your role is to highlight what is important right now and flag upcoming decisions.
Do NOT give direct instructions or tell the player what to do.
State what is happening, what is coming up, and what decisions may be relevant.
Players make their own choices — your role is to make sure they are informed.

Riot compliance: frame all points as awareness and context, never as commands.
Maximum 2 sentences per hint. Keep headlines under 8 words.
Output valid JSON only — no markdown, no explanation outside the JSON array.\
"""

_PREMIUM_PLANS = frozenset({"premium", "premium_monthly", "premium_annual", "pro", "pro_monthly"})


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class _LaneState(BaseModel):
    ally_champion: str
    enemy_champion: str
    matchup_winrate: float = Field(ge=0.0, le=1.0)
    ally_phase_strength: float = Field(ge=0.0, le=1.0)
    cs_diff: int
    ally_kill_pressure: bool


class _GameState(BaseModel):
    game_minute: int = Field(ge=0)
    game_phase: Literal["early", "mid", "late"]
    patch: str
    top: _LaneState
    mid: _LaneState
    bot: _LaneState


class ReasonsResponse(BaseModel):
    top: str | None
    mid: str | None
    bot: str | None


class _MacroRequest(BaseModel):
    context: str   # structured game-state block from macro_state.build_macro_context()


class _MacroHintItem(BaseModel):
    type: Literal["objective", "lane", "trade", "state"]
    urgency: Literal["critical", "high", "medium"]
    headline: str
    detail: str


class MacroResponse(BaseModel):
    hints: list[_MacroHintItem]


# ---------------------------------------------------------------------------
# Subscription check
# ---------------------------------------------------------------------------

def _get_plan(creds: HTTPAuthorizationCredentials | None) -> str:
    """Return the user's plan string, defaulting to 'free' on any failure."""
    if creds is None:
        return "free"
    try:
        user_resp = get_client().auth.get_user(creds.credentials)
        if not user_resp.user:
            return "free"
        result = (
            get_client()
            .table("subscriptions")
            .select("plan,status")
            .eq("user_id", str(user_resp.user.id))
            .limit(1)
            .execute()
        )
        if not result.data:
            return "free"
        sub = result.data[0]
        if sub.get("status") == "active":
            return sub.get("plan") or "free"
    except Exception as exc:
        logger.warning("Subscription check failed: %s", exc)
    return "free"


# ---------------------------------------------------------------------------
# Claude call
# ---------------------------------------------------------------------------

def _build_prompt(gs: _GameState) -> str:
    top, mid, bot = gs.top, gs.mid, gs.bot
    return f"""\
Current game state (minute {gs.game_minute}):

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


def _call_claude(game_state: _GameState) -> dict[str, str]:
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.ai_model,
        max_tokens=512,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_prompt(game_state)}],
    )
    data = json.loads(response.content[0].text)
    return {lane: data[lane]["reason"] for lane in ("top", "mid", "bot")}


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/reasons",
    response_model=ReasonsResponse,
    summary="Get AI reasoning for gank priorities (premium only)",
)
def post_reasons(
    game_state: _GameState,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> ReasonsResponse:
    """Called by the local backend every analysis cycle.

    Free users receive null reasons immediately — no Claude call is made.
    Premium/Pro users receive full per-lane reasoning from Claude.
    Falls back to null reasons gracefully if Claude is unreachable.
    """
    plan = _get_plan(creds)

    if plan not in _PREMIUM_PLANS:
        logger.debug("Free user — skipping Claude call (minute=%d)", game_state.game_minute)
        return ReasonsResponse(top=None, mid=None, bot=None)

    try:
        reasons = _call_claude(game_state)
        logger.info(
            "Claude reasons generated (plan=%s minute=%d)",
            plan,
            game_state.game_minute,
        )
        return ReasonsResponse(**reasons)
    except Exception as exc:
        logger.error("Claude call failed: %s", exc)
        return ReasonsResponse(top=None, mid=None, bot=None)


# ---------------------------------------------------------------------------
# Macro awareness endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/macro",
    response_model=MacroResponse,
    summary="Get macro awareness hints for mid/late game (premium only)",
)
def post_macro(
    request: _MacroRequest,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> MacroResponse:
    """Called by the local backend once laning phase has ended.

    Free users receive an empty hints list — no Claude call is made.
    Premium/Pro users receive 2-3 Claude-generated awareness points covering
    objective timing, lane state, and upcoming macro decisions.

    Riot compliance: all hints are framed as awareness, never as instructions.
    """
    plan = _get_plan(creds)

    if plan not in _PREMIUM_PLANS:
        logger.debug("Free user — skipping macro Claude call")
        return MacroResponse(hints=[])

    try:
        hints = _call_claude_macro(request.context)
        logger.info("Claude macro hints generated (plan=%s count=%d)", plan, len(hints))
        return MacroResponse(hints=hints)
    except Exception as exc:
        logger.error("Claude macro call failed: %s", exc)
        return MacroResponse(hints=[])


def _call_claude_macro(context: str) -> list[_MacroHintItem]:
    """Call Claude with the macro game-state context and parse the response."""
    user_message = (
        f"{context}\n\n"
        "Provide 2-3 awareness points for the jungler right now.\n"
        "Return a JSON array in exactly this format:\n"
        '[\n'
        '  {\n'
        '    "type": "objective|lane|trade|state",\n'
        '    "urgency": "critical|high|medium",\n'
        '    "headline": "Short headline (max 8 words)",\n'
        '    "detail": "Two sentences. What this situation means and why it matters."\n'
        '  }\n'
        ']'
    )

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.ai_model,
        max_tokens=512,
        system=_MACRO_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]

    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array from Claude macro, got {type(data).__name__}")

    return [_MacroHintItem(**item) for item in data]
