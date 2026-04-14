"""Tests for capture/champion_parser.py."""

import pytest
from capture.champion_parser import (
    parse_champion_name,
    parse_scoreboard_row,
    get_all_champion_names,
)


class TestParseChampionName:
    def test_exact_match(self):
        assert parse_champion_name("Riven") == "Riven"

    def test_case_insensitive(self):
        assert parse_champion_name("riven") == "Riven"
        assert parse_champion_name("RIVEN") == "Riven"

    def test_known_alias(self):
        # 'Gangplsnk' is a documented OCR alias for Gangplank
        assert parse_champion_name("Gangplsnk") == "Gangplank"

    def test_fuzzy_match_typo(self):
        # Close enough to fuzzy-match
        assert parse_champion_name("Gangplank") == "Gangplank"

    def test_space_trimmed(self):
        assert parse_champion_name("  Zed  ") == "Zed"

    def test_champion_with_spaces(self):
        assert parse_champion_name("Lee Sin") == "Lee Sin"

    def test_champion_shorthand_alias(self):
        # 'MF' is listed as alias for Miss Fortune
        assert parse_champion_name("MF") == "Miss Fortune"

    def test_champion_apostrophe(self):
        assert parse_champion_name("Kha'Zix") == "Kha'Zix"

    def test_unrecognised_raises(self):
        with pytest.raises(ValueError, match="Could not match"):
            parse_champion_name("xXxNotAChampxXx", cutoff=0.9)

    def test_cutoff_too_high_raises(self):
        # 'Rivn' might not reach 0.95 similarity
        with pytest.raises(ValueError):
            parse_champion_name("Rivn", cutoff=0.95)


class TestParseScoreboardRow:
    def test_full_row(self):
        row = ["Darius", "Lee Sin", "Zed", "Jinx", "Thresh"]
        result = parse_scoreboard_row(row)
        assert result == {
            "top": "Darius",
            "jungle": "Lee Sin",
            "mid": "Zed",
            "bot": "Jinx",
            "support": "Thresh",
        }

    def test_wrong_length_raises(self):
        with pytest.raises(ValueError, match="Expected 5"):
            parse_scoreboard_row(["Darius", "Lee Sin"])

    def test_aliases_in_row(self):
        # Gangplsnk is OCR alias → Gangplank
        row = ["Gangplsnk", "Khazix", "Zed", "Jinx", "Thresh"]
        result = parse_scoreboard_row(row)
        assert result["top"] == "Gangplank"


class TestGetAllChampionNames:
    def test_returns_sorted_list(self):
        names = get_all_champion_names()
        assert names == sorted(names)

    def test_contains_known_champions(self):
        names = get_all_champion_names()
        for champ in ["Riven", "Gangplank", "Lee Sin", "Miss Fortune", "Kha'Zix"]:
            assert champ in names

    def test_no_duplicates(self):
        names = get_all_champion_names()
        assert len(names) == len(set(names))
