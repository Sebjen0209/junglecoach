"""Detects the current game phase by OCR-ing the in-game timer.

The timer is displayed at the top-centre of the screen as MM:SS (e.g. "14:32").
We OCR the timer region captured by screen.py and return one of:
  "early"  — minutes 0–13
  "mid"    — minutes 14–24
  "late"   — minutes 25+

Returns ("early", 0) if the timer cannot be parsed (safe default — early game
suggestions are the least likely to cause mistakes).
"""

import logging
import re

import pytesseract
from PIL import Image, ImageOps, ImageFilter

logger = logging.getLogger(__name__)

# Tesseract config optimised for a short numeric string (MM:SS)
_TESS_CONFIG = "--psm 7 -c tessedit_char_whitelist=0123456789:"

_PHASE_THRESHOLDS = {
    "early": (0, 13),    # inclusive range
    "mid":   (14, 24),
    "late":  (25, 9999),
}


def _preprocess_timer(img: Image.Image) -> Image.Image:
    """Prepare timer crop for Tesseract: grayscale, sharpen, threshold, upscale."""
    gray = ImageOps.grayscale(img)
    sharpened = gray.filter(ImageFilter.UnsharpMask(radius=1, percent=200, threshold=2))
    binary = sharpened.point(lambda p: 255 if p > 160 else 0)
    w, h = binary.size
    return binary.resize((w * 3, h * 3), Image.LANCZOS)


def _parse_timer_text(raw: str) -> int | None:
    """Extract total minutes from an OCR string like '14:32' or '14 32'.

    Returns the minute component as an integer, or None if parsing fails.
    """
    cleaned = raw.strip().replace(" ", ":")
    match = re.search(r"(\d{1,2})[:\-](\d{2})", cleaned)
    if match:
        return int(match.group(1))
    # Fallback: if only digits, try to interpret as MMSS
    digits = re.sub(r"\D", "", cleaned)
    if len(digits) >= 3:
        return int(digits[:-2])
    return None


def _minutes_to_phase(minutes: int) -> str:
    for phase, (lo, hi) in _PHASE_THRESHOLDS.items():
        if lo <= minutes <= hi:
            return phase
    return "late"


def detect_game_phase(timer_img: Image.Image) -> tuple[str, int]:
    """Detect the current game phase and minute from a timer region image.

    Args:
        timer_img: PIL Image of the timer region (captured by screen.py).

    Returns:
        (phase, game_minute) where phase is 'early'|'mid'|'late' and
        game_minute is the detected minute (0 if detection fails).
    """
    try:
        processed = _preprocess_timer(timer_img)
        raw = pytesseract.image_to_string(processed, config=_TESS_CONFIG)
        logger.debug("Timer OCR raw: %r", raw)

        minutes = _parse_timer_text(raw)
        if minutes is None:
            logger.warning("Could not parse timer from OCR output %r — defaulting to early", raw)
            return "early", 0

        phase = _minutes_to_phase(minutes)
        logger.debug("Game phase: %s (minute %d)", phase, minutes)
        return phase, minutes

    except pytesseract.TesseractNotFoundError:
        logger.error("Tesseract not found — defaulting to early phase")
        return "early", 0
    except Exception as exc:
        logger.error("Unexpected error in game phase detection: %s", exc)
        return "early", 0
