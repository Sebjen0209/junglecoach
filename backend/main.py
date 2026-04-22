"""Entry point — starts the capture loop and FastAPI server together.

Run with:
    python main.py

Or for API-only mode (no capture loop, useful for testing):
    uvicorn server:app --reload --port 7429
"""

import logging
import os
import sys

# ---------------------------------------------------------------------------
# Frozen-app setup — must happen before any other imports so that the log
# file handler is attached before anything can crash.
# ---------------------------------------------------------------------------

if getattr(sys, "frozen", False):
    _exe_dir = os.path.dirname(sys.executable)

    # Fix CWD so relative paths like ./data/junglecoach.db resolve correctly.
    os.chdir(_exe_dir)

    # Ensure data directory exists — the matchup DB is downloaded here at runtime.
    os.makedirs(os.path.join(_exe_dir, "data"), exist_ok=True)

    # Write all logs to a file — there is no console window in the packaged app.
    # Use FileHandler directly because PyInstaller's bootstrap may have already
    # called logging.basicConfig, which would make a second call a no-op.
    _log_path = os.path.join(_exe_dir, "junglecoach.log")
    _fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    _fh = logging.FileHandler(_log_path, encoding="utf-8")
    _fh.setFormatter(_fmt)
    _root = logging.getLogger()
    _root.setLevel(logging.DEBUG)
    _root.handlers.clear()  # remove any handlers PyInstaller added
    _root.addHandler(_fh)
else:
    # Dev mode — log to stdout as normal.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

# ---------------------------------------------------------------------------
# Remaining imports (after logging is configured so any import errors are
# captured in the log file).
# ---------------------------------------------------------------------------

import uvicorn  # noqa: E402

from config import settings  # noqa: E402
from server import app  # noqa: E402  — import the object, not a string, so PyInstaller finds it

logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Starting JungleCoach backend on 127.0.0.1:%d", settings.api_port)
    try:
        # Pass the app object directly (not "server:app" string) — PyInstaller's
        # frozen import system handles `from server import app` correctly, but
        # uvicorn's string-based importer looks for a plain filesystem module and fails.
        # log_config=None prevents uvicorn from wiping our FileHandler.
        log_cfg = None if getattr(sys, "frozen", False) else {"version": 1, "disable_existing_loggers": False}
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=settings.api_port,
            log_level=settings.log_level.lower(),
            log_config=log_cfg,
        )
    except Exception:
        logger.exception("uvicorn crashed")


if __name__ == "__main__":
    main()
