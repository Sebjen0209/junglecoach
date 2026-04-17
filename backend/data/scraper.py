"""U.GG matchup win-rate scraper.

Fetches champion counter data from U.GG's server-side-rendered counter pages.
U.GG embeds matchup stats in window.__SSR_DATA__ in the page HTML, so a plain
httpx GET works — no headless browser needed.

Run manually after each LoL patch (~every 2 weeks):
    cd backend
    python -m data.scraper

For local dev without network access use --defaults:
    python -m data.scraper --defaults
"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from config import settings
from data.db import init_db, matchup_count, seed_power_spikes, upsert_matchup

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DDRAGON_VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
_DDRAGON_CHAMPIONS_URL = (
    "https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
)

# U.GG counter page URL — SSR embeds matchup data in window.__SSR_DATA__
_UGG_COUNTER_URL = "https://u.gg/lol/champions/{slug}/counter?role={role}"

# Tier we pull win rates for: world-wide Emerald+ ranked solo
_TARGET_TIER = "world_emerald_plus_{role}"

# U.GG role slug: our internal name → URL parameter and tier-key suffix
_ROLE_SLUGS: dict[str, str] = {
    "top": "top",
    "jungle": "jungle",
    "mid": "mid",
    "bot": "adc",
    "support": "support",
}

# Minimum games to accept a matchup row — anything below is noise
_MIN_GAMES = 10

# Polite delay between requests
_SLEEP_BETWEEN_REQUESTS = 0.5  # seconds

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://u.gg/",
}


# ---------------------------------------------------------------------------
# Data Dragon helpers
# ---------------------------------------------------------------------------

async def _fetch_champion_maps(
    client: httpx.AsyncClient,
) -> tuple[dict[str, int], dict[str, str]]:
    """Return (name_to_numeric_id, name_to_url_slug) from Riot Data Dragon.

    Uses Data Dragon's `id` field (not the display name) for URL slugs so
    special characters are handled correctly:
        "Kai'Sa" → (523, "kaisa")
        "Wukong"  → (62,  "monkeyking")
    """
    resp = await client.get(_DDRAGON_VERSIONS_URL, timeout=10)
    resp.raise_for_status()
    version = resp.json()[0]

    resp = await client.get(_DDRAGON_CHAMPIONS_URL.format(version=version), timeout=10)
    resp.raise_for_status()
    champs = resp.json()["data"]

    id_map: dict[str, int] = {}
    slug_map: dict[str, str] = {}
    for entry in champs.values():
        display: str = entry["name"]
        id_map[display] = int(entry["key"])
        slug_map[display] = entry["id"].lower()  # e.g. "kaisa", "monkeyking"

    logger.info("Loaded %d champions from Data Dragon (v%s)", len(id_map), version)
    return id_map, slug_map


def _detect_patch_from_ssr(ssr_data: dict) -> str | None:
    """Extract the current patch from a U.GG SSR_DATA response.

    The matchup CDN key embeds the patch:
        https://stats2.u.gg/lol/1.5/matchups/16_8/ranked_solo_5x5/64/1.5.0.json
                                                  ^^^^
    Returns e.g. "16.8" or None if undetectable.
    """
    for key in ssr_data:
        m = re.search(r"matchups/(\d+_\d+)/", key)
        if m:
            return m.group(1).replace("_", ".")
    return None


# ---------------------------------------------------------------------------
# Per-champion scraping
# ---------------------------------------------------------------------------

async def _fetch_matchup_data(
    client: httpx.AsyncClient,
    champion_name: str,
    role: str,
    url_slug: str,
    id_to_name: dict[int, str],
) -> tuple[list[dict], str | None]:
    """Fetch matchup rows for one champion+role from U.GG's SSR page.

    Returns:
        (rows, patch_string) where rows is a list of:
            {"enemy_name": str, "win_rate": float (0–1), "sample_size": int}
        patch_string is e.g. "16.8", detected from the CDN key.
        Both are empty/None on failure.
    """
    role_slug = _ROLE_SLUGS[role]
    url = _UGG_COUNTER_URL.format(slug=url_slug, role=role_slug)
    tier_key = _TARGET_TIER.format(role=role_slug)

    try:
        resp = await client.get(url, timeout=20)
        if resp.status_code != 200:
            logger.debug("U.GG returned HTTP %d for %s/%s", resp.status_code, champion_name, role)
            return [], None
    except httpx.HTTPError as exc:
        logger.warning("HTTP error fetching %s/%s: %s", champion_name, role, exc)
        return [], None

    # Extract window.__SSR_DATA__ from the HTML
    m = re.search(r"window\.__SSR_DATA__\s*=\s*(\{.*?\});?\s*\n", resp.text, re.DOTALL)
    if not m:
        logger.debug("No __SSR_DATA__ in page for %s/%s", champion_name, role)
        return [], None

    try:
        ssr_data: dict = json.loads(m.group(1))
    except json.JSONDecodeError:
        logger.warning("Failed to parse __SSR_DATA__ for %s/%s", champion_name, role)
        return [], None

    detected_patch = _detect_patch_from_ssr(ssr_data)

    # Find the matchup CDN key for this champion
    matchup_key = next(
        (k for k in ssr_data if "matchups" in k and "stats2.u.gg" in k),
        None,
    )
    if not matchup_key:
        logger.debug("No matchup key in SSR_DATA for %s/%s", champion_name, role)
        return [], detected_patch

    tier_data: dict | None = ssr_data[matchup_key].get("data", {}).get(tier_key)
    if not tier_data:
        logger.debug("No %r data for %s/%s", tier_key, champion_name, role)
        return [], detected_patch

    rows = []
    for counter in tier_data.get("counters", []):
        enemy_name = id_to_name.get(int(counter.get("champion_id", 0)))
        if not enemy_name:
            continue
        matches = int(counter.get("matches", 0))
        if matches < _MIN_GAMES:
            continue
        # win_rate in SSR_DATA is already a percentage (e.g. 49.12 = 49.12%)
        win_rate_pct = float(counter.get("win_rate", 50.0))
        rows.append({
            "enemy_name": enemy_name,
            "win_rate": win_rate_pct / 100.0,
            "sample_size": matches,
        })

    return rows, detected_patch


# ---------------------------------------------------------------------------
# Public scrape entry point
# ---------------------------------------------------------------------------

async def scrape(patch: str | None = None) -> None:
    """Full scrape: all champions × all roles from U.GG SSR pages.

    Args:
        patch: Patch string e.g. "16.8". Auto-detected from U.GG if None.
    """
    init_db()
    seed_power_spikes(patch or settings.current_patch)

    champions_file = Path(__file__).parent / "champions.json"
    our_champions: list[str] = [
        c["name"] for c in json.loads(champions_file.read_text())["champions"]
    ]

    async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True) as client:
        id_map, slug_map = await _fetch_champion_maps(client)
        id_to_name = {v: k for k, v in id_map.items()}

        updated_at = datetime.now(timezone.utc).isoformat()
        total_written = 0
        detected_patch: str | None = patch  # will be overwritten from first response

        total = len(our_champions)
        for i, champion_name in enumerate(our_champions, 1):
            url_slug = slug_map.get(champion_name)
            if url_slug is None:
                logger.warning("No Data Dragon slug for %r — skipping", champion_name)
                continue

            champ_rows = 0
            for role in _ROLE_SLUGS:
                rows, found_patch = await _fetch_matchup_data(
                    client, champion_name, role, url_slug, id_to_name
                )
                if found_patch and detected_patch is None:
                    detected_patch = found_patch
                    logger.info("Auto-detected patch: %s", detected_patch)

                current_patch = detected_patch or settings.current_patch
                for row in rows:
                    upsert_matchup(
                        ally=champion_name,
                        enemy=row["enemy_name"],
                        role=role,
                        win_rate=row["win_rate"],
                        sample_size=row["sample_size"],
                        patch=current_patch,
                        updated_at=updated_at,
                    )
                    total_written += 1
                    champ_rows += 1

                time.sleep(_SLEEP_BETWEEN_REQUESTS)

            logger.info("[%d/%d] %-20s — %d rows", i, total, champion_name, champ_rows)

    logger.info("Scrape complete — %d total matchup rows written", total_written)
    if detected_patch:
        logger.info("Patch: %s — update CURRENT_PATCH in .env to match", detected_patch)


# ---------------------------------------------------------------------------
# Default seeding (local dev — no network required)
# ---------------------------------------------------------------------------

def seed_defaults(patch: str | None = None) -> None:
    """Seed the DB with neutral 50% win rates for all champion pairs.

    Used for local development when U.GG data is not available.
    Provides a working baseline so the analysis engine can run without
    a real scrape.
    """
    patch = patch or settings.current_patch
    init_db()
    seed_power_spikes(patch)

    champions_file = Path(__file__).parent / "champions.json"
    champions: list[str] = [
        c["name"] for c in json.loads(champions_file.read_text())["champions"]
    ]

    updated_at = datetime.now(timezone.utc).isoformat()
    count = 0

    for ally in champions:
        for enemy in champions:
            if ally == enemy:
                continue
            for role in _ROLE_SLUGS:
                upsert_matchup(
                    ally=ally,
                    enemy=enemy,
                    role=role,
                    win_rate=0.50,
                    sample_size=100,
                    patch=patch,
                    updated_at=updated_at,
                )
                count += 1

    logger.info("Seeded %d default matchup rows (50%% win rate) for patch %s", count, patch)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if "--defaults" in sys.argv:
        print("Seeding default (50%) matchup data for local dev...")
        seed_defaults()
        print(f"Done. {matchup_count()} rows in DB.")
    else:
        patch_arg: str | None = None
        for arg in sys.argv[1:]:
            if arg.startswith("--patch="):
                patch_arg = arg.split("=", 1)[1]
        print(f"Scraping U.GG for patch {patch_arg or 'auto-detect'}...")
        asyncio.run(scrape(patch_arg))
        print(f"Done. {matchup_count()} rows in DB.")
