"""Tests for capture/ocr.py.

winocr is mocked throughout — these tests validate the pre-processing pipeline,
splitting logic, and text-cleaning, not the OCR engine itself.
"""

from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from capture.ocr import (
    ScoreboardOCRResult,
    _clean_ocr_text,
    extract_scoreboard,
    preprocess,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _blank_image(width: int = 200, height: int = 100, colour: int = 0) -> Image.Image:
    """Create a solid-colour grayscale test image."""
    return Image.new("RGB", (width, height), (colour, colour, colour))


class _MockOcrLine:
    """Minimal stand-in for a winocr OcrLine object."""
    def __init__(self, text: str) -> None:
        self.text = text


class _MockOcrResult:
    """Minimal stand-in for a winocr OcrResult object."""
    def __init__(self, text: str) -> None:
        self.lines = [_MockOcrLine(text)]


def _make_winocr_side_effect(ally: list[str], enemy: list[str]):
    """Return a side_effect list: first 5 calls = ally bands, next 5 = enemy bands."""
    return [_MockOcrResult(f"{name}\n") for name in ally + enemy]


# ---------------------------------------------------------------------------
# preprocess()
# ---------------------------------------------------------------------------

class TestPreprocess:
    def test_returns_grayscale_image(self):
        img = _blank_image(100, 50)
        result = preprocess(img)
        assert result.mode == "L"

    def test_upscales_by_factor_2(self):
        img = _blank_image(100, 50)
        result = preprocess(img)
        assert result.size == (200, 100)

    def test_bright_image_becomes_white(self):
        img = _blank_image(10, 10, colour=200)  # above threshold (140)
        result = preprocess(img)
        pixels = list(result.getdata())
        assert all(p == 255 for p in pixels)

    def test_dark_image_becomes_black(self):
        img = _blank_image(10, 10, colour=50)  # below threshold (140)
        result = preprocess(img)
        pixels = list(result.getdata())
        assert all(p == 0 for p in pixels)


# ---------------------------------------------------------------------------
# _clean_ocr_text()
# ---------------------------------------------------------------------------

class TestCleanOcrText:
    def test_strips_whitespace(self):
        assert _clean_ocr_text("  Riven  ") == "Riven"

    def test_collapses_multiple_spaces(self):
        assert _clean_ocr_text("Lee  Sin") == "Lee Sin"

    def test_removes_newlines(self):
        # \n is treated as whitespace → collapses to a single space
        assert _clean_ocr_text("Gang\nplank") == "Gang plank"

    def test_preserves_apostrophe(self):
        assert _clean_ocr_text("Kha'Zix") == "Kha'Zix"

    def test_preserves_dot(self):
        assert _clean_ocr_text("Dr. Mundo") == "Dr. Mundo"

    def test_removes_digits(self):
        assert _clean_ocr_text("R1ven") == "Rven"

    def test_removes_special_chars(self):
        assert _clean_ocr_text("@Riven!") == "Riven"

    def test_empty_string(self):
        assert _clean_ocr_text("") == ""

    def test_only_noise(self):
        assert _clean_ocr_text("123!!!") == ""


# ---------------------------------------------------------------------------
# extract_scoreboard() — mocked winocr
# ---------------------------------------------------------------------------

MOCK_CHAMPION_NAMES = ["Darius", "Lee Sin", "Zed", "Jinx", "Thresh"]
MOCK_ENEMY_NAMES = ["Garen", "Graves", "Orianna", "Caitlyn", "Lulu"]


class TestExtractScoreboard:
    @patch("capture.ocr.winocr.recognize_pil_sync")
    def test_returns_scoreboard_result(self, mock_ocr):
        mock_ocr.side_effect = _make_winocr_side_effect(
            MOCK_CHAMPION_NAMES, MOCK_ENEMY_NAMES
        )
        img = _blank_image(1340, 760)
        result = extract_scoreboard(img)
        assert isinstance(result, ScoreboardOCRResult)

    @patch("capture.ocr.winocr.recognize_pil_sync")
    def test_ally_names_match(self, mock_ocr):
        mock_ocr.side_effect = _make_winocr_side_effect(
            MOCK_CHAMPION_NAMES, MOCK_ENEMY_NAMES
        )
        result = extract_scoreboard(_blank_image(1340, 760))
        assert result.ally_raw == MOCK_CHAMPION_NAMES

    @patch("capture.ocr.winocr.recognize_pil_sync")
    def test_enemy_names_match(self, mock_ocr):
        mock_ocr.side_effect = _make_winocr_side_effect(
            MOCK_CHAMPION_NAMES, MOCK_ENEMY_NAMES
        )
        result = extract_scoreboard(_blank_image(1340, 760))
        assert result.enemy_raw == MOCK_ENEMY_NAMES

    @patch("capture.ocr.winocr.recognize_pil_sync")
    def test_returns_five_per_team(self, mock_ocr):
        mock_ocr.side_effect = _make_winocr_side_effect(
            MOCK_CHAMPION_NAMES, MOCK_ENEMY_NAMES
        )
        result = extract_scoreboard(_blank_image(1340, 760))
        assert len(result.ally_raw) == 5
        assert len(result.enemy_raw) == 5

    @patch("capture.ocr.winocr.recognize_pil_sync")
    def test_noisy_ocr_output_is_cleaned(self, mock_ocr):
        noisy = ["D4r1us\n", "Lee  Sin\n", "  Zed  \n", "J!nx\n", "Thresh!\n"]
        # Digits are stripped entirely (fuzzy matcher in champion_parser handles the rest)
        clean = ["Drus", "Lee Sin", "Zed", "Jnx", "Thresh"]
        mock_ocr.side_effect = _make_winocr_side_effect(noisy, MOCK_ENEMY_NAMES)
        result = extract_scoreboard(_blank_image(1340, 760))
        assert result.ally_raw == clean

    @patch("capture.ocr.winocr.recognize_pil_sync")
    def test_ocr_called_ten_times(self, mock_ocr):
        mock_ocr.side_effect = _make_winocr_side_effect(
            MOCK_CHAMPION_NAMES, MOCK_ENEMY_NAMES
        )
        extract_scoreboard(_blank_image(1340, 760))
        assert mock_ocr.call_count == 10
