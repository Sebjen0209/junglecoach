"""Game phase detection.

Primary path — game_time_to_phase(seconds):
    Converts the float game time from the Riot Live Client Data API directly
    to a phase string and minute count. No image processing, no dependencies
    beyond the standard library.

Legacy path — detect_game_phase(timer_img):
    OCR-based detection from a screenshot of the in-game timer. Kept for
    offline testing and development without a running game. Requires pytesseract
    + the Tesseract binary (installed separately, not in requirements.txt).

Phase thresholds:
  "early"  — minutes  0–13
  "mid"    — minutes 14–24
  "late"   — minutes 25+
"""

import logging
import re

from PIL import Image, ImageOps, ImageFilter

logger = logging.getLogger(__name__)

_PHASE_THRESHOLDS: dict[str, tuple[int, int]] = {
    "early": (0, 13),
    "mid":   (14, 24),
    "late":  (25, 9999),
}


def _minutes_to_phase(minutes: int) -> str:
    for phase, (lo, hi) in _PHASE_THRESHOLDS.items():
        if lo <= minutes <= hi:
            return phase
    return "late"


# ---------------------------------------------------------------------------
# Primary path — no OCR, no external dependencies
# ---------------------------------------------------------------------------

def game_time_to_phase(seconds: float) -> tuple[str, int]:
    """Convert raw game time in seconds to a phase and minute count.

    This is the primary phase-detection function. It uses the gameTime float
    returned by the Riot Live Client Data API — no screen capture required.

    Args:
        seconds: Game time in seconds (e.g. 845.3 → 14 minutes → "mid").

    Returns:
        (phase, game_minute) where phase is 'early' | 'mid' | 'late'.
    """
    minutes = int(seconds // 60)
    return _minutes_to_phase(minutes), minutes


# ---------------------------------------------------------------------------
# Legacy OCR path — kept for reference and offline development.
# Requires: pip install pytesseract  +  Tesseract binary on PATH.
# Not used by the main data pipeline.
# ---------------------------------------------------------------------------

_TESS_CONFIG = "--psm 7 -c tessedit_char_whitelist=0123456789:"


def _preprocess_timer(img: Image.Image) -> Image.Image:
    """Prepare timer crop for Tesseract: grayscale, sharpen, threshold, upscale."""
    gray = ImageOps.grayscale(img)
    sharpened = gray.filter(ImageFilter.UnsharpMask(radius=1, percent=200, threshold=2))
    binary = sharpened.point(lambda p: 255 if p > 160 else 0)
    w, h = binary.size
    return binary.resize((w * 3, h * 3), Image.LANCZOS)


def _parse_timer_text(raw: str) -> int | None:
    """Extract total minutes from an OCR string like '14:32' or '14 32'."""
    cleaned = raw.strip().replace(" ", ":")
    match = re.search(r"(\d{1,2})[:\-](\d{2})", cleaned)
    if match:
        return int(match.group(1))
    digits = re.sub(r"\D", "", cleaned)
    if len(digits) >= 3:
        return int(digits[:-2])
    return None


def detect_game_phase(timer_img: Image.Image) -> tuple[str, int]:
    """Detect game phase from a timer region screenshot (OCR-based, legacy).

    Prefer game_time_to_phase() when a live game is running. Use this only
    for offline testing with pre-captured screenshots.

    Args:
        timer_img: PIL Image of the timer region from the game screen.

    Returns:
        (phase, game_minute). Returns ('early', 0) if detection fails.
    """
    try:
        import pytesseract  # lazy — not in requirements.txt, installed separately
    except ImportError:
        logger.error(
            "pytesseract is not installed. "
            "Use game_time_to_phase() for the Live Client API path."
        )
        return "early", 0

    try:
        processed = _preprocess_timer(timer_img)
        raw = pytesseract.image_to_string(processed, config=_TESS_CONFIG)
        logger.debug("Timer OCR raw: %r", raw)

        minutes = _parse_timer_text(raw)
        if minutes is None:
            logger.warning("Could not parse timer %r — defaulting to early", raw)
            return "early", 0

        phase = _minutes_to_phase(minutes)
        logger.debug("Game phase: %s (minute %d)", phase, minutes)
        return phase, minutes

    except Exception as exc:
        logger.error("Unexpected error in OCR phase detection: %s", exc)
        return "early", 0
