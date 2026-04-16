"""Post-game coaching via Claude API.

Formats classified events into a structured prompt, calls the Anthropic API,
and parses the response into a list of CoachingMoment objects.

Prompt strategy:
  - Send all events as a numbered JSON list in a single call (cheaper than
    one call per event, and keeps context coherent).
  - Ask Claude to return a JSON array matched by index.
  - System prompt anchors Claude to low-elo coaching tone.
"""

import json
import logging
from typing import Any

import anthropic

from analysis.postgame.events import GankEvent, ObjectiveEvent, PathingIssue
from config import settings
from models import CoachingMoment

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a League of Legends jungle coach for low-elo players (Silver/Gold rank).
You will receive a list of timestamped events from a jungler's game.
For each event, evaluate the decision quality and explain it clearly.

Guidelines:
- Use plain language — no jargon without explanation.
- Be constructive and encouraging, not harsh.
- Focus on the WHY behind good and bad decisions.
- Keep each explanation to 2-3 sentences maximum.
- For bad decisions, always give a concrete alternative.
- Output ONLY valid JSON — no markdown, no text outside the JSON array.\
"""

_OBJECTIVE_DISPLAY: dict[str, str] = {
    "DRAGON": "Dragon",
    "BARON_NASHOR": "Baron Nashor",
    "RIFTHERALD": "Rift Herald",
}


def get_coaching_feedback(
    ganks: list[GankEvent],
    objectives: list[ObjectiveEvent],
    pathing: list[PathingIssue],
    champion_name: str,
) -> list[CoachingMoment]:
    """Send classified events to Claude and return structured coaching feedback.

    Args:
        ganks:         Classified gank events.
        objectives:    Classified objective events.
        pathing:       Detected pathing issues.
        champion_name: Champion the jungler played.

    Returns:
        List of CoachingMoment sorted by game timestamp.

    Raises:
        ValueError:           If Claude returns malformed JSON.
        anthropic.APIError:   On API failure.
    """
    events = _build_event_list(ganks, objectives, pathing, champion_name)
    if not events:
        logger.warning("No events to coach — returning empty list")
        return []

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    logger.info("Calling Claude for post-game coaching (%d events, %s)", len(events), champion_name)

    response = client.messages.create(
        model=settings.ai_model,
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_prompt(events, champion_name)}],
    )

    return _parse_response(response.content[0].text)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _build_event_list(
    ganks: list[GankEvent],
    objectives: list[ObjectiveEvent],
    pathing: list[PathingIssue],
    champion_name: str,
) -> list[dict[str, Any]]:
    """Merge and sort all events into a flat numbered list for the prompt."""
    events: list[dict[str, Any]] = []

    for g in ganks:
        verb = "got a kill" if g.was_jungler_killer else "assisted a kill"
        events.append({
            "index": len(events),
            "timestamp": g.timestamp_str,
            "type": "gank",
            "description": f"{champion_name} {verb} on an enemy in {g.lane} lane.",
            "lane": g.lane,
            "outcome": g.outcome,
        })

    for obj in objectives:
        name = _OBJECTIVE_DISPLAY.get(obj.objective_type, obj.objective_type)
        secured = "secured by ally team" if obj.secured_by_ally else "taken by enemy team"
        proximity = "near the pit" if obj.was_near_pit else f"{int(obj.jungler_distance_from_pit)} map units away from the pit"
        vision = "ward coverage existed" if obj.had_vision_before else "no ward coverage in the 60s before"
        spawn_note = " (first spawn)" if obj.is_first_spawn else " (respawn)"

        events.append({
            "index": len(events),
            "timestamp": obj.timestamp_str,
            "type": "objective",
            "description": (
                f"{name}{spawn_note} was {secured}. "
                f"Jungler was {proximity}. {vision}."
            ),
            "secured_by_ally": obj.secured_by_ally,
            "jungler_was_near": obj.was_near_pit,
            "had_vision": obj.had_vision_before,
            "is_first_spawn": obj.is_first_spawn,
        })

    for p in pathing:
        if p.issue == "in_base":
            desc = f"At minute {p.minute}, {champion_name} was sitting in base."
        else:
            desc = f"At minute {p.minute}, {champion_name} moved less than 800 units (possibly idle in the jungle)."
        events.append({
            "index": len(events),
            "timestamp": p.timestamp_str,
            "type": "pathing",
            "description": desc,
            "issue": p.issue,
        })

    # Sort by timestamp string (mm:ss — lexicographic sort works here)
    return sorted(events, key=lambda e: e["timestamp"])


def _build_prompt(events: list[dict[str, Any]], champion_name: str) -> str:
    return f"""\
Champion: {champion_name}
Total events: {len(events)}

Events (JSON):
{json.dumps(events, indent=2)}

For each event return an object with exactly these keys:
  "index"             — copy the index from input (integer)
  "timestamp"         — copy the timestamp from input (string)
  "what_happened"     — one sentence summarising the event for the player
  "was_good_decision" — true or false (boolean)
  "reasoning"         — 2-3 sentences explaining why it was good or bad (plain language)
  "suggestion"        — what they should have done instead, or null if the decision was correct

Return a JSON array of these objects, one per event, sorted by timestamp.\
"""


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _parse_response(raw: str) -> list[CoachingMoment]:
    """Parse Claude's JSON array into CoachingMoment objects.

    Raises:
        ValueError: If the response is not a valid JSON array.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Claude returned non-JSON: {raw!r}") from exc

    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array from Claude, got {type(data).__name__}")

    moments: list[CoachingMoment] = []
    for item in data:
        moments.append(CoachingMoment(
            timestamp_str=str(item.get("timestamp", "00:00")),
            what_happened=str(item.get("what_happened", "")),
            was_good_decision=bool(item.get("was_good_decision", False)),
            reasoning=str(item.get("reasoning", "")),
            suggestion=item.get("suggestion") or None,
        ))

    return sorted(moments, key=lambda m: m.timestamp_str)
