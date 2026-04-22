"""Startup patch check — downloads fresh matchup data when a new patch is live.

Called once during server startup. Compares the patch version stored in the
local SQLite database against the latest version advertised by the cloud API.
If they differ, downloads the new matchups.db atomically.

Behaviour on failure:
  - Network unreachable → warning logged, startup continues with stale data.
  - Download error → warning logged, stale file is left untouched.
  - Corrupt download → temp file is deleted, stale file is left untouched.

Never raises — this must not prevent the server from starting.
"""

import logging
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

import httpx

from config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(connect=5.0, read=300.0, write=5.0, pool=5.0)
_CHUNK_SIZE = 1024 * 256  # 256 KB


def get_local_patch() -> str | None:
    """Return the most recent patch string stored in the local matchups DB.

    Queries the matchups table for the latest updated_at row. Returns None
    if the DB doesn't exist yet or has no matchup rows.
    """
    db_path = Path(settings.db_path)
    if not db_path.exists():
        return None
    try:
        conn = sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT patch FROM matchups ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as exc:
        logger.warning("Could not read local patch from DB: %s", exc)
        return None


def check_and_update() -> bool:
    """Check the cloud API for a newer patch and download it if available.

    Returns:
        True if the database was replaced with a newer version.
        False if already up to date, cloud API is unreachable, or update failed.
    """
    if not settings.cloud_api_url:
        logger.debug("CLOUD_API_URL not set — skipping patch update check")
        return False

    url = settings.cloud_api_url.rstrip("/") + "/data/latest"

    try:
        resp = httpx.get(url, timeout=_TIMEOUT)
        resp.raise_for_status()
        version = resp.json()
    except Exception as exc:
        logger.warning("Could not reach cloud API for patch check (%s): %s", url, exc)
        return False

    server_patch: str = version.get("patch", "")
    db_url: str = version.get("db_url", "")
    row_count: int = version.get("row_count", 0)

    if not server_patch or not db_url:
        logger.warning("Cloud API returned invalid data version response: %s", version)
        return False

    local_patch = get_local_patch()
    if local_patch == server_patch:
        logger.info("Matchup data is up to date (patch %s)", server_patch)
        return False

    logger.info(
        "New patch available: local=%s server=%s — downloading %d rows from %s",
        local_patch or "none",
        server_patch,
        row_count,
        db_url,
    )

    return _download_and_install(db_url, server_patch)


def _download_and_install(db_url: str, patch: str) -> bool:
    """Stream the new DB file to a temp path, then atomically replace the live DB.

    Returns True on success, False on any failure.
    """
    dest = Path(settings.db_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".db",
            dir=dest.parent,
        ) as tmp:
            tmp_path = tmp.name
            with httpx.stream("GET", db_url, timeout=_TIMEOUT, follow_redirects=True) as stream:
                stream.raise_for_status()
                bytes_written = 0
                for chunk in stream.iter_bytes(chunk_size=_CHUNK_SIZE):
                    tmp.write(chunk)
                    bytes_written += len(chunk)

        # Basic sanity check — an empty or tiny file is corrupt
        if os.path.getsize(tmp_path) < 4096:
            raise ValueError(
                f"Downloaded file is suspiciously small ({os.path.getsize(tmp_path)} bytes)"
            )

        # Atomic replace: rename() is atomic on the same filesystem
        shutil.move(tmp_path, str(dest))
        tmp_path = None  # prevent cleanup in finally block

        logger.info(
            "Matchup DB updated to patch %s (%.1f MB)",
            patch,
            bytes_written / 1024 / 1024,
        )
        return True

    except Exception as exc:
        logger.error("Failed to download/install new matchup DB (patch %s): %s", patch, exc)
        return False

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
