"""CI helper — check whether Data Dragon has a newer patch than the cloud API.

Exits 0 if a new patch is available (sets GITHUB_OUTPUT for the workflow).
Exits 1 if the data is already up to date or the check fails.

Usage:
    python scripts/check_patch.py

Required environment variables:
    CLOUD_API_URL    e.g. https://junglecoach.up.railway.app

Writes to GITHUB_OUTPUT:
    new_patch_available=true|false
    latest_patch=16.9
"""

import os
import sys

import httpx

_DDRAGON_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
_TIMEOUT = 15


def _github_output(key: str, value: str) -> None:
    """Write a key=value pair to $GITHUB_OUTPUT (or stdout if not in CI)."""
    output_file = os.environ.get("GITHUB_OUTPUT")
    line = f"{key}={value}\n"
    if output_file:
        with open(output_file, "a", encoding="utf-8") as f:
            f.write(line)
    else:
        print(f"[output] {line}", end="")


def get_ddragon_patch() -> str:
    """Fetch the latest patch version from Riot's Data Dragon CDN."""
    resp = httpx.get(_DDRAGON_URL, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()[0]  # e.g. "16.9.1" — we'll normalise to major.minor


def normalise(version: str) -> str:
    """Convert '16.9.1' → '16.9' (major.minor only, matching our patch keys)."""
    parts = version.split(".")
    return f"{parts[0]}.{parts[1]}"


def get_cloud_patch() -> str | None:
    """Fetch the current patch from the cloud API. Returns None if unavailable."""
    cloud_url = os.environ.get("CLOUD_API_URL", "").rstrip("/")
    if not cloud_url:
        print("CLOUD_API_URL not set — treating as 'no current version'")
        return None
    try:
        resp = httpx.get(f"{cloud_url}/data/latest", timeout=_TIMEOUT)
        if resp.status_code == 503:
            return None  # no data uploaded yet
        resp.raise_for_status()
        return resp.json().get("patch")
    except Exception as exc:
        print(f"WARNING: could not reach cloud API: {exc}", file=sys.stderr)
        return None


def main() -> None:
    try:
        raw_patch = get_ddragon_patch()
    except Exception as exc:
        print(f"ERROR: could not fetch Data Dragon versions: {exc}", file=sys.stderr)
        sys.exit(1)

    latest_patch = normalise(raw_patch)
    cloud_patch = get_cloud_patch()

    print(f"Data Dragon latest : {latest_patch}")
    print(f"Cloud API current  : {cloud_patch or 'none'}")

    _github_output("latest_patch", latest_patch)

    if cloud_patch == latest_patch:
        print("Already up to date — nothing to do.")
        _github_output("new_patch_available", "false")
        sys.exit(0)
    else:
        print(f"New patch detected: {cloud_patch!r} → {latest_patch!r}")
        _github_output("new_patch_available", "true")
        sys.exit(0)


if __name__ == "__main__":
    main()
