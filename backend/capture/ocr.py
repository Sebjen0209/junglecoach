"""OCR wrapper for extracting champion names from the TAB scoreboard.

Pipeline per capture:
  1. Receive a scoreboard PIL Image from screen.py
  2. Pre-process: grayscale → threshold → upscale (improves Tesseract accuracy)
  3. Run pytesseract on the image
  4. Split raw text into two team rows (ally / enemy)
  5. Return two lists of 5 raw strings each (one per lane)

The caller (champion_parser.py) is responsible for fuzzy-matching the raw
strings to canonical champion names.
"""

import logging
import re
from dataclasses import dataclass

import pytesseract
from PIL import Image, ImageFilter, ImageOps

logger = logging.getLogger(__name__)

# Tesseract config: single-column text, digits+letters only (champion names
# never have punctuation in the scoreboard font). Page segmentation mode 6
# treats the image as a single uniform block of text.
_TESS_CONFIG = "--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz' ."

# Upscale factor applied before OCR — Tesseract accuracy improves significantly
# when characters are at least 30px tall.
_UPSCALE_FACTOR = 2

# The scoreboard has two halves: ally team (left) and enemy team (right).
# These x-axis split ratios are approximate for 1080p after our crop.
# Left half = ally, right half = enemy.
_ALLY_X_RATIO = (0.0, 0.5)
_ENEMY_X_RATIO = (0.5, 1.0)

# Each team row has 5 champions stacked roughly equally in y.
# We split into 5 vertical bands to read each champion independently.
_NUM_CHAMPIONS = 5


@dataclass
class ScoreboardOCRResult:
    """Raw OCR output for both teams. Strings are not yet fuzzy-matched."""

    ally_raw: list[str]   # 5 strings: [top, jungle, mid, bot, support]
    enemy_raw: list[str]  # 5 strings: [top, jungle, mid, bot, support]


def preprocess(img: Image.Image) -> Image.Image:
    """Prepare a scoreboard image for Tesseract.

    Steps:
    - Convert to grayscale
    - Apply unsharp mask to sharpen edges
    - Binarise with a fixed threshold (champion names are bright on dark BG)
    - Upscale to improve character recognition
    """
    gray = ImageOps.grayscale(img)
    sharpened = gray.filter(ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3))
    # Threshold: pixels > 140 → white (text), else → black (background)
    binary = sharpened.point(lambda p: 255 if p > 140 else 0)
    w, h = binary.size
    upscaled = binary.resize((w * _UPSCALE_FACTOR, h * _UPSCALE_FACTOR), Image.LANCZOS)
    return upscaled


def _crop_half(img: Image.Image, x_ratio: tuple[float, float]) -> Image.Image:
    """Crop img to a horizontal band defined by x_ratio (0.0–1.0)."""
    w, h = img.size
    left = int(w * x_ratio[0])
    right = int(w * x_ratio[1])
    return img.crop((left, 0, right, h))


def _extract_champion_names_from_half(half_img: Image.Image) -> list[str]:
    """Split a team half-image into 5 rows and OCR each one.

    Returns a list of 5 raw strings (may be empty strings if OCR fails).
    """
    w, h = half_img.size
    band_height = h // _NUM_CHAMPIONS
    names: list[str] = []

    for i in range(_NUM_CHAMPIONS):
        top = i * band_height
        bottom = (i + 1) * band_height if i < _NUM_CHAMPIONS - 1 else h
        band = half_img.crop((0, top, w, bottom))
        processed = preprocess(band)
        raw = pytesseract.image_to_string(processed, config=_TESS_CONFIG)
        cleaned = _clean_ocr_text(raw)
        names.append(cleaned)
        logger.debug("OCR band %d → %r", i, cleaned)

    return names


def _clean_ocr_text(raw: str) -> str:
    """Strip noise from a single OCR line.

    Removes newlines, multiple spaces, and leading/trailing whitespace.
    Preserves apostrophes (Cho'Gath, Kha'Zix) and dots (Dr. Mundo).
    """
    # Collapse whitespace
    text = re.sub(r"\s+", " ", raw)
    # Remove any character that isn't a letter, space, apostrophe, or dot
    text = re.sub(r"[^A-Za-z '.]+", "", text)
    return text.strip()


def extract_scoreboard(scoreboard_img: Image.Image) -> ScoreboardOCRResult:
    """Run OCR on a full scoreboard image and return raw champion name lists.

    Args:
        scoreboard_img: PIL Image of the TAB scoreboard region (already
                        cropped by screen.py).

    Returns:
        ScoreboardOCRResult with ally_raw and enemy_raw lists of 5 strings.

    Raises:
        RuntimeError: If Tesseract is not installed or cannot be found.
    """
    try:
        ally_half = _crop_half(scoreboard_img, _ALLY_X_RATIO)
        enemy_half = _crop_half(scoreboard_img, _ENEMY_X_RATIO)

        ally_raw = _extract_champion_names_from_half(ally_half)
        enemy_raw = _extract_champion_names_from_half(enemy_half)

        logger.debug("OCR ally: %s", ally_raw)
        logger.debug("OCR enemy: %s", enemy_raw)

        return ScoreboardOCRResult(ally_raw=ally_raw, enemy_raw=enemy_raw)

    except pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError(
            "Tesseract is not installed or not on PATH. "
            "Install from https://github.com/UB-Mannheim/tesseract/wiki"
        ) from exc
