"""CI script — upload a freshly scraped matchups.db to Supabase Storage
and notify the cloud API's POST /data/versions endpoint.

Usage (from repo root):
    python scripts/upload_matchups.py \
        --patch 16.9 \
        --db backend/data/junglecoach.db

Required environment variables (injected by GitHub Actions):
    SUPABASE_URL                 e.g. https://abc123.supabase.co
    SUPABASE_SERVICE_ROLE_KEY    service role key (never the anon key)
    CLOUD_API_URL                e.g. https://junglecoach.up.railway.app
    SCRAPER_SECRET               bearer token for POST /data/versions

Exit codes:
    0  success
    1  missing args / env vars
    2  upload failed
    3  cloud API notification failed
"""

import argparse
import os
import sys
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BUCKET = "matchup-data"
_TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=300.0, pool=10.0)


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"ERROR: environment variable {name!r} is not set", file=sys.stderr)
        sys.exit(1)
    return value


# ---------------------------------------------------------------------------
# Supabase Storage upload
# ---------------------------------------------------------------------------

def upload_to_storage(db_path: Path, patch: str) -> str:
    """Upload db_path to Supabase Storage and return the public URL.

    Uses the Supabase Storage REST API directly (no extra Python deps).
    The file is placed at: {bucket}/matchups-{patch}.db
    Any existing file with the same path is overwritten (upsert=true).

    Returns:
        The public URL of the uploaded file.
    """
    supabase_url = _require_env("SUPABASE_URL").rstrip("/")
    service_role_key = _require_env("SUPABASE_SERVICE_ROLE_KEY")

    object_path = f"matchups-{patch}.db"
    upload_url = f"{supabase_url}/storage/v1/object/{_BUCKET}/{object_path}"
    public_url = f"{supabase_url}/storage/v1/object/public/{_BUCKET}/{object_path}"

    print(f"Uploading {db_path} ({db_path.stat().st_size / 1024 / 1024:.1f} MB) → {upload_url}")

    with db_path.open("rb") as f:
        resp = httpx.put(
            upload_url,
            content=f,
            headers={
                "Authorization": f"Bearer {service_role_key}",
                "Content-Type": "application/octet-stream",
                "x-upsert": "true",
            },
            timeout=_TIMEOUT,
        )

    if resp.status_code not in (200, 201):
        print(
            f"ERROR: Supabase Storage upload failed — HTTP {resp.status_code}: {resp.text}",
            file=sys.stderr,
        )
        sys.exit(2)

    print(f"Upload complete. Public URL: {public_url}")
    return public_url


# ---------------------------------------------------------------------------
# Cloud API notification
# ---------------------------------------------------------------------------

def notify_cloud_api(patch: str, db_url: str, row_count: int) -> None:
    """Tell the cloud API about the new data version via POST /data/versions."""
    cloud_api_url = _require_env("CLOUD_API_URL").rstrip("/")
    scraper_secret = _require_env("SCRAPER_SECRET")

    endpoint = f"{cloud_api_url}/data/versions"
    print(f"Notifying cloud API: {endpoint}")

    resp = httpx.post(
        endpoint,
        json={"patch": patch, "db_url": db_url, "row_count": row_count},
        headers={"Authorization": f"Bearer {scraper_secret}"},
        timeout=30,
    )

    if resp.status_code not in (200, 204):
        print(
            f"ERROR: Cloud API notification failed — HTTP {resp.status_code}: {resp.text}",
            file=sys.stderr,
        )
        sys.exit(3)

    print(f"Cloud API notified. Patch {patch!r} is now live ({row_count} rows).")


# ---------------------------------------------------------------------------
# Row count helper
# ---------------------------------------------------------------------------

def count_rows(db_path: Path, patch: str) -> int:
    """Count matchup rows for the given patch in the local SQLite DB."""
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT COUNT(*) FROM matchups WHERE patch = ?", (patch,)
    ).fetchone()
    conn.close()
    return row[0] if row else 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Upload matchup DB and notify cloud API")
    parser.add_argument("--patch", required=True, help="Patch string, e.g. 16.9")
    parser.add_argument("--db", required=True, help="Path to the matchups.db file")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB file not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    row_count = count_rows(db_path, args.patch)
    if row_count == 0:
        print(
            f"WARNING: No matchup rows found for patch {args.patch!r}. "
            "Scrape may have failed — aborting upload.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Found {row_count} matchup rows for patch {args.patch!r}")

    public_url = upload_to_storage(db_path, args.patch)
    notify_cloud_api(args.patch, public_url, row_count)

    print("Done.")


if __name__ == "__main__":
    main()
