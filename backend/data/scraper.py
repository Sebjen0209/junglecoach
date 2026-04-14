"""Scrapes champion matchup win-rate data from U.GG and writes it to SQLite.

Run manually after each LoL patch (~every 2 weeks):
    cd backend
    python data/scraper.py

U.GG exposes matchup stats via their internal stats CDN. The endpoint returns
per-champion matchup tables keyed by (ally, enemy, role). We map their
champion IDs to names using the Riot Data Dragon champion list.

Rate limiting: we sleep between requests to avoid hammering U.GG.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from config import settings
from data.db import init_db, upsert_matchup, seed_power_spikes, matchup_count

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# U.GG API constants
# ---------------------------------------------------------------------------

# Riot Data Dragon — maps champion names to IDs (used to cross-reference U.GG)
_DDRAGON_URL = "https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
_DDRAGON_VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"

# U.GG stats CDN endpoint for matchup data
# Tier 2 = Platinum+ (default for most stat sites)
_UGG_MATCHUP_URL = (
    "https://stats2.u.gg/lol/1.5/matchup_data/world/{patch}/silver_plus/{champ_id}/{role}/1.json"
)

# Role slug mapping (U.GG uses numeric IDs)
_ROLE_IDS = {
    "top": 4,
    "jungle": 1,
    "mid": 5,
    "bot": 3,
    "support": 2,
}

_SLEEP_BETWEEN_REQUESTS = 0.5  # seconds


# ---------------------------------------------------------------------------
# Data Dragon helpers
# ---------------------------------------------------------------------------

async def _fetch_latest_patch(client: httpx.AsyncClient) -> str:
    """Return the latest available Data Dragon version string."""
    resp = await client.get(_DDRAGON_VERSIONS_URL, timeout=10)
    resp.raise_for_status()
    versions = resp.json()
    return versions[0]  # most recent


async def _fetch_champion_id_map(client: httpx.AsyncClient, version: str) -> dict[str, int]:
    """Return {canonical_name: champion_int_id} from Data Dragon."""
    resp = await client.get(_DDRAGON_URL.format(version=version), timeout=10)
    resp.raise_for_status()
    data = resp.json()
    # Data Dragon uses string keys and 'key' field holds the numeric ID
    return {info["name"]: int(info["key"]) for info in data["data"].values()}


# ---------------------------------------------------------------------------
# U.GG scraper
# ---------------------------------------------------------------------------

async def _fetch_matchup_data(
    client: httpx.AsyncClient,
    champ_id: int,
    role: str,
    patch: str,
) -> list[dict] | None:
    """Fetch raw matchup rows for one champion+role from U.GG.

    Returns a list of dicts with keys: enemy_id, win_rate, sample_size.
    Returns None if the request fails (non-fatal — we skip the champion).
    """
    # U.GG uses a condensed patch format: "14_6" → "14.6"
    patch_slug = patch.replace(".", "_")
    url = _UGG_MATCHUP_URL.format(
        patch=patch_slug, champ_id=champ_id, role=_ROLE_IDS[role]
    )
    try:
        resp = await client.get(url, timeout=15)
        if resp.status_code == 404:
            logger.debug("No U.GG data for champ_id=%d role=%s", champ_id, role)
            return None
        resp.raise_for_status()
        raw = resp.json()
        # U.GG response structure: list of [enemy_id, wins, games, ...]
        rows = []
        for entry in raw.get("data", []):
            if len(entry) < 3:
                continue
            enemy_id, wins, games = entry[0], entry[1], entry[2]
            if games < 50:  # skip tiny sample sizes
                continue
            rows.append({
                "enemy_id": enemy_id,
                "win_rate": wins / games,
                "sample_size": games,
            })
        return rows
    except httpx.HTTPError as exc:
        logger.warning("HTTP error fetching champ_id=%d role=%s: %s", champ_id, role, exc)
        return None


async def scrape(patch: str | None = None) -> None:
    """Full scrape: fetch all champion matchup data for the given patch.

    Args:
        patch: Patch string e.g. '14.6'. Defaults to settings.current_patch.
    """
    patch = patch or settings.current_patch
    logger.info("Starting U.GG scrape for patch %s", patch)

    init_db()
    seed_power_spikes(patch)

    # Load our champion list
    champions_file = Path(__file__).parent / "champions.json"
    our_champions: list[str] = [
        c["name"] for c in json.loads(champions_file.read_text())["champions"]
    ]

    async with httpx.AsyncClient(
        headers={"User-Agent": "JungleCoach/0.1 (personal tool)"},
        follow_redirects=True,
    ) as client:
        logger.info("Fetching Data Dragon champion ID map...")
        ddragon_version = await _fetch_latest_patch(client)
        id_map = await _fetch_champion_id_map(client, ddragon_version)

        updated_at = datetime.now(timezone.utc).isoformat()
        total_written = 0

        for ally_name in our_champions:
            ally_id = id_map.get(ally_name)
            if ally_id is None:
                logger.warning("No Data Dragon ID for %r — skipping", ally_name)
                continue

            for role in _ROLE_IDS:
                rows = await _fetch_matchup_data(client, ally_id, role, patch)
                if not rows:
                    continue

                # Build reverse map: id → name (for enemy lookup)
                id_to_name = {v: k for k, v in id_map.items()}

                for row in rows:
                    enemy_name = id_to_name.get(row["enemy_id"])
                    if not enemy_name:
                        continue
                    upsert_matchup(
                        ally=ally_name,
                        enemy=enemy_name,
                        role=role,
                        win_rate=row["win_rate"],
                        sample_size=row["sample_size"],
                        patch=patch,
                        updated_at=updated_at,
                    )
                    total_written += 1

                time.sleep(_SLEEP_BETWEEN_REQUESTS)

        logger.info("Scrape complete — %d matchup rows written", total_written)


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
            for role in _ROLE_IDS:
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

    logger.info("Seeded %d default matchup rows (50%% win rate)", count)


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
        print(f"Scraping U.GG for patch {settings.current_patch}...")
        asyncio.run(scrape())
        print(f"Done. {matchup_count()} rows in DB.")
