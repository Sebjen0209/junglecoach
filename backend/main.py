"""Entry point — starts the capture loop and FastAPI server together.

Run with:
    python main.py

Or for API-only mode (no capture loop, useful for testing):
    uvicorn server:app --reload --port 7429
"""

import logging
import sys

import uvicorn

from config import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Starting JungleCoach backend on 127.0.0.1:%d", settings.api_port)
    uvicorn.run(
        "server:app",
        host="127.0.0.1",
        port=settings.api_port,
        log_level=settings.log_level.lower(),
        # reload=False in production — use uvicorn directly with --reload for dev
    )


if __name__ == "__main__":
    main()
