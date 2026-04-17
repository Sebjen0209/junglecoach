"""Tests for analysis/experience.py."""

import pytest

from analysis.experience import experience_delta, _autofill_penalty
from models import PlayerProfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _profile(
    mastery_level: int = 5,
    mastery_points: int = 200_000,
    rank_tier: int = 4,      # Gold
    rank_name: str = "GOLD",
    summoner_name: str = "Alice",
    champion_name: str = "Riven",
) -> PlayerProfile:
    return PlayerProfile(
        summoner_name=summoner_name,
        champion_name=champion_name,
        mastery_level=mastery_level,
        mastery_points=mastery_points,
        rank_tier=rank_tier,
        rank_name=rank_name,
    )


# ---------------------------------------------------------------------------
# experience_delta
# ---------------------------------------------------------------------------

class TestExperienceDelta:
    def test_both_none_returns_zero(self):
        assert experience_delta(None, None) == 0.0

    def test_equal_mastery_returns_zero(self):
        ally = _profile(mastery_level=5)
        enemy = _profile(mastery_level=5)
        assert experience_delta(ally, enemy) == pytest.approx(0.0)

    def test_higher_ally_mastery_positive_delta(self):
        ally = _profile(mastery_level=7)
        enemy = _profile(mastery_level=4)
        delta = experience_delta(ally, enemy)
        assert delta > 0

    def test_lower_ally_mastery_negative_delta(self):
        ally = _profile(mastery_level=2)
        enemy = _profile(mastery_level=6)
        delta = experience_delta(ally, enemy)
        assert delta < 0

    def test_max_mastery_diff_stays_within_cap(self):
        # Mastery 7 vs Mastery 1 = 6 levels × 0.01 = +0.06 (within ±0.10 cap)
        ally = _profile(mastery_level=7)
        enemy = _profile(mastery_level=1)
        assert experience_delta(ally, enemy) == pytest.approx(0.06)

    def test_total_delta_never_exceeds_cap(self):
        # Mastery 7 + autofill enemy → should not exceed 0.10
        ally = _profile(mastery_level=7)
        enemy = _profile(mastery_level=1)
        delta = experience_delta(ally, enemy)
        assert abs(delta) <= 0.10

    def test_ally_none_uses_midpoint_assumption(self):
        # ally unknown → assumed level 4; enemy level 4 → delta = 0
        enemy = _profile(mastery_level=4)
        assert experience_delta(None, enemy) == pytest.approx(0.0)

    def test_enemy_none_uses_midpoint_assumption(self):
        # ally level 7, enemy unknown → assumed level 4 → delta = +0.03
        ally = _profile(mastery_level=7)
        assert experience_delta(ally, None) == pytest.approx(0.03)


# ---------------------------------------------------------------------------
# _autofill_penalty
# ---------------------------------------------------------------------------

class TestAutofillPenalty:
    def test_high_rank_low_mastery_is_penalised(self):
        # Platinum (tier=5) with Mastery 1 and 5k points = clearly autofilled
        p = _profile(rank_tier=5, rank_name="PLATINUM", mastery_level=1, mastery_points=5_000)
        assert _autofill_penalty(p) == pytest.approx(-0.04)

    def test_high_rank_high_mastery_no_penalty(self):
        p = _profile(rank_tier=6, rank_name="EMERALD", mastery_level=6, mastery_points=300_000)
        assert _autofill_penalty(p) == 0.0

    def test_low_rank_low_mastery_no_penalty(self):
        # Bronze player with low mastery is just new — not autofilled
        p = _profile(rank_tier=2, rank_name="BRONZE", mastery_level=1, mastery_points=3_000)
        assert _autofill_penalty(p) == 0.0

    def test_borderline_mastery_points_no_penalty(self):
        # Exactly at the threshold — should NOT trigger penalty
        p = _profile(rank_tier=5, mastery_level=2, mastery_points=10_000)
        assert _autofill_penalty(p) == 0.0

    def test_unranked_no_penalty(self):
        p = _profile(rank_tier=0, rank_name="UNRANKED", mastery_level=1, mastery_points=1_000)
        assert _autofill_penalty(p) == 0.0

    def test_diamond_autofill_is_penalised(self):
        p = _profile(rank_tier=7, rank_name="DIAMOND", mastery_level=2, mastery_points=8_000)
        assert _autofill_penalty(p) == pytest.approx(-0.04)
