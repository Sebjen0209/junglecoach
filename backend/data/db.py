"""SQLite database access layer.

All reads and writes go through this module. The schema matches data-schema.md.
Call init_db() once at startup to ensure tables exist.
"""

import json
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)

_POWER_SPIKES_FILE = Path(__file__).parent / "power_spikes.json"


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

@contextmanager
def _get_conn():
    """Yield a SQLite connection, closing it on exit."""
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create tables if they don't exist. Safe to call on every startup."""
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)

    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS matchups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ally_champion TEXT NOT NULL,
                enemy_champion TEXT NOT NULL,
                role TEXT NOT NULL,
                win_rate REAL NOT NULL,
                sample_size INTEGER NOT NULL,
                patch TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_matchup
                ON matchups(ally_champion, enemy_champion, role, patch);

            CREATE TABLE IF NOT EXISTS power_spikes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                champion TEXT NOT NULL UNIQUE,
                early_strength REAL NOT NULL,
                mid_strength REAL NOT NULL,
                late_strength REAL NOT NULL,
                patch TEXT NOT NULL
            );
        """)
    logger.info("Database initialised at %s", settings.db_path)


# ---------------------------------------------------------------------------
# Matchup queries
# ---------------------------------------------------------------------------

def get_matchup_winrate(
    ally: str,
    enemy: str,
    role: str,
    patch: str | None = None,
) -> float | None:
    """Return ally's win rate vs enemy in the given role, or None if unknown.

    Tries the requested patch first, then falls back to any patch for that
    pair/role so older data is better than nothing.
    """
    patch = patch or settings.current_patch

    with _get_conn() as conn:
        # Try exact patch first
        row = conn.execute(
            "SELECT win_rate FROM matchups "
            "WHERE ally_champion=? AND enemy_champion=? AND role=? AND patch=?",
            (ally, enemy, role, patch),
        ).fetchone()
        if row:
            return row["win_rate"]

        # Fallback: any patch, most recent first
        row = conn.execute(
            "SELECT win_rate FROM matchups "
            "WHERE ally_champion=? AND enemy_champion=? AND role=? "
            "ORDER BY updated_at DESC LIMIT 1",
            (ally, enemy, role),
        ).fetchone()
        return row["win_rate"] if row else None


def upsert_matchup(
    ally: str,
    enemy: str,
    role: str,
    win_rate: float,
    sample_size: int,
    patch: str,
    updated_at: str,
) -> None:
    """Insert or update a matchup row."""
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO matchups
                (ally_champion, enemy_champion, role, win_rate, sample_size, patch, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ally_champion, enemy_champion, role, patch)
            DO UPDATE SET
                win_rate=excluded.win_rate,
                sample_size=excluded.sample_size,
                updated_at=excluded.updated_at
            """,
            (ally, enemy, role, win_rate, sample_size, patch, updated_at),
        )


def matchup_count(patch: str | None = None) -> int:
    """Return number of matchup rows, optionally filtered by patch."""
    patch = patch or settings.current_patch
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM matchups WHERE patch=?", (patch,)
        ).fetchone()
        return row[0]


# ---------------------------------------------------------------------------
# Power spike queries
# ---------------------------------------------------------------------------

def get_phase_strength(champion: str, phase: str) -> float:
    """Return a champion's strength rating (0–1) for the given game phase.

    Falls back to power_spikes.json if the champion isn't in the DB,
    and to 0.5 if it's not in the JSON either.
    """
    col = {"early": "early_strength", "mid": "mid_strength", "late": "late_strength"}.get(phase)
    if not col:
        raise ValueError(f"Invalid phase: {phase!r}. Must be early/mid/late.")

    with _get_conn() as conn:
        row = conn.execute(
            f"SELECT {col} FROM power_spikes WHERE champion=?", (champion,)
        ).fetchone()
        if row:
            return row[col]

    # Fallback: read from JSON
    try:
        data = json.loads(_POWER_SPIKES_FILE.read_text(encoding="utf-8"))
        entry = data["champions"].get(champion)
        if entry:
            return entry[phase]
    except Exception as exc:
        logger.warning("Could not read power_spikes.json: %s", exc)

    logger.warning("No power spike data for %r (phase=%s) — defaulting to 0.5", champion, phase)
    return 0.5


def seed_power_spikes(patch: str | None = None) -> int:
    """Load power_spikes.json into the DB. Returns number of rows written."""
    patch = patch or settings.current_patch
    data = json.loads(_POWER_SPIKES_FILE.read_text(encoding="utf-8"))
    count = 0
    with _get_conn() as conn:
        for champion, spikes in data["champions"].items():
            conn.execute(
                """
                INSERT INTO power_spikes
                    (champion, early_strength, mid_strength, late_strength, patch)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(champion) DO UPDATE SET
                    early_strength=excluded.early_strength,
                    mid_strength=excluded.mid_strength,
                    late_strength=excluded.late_strength,
                    patch=excluded.patch
                """,
                (champion, spikes["early"], spikes["mid"], spikes["late"], patch),
            )
            count += 1
    logger.info("Seeded %d power spike rows (patch %s)", count, patch)
    return count
