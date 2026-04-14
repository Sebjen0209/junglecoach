"""Maps raw OCR text to canonical champion names and roles.

Uses exact matching first, then alias lookup, then difflib fuzzy matching
as a last resort. Raises ValueError if no match above the confidence
threshold is found.
"""

import json
import logging
from difflib import get_close_matches
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_FILE = Path(__file__).parent.parent / "data" / "champions.json"

# Loaded once at import time — small file, safe to cache in memory.
def _load_champions() -> tuple[dict[str, str], list[str]]:
    """Return (alias_map, canonical_names_list).

    alias_map: lowercase alias/name → canonical name
    canonical_names_list: list of all canonical names (for difflib)
    """
    data = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    alias_map: dict[str, str] = {}
    canonical: list[str] = []

    for entry in data["champions"]:
        name: str = entry["name"]
        canonical.append(name)
        alias_map[name.lower()] = name
        for alias in entry.get("aliases", []):
            alias_map[alias.lower()] = name

    return alias_map, canonical


_ALIAS_MAP, _CANONICAL_NAMES = _load_champions()

# Scoreboard column order → role (0-indexed, left to right on TAB screen)
_COLUMN_ROLES = ["top", "jungle", "mid", "bot", "support"]


def parse_champion_name(raw: str, cutoff: float = 0.6) -> str:
    """Resolve a raw OCR string to a canonical champion name.

    Args:
        raw: The raw string from OCR (may contain typos/garbled chars).
        cutoff: Minimum similarity score for fuzzy matching (0–1).

    Returns:
        The canonical champion name from champions.json.

    Raises:
        ValueError: If no match is found above the cutoff.
    """
    cleaned = raw.strip()

    # 1. Exact match (case-insensitive)
    exact = _ALIAS_MAP.get(cleaned.lower())
    if exact:
        return exact

    # 2. Fuzzy match against canonical names + aliases
    matches = get_close_matches(cleaned.lower(), _ALIAS_MAP.keys(), n=1, cutoff=cutoff)
    if matches:
        canonical = _ALIAS_MAP[matches[0]]
        logger.debug("Fuzzy matched %r → %r", raw, canonical)
        return canonical

    raise ValueError(
        f"Could not match OCR output {raw!r} to any known champion "
        f"(cutoff={cutoff})"
    )


def parse_scoreboard_row(names: list[str]) -> dict[str, str]:
    """Parse a list of 5 champion names (one team row) into a role→name dict.

    Args:
        names: List of 5 raw OCR strings in scoreboard column order
               [top, jungle, mid, bot, support].

    Returns:
        Dict mapping role names to canonical champion names.

    Raises:
        ValueError: If the list doesn't have exactly 5 entries, or if any
                    name cannot be resolved.
    """
    if len(names) != 5:
        raise ValueError(
            f"Expected 5 champion names for a full team row, got {len(names)}: {names}"
        )

    result: dict[str, str] = {}
    for i, raw in enumerate(names):
        role = _COLUMN_ROLES[i]
        result[role] = parse_champion_name(raw)

    return result


def get_all_champion_names() -> list[str]:
    """Return sorted list of all canonical champion names."""
    return sorted(_CANONICAL_NAMES)
