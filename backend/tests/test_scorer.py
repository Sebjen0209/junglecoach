"""Tests for analysis/scorer.py."""

import pytest
from models import GameState, LaneState
from analysis.scorer import score_lane, score_to_priority, score_all_lanes


def _make_lane(
    ally="Riven",
    enemy="Gangplank",
    winrate=0.58,
    phase_strength=0.8,
    cs_diff=0,
    kill_pressure=False,
) -> LaneState:
    return LaneState(
        ally_champion=ally,
        enemy_champion=enemy,
        matchup_winrate=winrate,
        ally_phase_strength=phase_strength,
        cs_diff=cs_diff,
        ally_kill_pressure=kill_pressure,
    )


def _make_game_state(top=None, mid=None, bot=None) -> GameState:
    return GameState(
        game_minute=10,
        game_phase="early",
        patch="14.6",
        top=top or _make_lane(),
        mid=mid or _make_lane("Zed", "Azir", 0.54),
        bot=bot or _make_lane("Jinx", "Caitlyn", 0.50),
    )


# ---------------------------------------------------------------------------
# score_lane()
# ---------------------------------------------------------------------------

class TestScoreLane:
    def test_favourable_matchup_gives_positive_score(self):
        lane = _make_lane(winrate=0.60, phase_strength=0.8)
        # counter_score = (0.60 - 0.50) * 200 = 20
        # phase = 20 * 0.8 = 16
        assert score_lane(lane) == pytest.approx(16.0)

    def test_even_matchup_gives_zero_counter_score(self):
        lane = _make_lane(winrate=0.50, phase_strength=0.8, cs_diff=0, kill_pressure=False)
        assert score_lane(lane) == pytest.approx(0.0)

    def test_unfavourable_matchup_gives_negative_score(self):
        lane = _make_lane(winrate=0.44, phase_strength=0.8)
        # counter_score = (0.44 - 0.50) * 200 = -12
        # phase = -12 * 0.8 = -9.6
        assert score_lane(lane) == pytest.approx(-9.6)

    def test_kill_pressure_adds_15(self):
        base = score_lane(_make_lane(winrate=0.50, phase_strength=0.5, kill_pressure=False))
        with_pressure = score_lane(_make_lane(winrate=0.50, phase_strength=0.5, kill_pressure=True))
        assert with_pressure - base == pytest.approx(15.0)

    def test_cs_diff_positive_adds_bonus(self):
        no_cs = score_lane(_make_lane(winrate=0.50, phase_strength=0.5, cs_diff=0))
        with_cs = score_lane(_make_lane(winrate=0.50, phase_strength=0.5, cs_diff=20))
        assert with_cs - no_cs == pytest.approx(10.0)

    def test_cs_bonus_capped_at_20(self):
        big_cs = score_lane(_make_lane(winrate=0.50, phase_strength=0.5, cs_diff=100))
        cap_cs = score_lane(_make_lane(winrate=0.50, phase_strength=0.5, cs_diff=40))
        assert big_cs == cap_cs  # both hit the cap

    def test_negative_cs_diff_subtracts(self):
        lane = _make_lane(winrate=0.50, phase_strength=0.5, cs_diff=-20)
        score = score_lane(lane)
        # cs_bonus = min(-20 * 0.5, 20) = -10
        assert score == pytest.approx(-10.0)

    def test_combined_high_priority_scenario(self):
        lane = _make_lane(winrate=0.60, phase_strength=1.0, cs_diff=20, kill_pressure=True)
        # counter=20, phase=20*1.0=20, pressure=15, cs=min(10,20)=10 → 45
        assert score_lane(lane) == pytest.approx(45.0)
        assert score_to_priority(score_lane(lane)) == "high"


# ---------------------------------------------------------------------------
# score_to_priority()
# ---------------------------------------------------------------------------

class TestScoreToPriority:
    def test_above_40_is_high(self):
        assert score_to_priority(40.1) == "high"
        assert score_to_priority(100.0) == "high"

    def test_exactly_40_is_medium(self):
        assert score_to_priority(40.0) == "medium"

    def test_between_15_and_40_is_medium(self):
        assert score_to_priority(27.5) == "medium"
        assert score_to_priority(15.1) == "medium"

    def test_exactly_15_is_low(self):
        assert score_to_priority(15.0) == "low"

    def test_below_15_is_low(self):
        assert score_to_priority(0.0) == "low"
        assert score_to_priority(-50.0) == "low"


# ---------------------------------------------------------------------------
# score_all_lanes()
# ---------------------------------------------------------------------------

class TestScoreAllLanes:
    def test_returns_all_three_lanes(self):
        gs = _make_game_state()
        result = score_all_lanes(gs)
        assert set(result.keys()) == {"top", "mid", "bot"}

    def test_each_entry_is_score_priority_tuple(self):
        gs = _make_game_state()
        for lane, (score, priority) in score_all_lanes(gs).items():
            assert isinstance(score, float)
            assert priority in ("high", "medium", "low")

    def test_high_score_lane_ranks_high(self):
        top = _make_lane(winrate=0.65, phase_strength=1.0, cs_diff=30, kill_pressure=True)
        gs = _make_game_state(top=top)
        _, priority = score_all_lanes(gs)["top"]
        assert priority == "high"


# ---------------------------------------------------------------------------
# Live-signal bonuses / penalties
# ---------------------------------------------------------------------------

def _make_lane_live(
    winrate: float = 0.50,
    phase_strength: float = 0.5,
    enemy_has_flash: bool = True,
    level_diff: int = 0,
    ally_is_dead: bool = False,
    enemy_is_dead: bool = False,
) -> LaneState:
    return LaneState(
        ally_champion="Riven",
        enemy_champion="Gangplank",
        matchup_winrate=winrate,
        ally_phase_strength=phase_strength,
        cs_diff=0,
        ally_kill_pressure=False,
        enemy_has_flash=enemy_has_flash,
        level_diff=level_diff,
        ally_is_dead=ally_is_dead,
        enemy_is_dead=enemy_is_dead,
    )


class TestLiveSignals:
    def test_no_flash_adds_20(self):
        base = score_lane(_make_lane_live(enemy_has_flash=True))
        no_flash = score_lane(_make_lane_live(enemy_has_flash=False))
        assert no_flash - base == pytest.approx(20.0)

    def test_enemy_with_flash_no_bonus(self):
        lane = _make_lane_live(enemy_has_flash=True)
        # no flash bonus — score is just phase_score (0 for 0.50 winrate)
        assert score_lane(lane) == pytest.approx(0.0)

    def test_level_ahead_adds_bonus(self):
        base = score_lane(_make_lane_live(level_diff=0))
        ahead = score_lane(_make_lane_live(level_diff=2))
        # 2 levels × 4.0 weight = +8
        assert ahead - base == pytest.approx(8.0)

    def test_level_behind_subtracts(self):
        base = score_lane(_make_lane_live(level_diff=0))
        behind = score_lane(_make_lane_live(level_diff=-2))
        assert base - behind == pytest.approx(8.0)

    def test_level_diff_capped_at_12(self):
        large_diff = score_lane(_make_lane_live(level_diff=10))
        capped = score_lane(_make_lane_live(level_diff=3))
        # 3 × 4 = 12, which is the cap; 10 × 4 = 40 would exceed cap
        assert large_diff == capped

    def test_enemy_dead_adds_25(self):
        base = score_lane(_make_lane_live(enemy_is_dead=False))
        dead = score_lane(_make_lane_live(enemy_is_dead=True))
        assert dead - base == pytest.approx(25.0)

    def test_ally_dead_subtracts_60(self):
        base = score_lane(_make_lane_live(ally_is_dead=False))
        dead = score_lane(_make_lane_live(ally_is_dead=True))
        assert base - dead == pytest.approx(60.0)

    def test_ally_dead_overrides_enemy_dead(self):
        both_dead = score_lane(_make_lane_live(ally_is_dead=True, enemy_is_dead=True))
        only_ally_dead = score_lane(_make_lane_live(ally_is_dead=True, enemy_is_dead=False))
        # ally_dead takes priority — enemy_dead bonus is ignored
        assert both_dead == only_ally_dead

    def test_no_flash_and_enemy_dead_stack(self):
        base = score_lane(_make_lane_live())
        stacked = score_lane(_make_lane_live(enemy_has_flash=False, enemy_is_dead=True))
        assert stacked - base == pytest.approx(20.0 + 25.0)

    def test_all_signals_combine(self):
        lane = _make_lane_live(
            winrate=0.60,
            phase_strength=1.0,
            enemy_has_flash=False,
            level_diff=2,
            enemy_is_dead=True,
        )
        # counter=20, phase=20*1.0=20, flash=20, level=8, dead=25 → 73
        assert score_lane(lane) == pytest.approx(73.0)
