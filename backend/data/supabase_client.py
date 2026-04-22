"""Supabase helpers for token verification and post-game usage limits."""

import logging
from datetime import datetime, timedelta, timezone

import requests

from config import settings

logger = logging.getLogger(__name__)

# Limits keyed by plan value stored in Supabase subscriptions table.
PLAN_LIMITS: dict[str, dict] = {
    "free":    {"count": 2,  "days": 30},
    "premium": {"count": 15, "days": 7},
    "pro":     {"count": 35, "days": 7},
}


def _headers(token: str) -> dict:
    return {
        "apikey": settings.supabase_anon_key,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def verify_and_get_user_id(token: str) -> str | None:
    """Verify the Supabase JWT and return the user's UUID, or None if invalid."""
    try:
        res = requests.get(
            f"{settings.supabase_url}/auth/v1/user",
            headers=_headers(token),
            timeout=4,
        )
        if res.status_code == 200:
            return res.json().get("id")
    except Exception:
        logger.warning("Supabase token verification request failed")
    return None


def get_user_plan(user_id: str, token: str) -> str:
    """Return the user's active plan name ('free' if not found or inactive)."""
    try:
        res = requests.get(
            f"{settings.supabase_url}/rest/v1/subscriptions",
            params={"user_id": f"eq.{user_id}", "select": "plan,status", "limit": "1"},
            headers=_headers(token),
            timeout=4,
        )
        if res.status_code == 200:
            rows = res.json()
            if rows and rows[0].get("status") == "active":
                return rows[0].get("plan", "free")
    except Exception:
        logger.warning("Could not fetch user plan from Supabase")
    return "free"


def count_postgame_usage(user_id: str, token: str, plan: str) -> int:
    """Count post-game analyses used within the plan's rolling window."""
    cfg = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
    since = (datetime.now(timezone.utc) - timedelta(days=cfg["days"])).isoformat()
    try:
        res = requests.get(
            f"{settings.supabase_url}/rest/v1/usage_events",
            params={
                "user_id": f"eq.{user_id}",
                "event_type": "eq.postgame_analysed",
                "created_at": f"gte.{since}",
                "select": "id",
            },
            headers=_headers(token),
            timeout=4,
        )
        if res.status_code == 200:
            return len(res.json())
    except Exception:
        logger.warning("Could not count post-game usage from Supabase")
    return 0


def record_postgame_usage(user_id: str, match_id: str, token: str) -> None:
    """Insert a usage_events row for a completed post-game analysis."""
    try:
        requests.post(
            f"{settings.supabase_url}/rest/v1/usage_events",
            json={"user_id": user_id, "event_type": "postgame_analysed", "metadata": {"match_id": match_id}},
            headers={**_headers(token), "Prefer": "return=minimal"},
            timeout=4,
        )
    except Exception:
        logger.warning("Could not record post-game usage event")


def get_plan_limit(plan: str) -> dict:
    return PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
