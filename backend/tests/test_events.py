"""Tests for analysis/postgame/events.py — event classification."""

import pytest

from analysis.postgame.events import (
    GankEvent,
    ObjectiveEvent,
    PathingIssue,
    classify_ganks,
    classify_objectives,
    detect_pathing_issues,
    _classify_lane,
    _ms_to_str,
)
from analysis.postgame.timeline import (
    BARON_PIT,
    BLUE_BASE,
    BLUE_TEAM,
    DRAGON_PIT,
    JunglerTimelineData,
    NEAR_BASE_RADIUS,
    PositionFrame,
    RawGank,
    RawObjective,
    RawWard,
    RED_BASE,
    RED_TEAM,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _raw_gank(ts_ms: int, killer: int, victim: int, assisting: list[int], x: int, y: int) -> RawGank:
    return RawGank(
        timestamp_ms=ts_ms,
        killer_id=killer,
        victim_id=victim,
        assisting_ids=assisting,
        position_x=x,
        position_y=y,
    )


def _raw_obj(
    ts_ms: int,
    monster: str,
    killer_id: int,
    killer_team: int,
    jx: int,
    jy: int,
    jungler_was_killer: bool = False,
) -> RawObjective:
    return RawObjective(
        timestamp_ms=ts_ms,
        monster_type=monster,
        killer_id=killer_id,
        killer_team_id=killer_team,
        jungler_x=jx,
        jungler_y=jy,
        jungler_was_killer=jungler_was_killer,
    )


def _ward(ts_ms: int, x: int, y: int) -> RawWard:
    return RawWard(timestamp_ms=ts_ms, placer_id=2, x=x, y=y)


def _data(team_id: int, frames: list[PositionFrame]) -> JunglerTimelineData:
    d = JunglerTimelineData(participant_id=2, team_id=team_id, champion_name="Vi", puuid="p")
    d.position_frames = frames
    return d


# ---------------------------------------------------------------------------
# _ms_to_str
# ---------------------------------------------------------------------------

class TestMsToStr:
    def test_zero(self):
        assert _ms_to_str(0) == "00:00"

    def test_one_minute(self):
        assert _ms_to_str(60_000) == "01:00"

    def test_five_thirty(self):
        assert _ms_to_str(5 * 60_000 + 30_000) == "05:30"

    def test_sub_second_truncated(self):
        assert _ms_to_str(90_500) == "01:30"

    def test_double_digit_minutes(self):
        assert _ms_to_str(25 * 60_000) == "25:00"


# ---------------------------------------------------------------------------
# _classify_lane
# ---------------------------------------------------------------------------

class TestClassifyLane:
    def test_low_y_is_bot(self):
        # Hard bot zone: x > 10500 AND y < 5000
        assert _classify_lane(11000, 3000) == "bot"

    def test_high_y_is_top(self):
        assert _classify_lane(3000, 12000) == "top"

    def test_middle_y_is_mid(self):
        assert _classify_lane(7000, 7000) == "mid"

    def test_at_hard_bot_boundary(self):
        # Just inside and just outside the hard bot zone (x threshold is 10500)
        assert _classify_lane(10501, 4999) == "bot"
        assert _classify_lane(10499, 4999) == "jungle/bot"

    def test_at_hard_top_boundary(self):
        # Just inside and just outside the hard top zone (x threshold is 3800)
        assert _classify_lane(3799, 9501) == "top"
        assert _classify_lane(3801, 9501) == "jungle/top"

    def test_jungle_top_zone(self):
        # Near top lane but in the jungle — x < 5500 AND y > 8500
        assert _classify_lane(4500, 9000) == "jungle/top"

    def test_jungle_bot_zone(self):
        # Near bot lane but in the jungle — x > 8500 AND y < 6000
        assert _classify_lane(9500, 4500) == "jungle/bot"

    def test_deep_jungle_is_jungle(self):
        # Centre of the map, away from all lane/near-lane zones
        assert _classify_lane(7000, 5000) == "jungle"


# ---------------------------------------------------------------------------
# classify_ganks
# ---------------------------------------------------------------------------

class TestClassifyGanks:
    JUNGLER = 2

    def test_kill_outcome(self):
        ganks = [_raw_gank(90_000, killer=self.JUNGLER, victim=8, assisting=[], x=7000, y=7000)]
        result = classify_ganks(ganks, self.JUNGLER)
        assert result[0].outcome == "kill"
        assert result[0].was_jungler_killer is True

    def test_assist_outcome(self):
        ganks = [_raw_gank(90_000, killer=3, victim=8, assisting=[self.JUNGLER], x=7000, y=7000)]
        result = classify_ganks(ganks, self.JUNGLER)
        assert result[0].outcome == "assist"
        assert result[0].was_jungler_killer is False

    def test_lane_bot(self):
        ganks = [_raw_gank(90_000, self.JUNGLER, 9, [], x=11000, y=2000)]
        assert classify_ganks(ganks, self.JUNGLER)[0].lane == "bot"

    def test_lane_top(self):
        ganks = [_raw_gank(90_000, self.JUNGLER, 6, [], x=2000, y=12000)]
        assert classify_ganks(ganks, self.JUNGLER)[0].lane == "top"

    def test_lane_mid(self):
        ganks = [_raw_gank(90_000, self.JUNGLER, 8, [], x=7000, y=7000)]
        assert classify_ganks(ganks, self.JUNGLER)[0].lane == "mid"

    def test_sorted_ascending(self):
        ganks = [
            _raw_gank(180_000, self.JUNGLER, 8, [], 7000, 7000),
            _raw_gank(60_000,  self.JUNGLER, 6, [], 2000, 12000),
        ]
        result = classify_ganks(ganks, self.JUNGLER)
        assert result[0].timestamp_ms == 60_000
        assert result[1].timestamp_ms == 180_000

    def test_timestamp_str_format(self):
        ganks = [_raw_gank(5 * 60_000, self.JUNGLER, 6, [], 2000, 12000)]
        assert classify_ganks(ganks, self.JUNGLER)[0].timestamp_str == "05:00"

    def test_position_stored(self):
        ganks = [_raw_gank(90_000, self.JUNGLER, 8, [], x=1234, y=5678)]
        result = classify_ganks(ganks, self.JUNGLER)
        assert result[0].position_x == 1234
        assert result[0].position_y == 5678

    def test_empty_returns_empty(self):
        assert classify_ganks([], self.JUNGLER) == []


# ---------------------------------------------------------------------------
# classify_objectives
# ---------------------------------------------------------------------------

class TestClassifyObjectives:
    def test_ally_secured(self):
        obj = [_raw_obj(5 * 60_000, "DRAGON", 2, BLUE_TEAM, *DRAGON_PIT)]
        result = classify_objectives(obj, [], BLUE_TEAM)
        assert result[0].secured_by_ally is True

    def test_enemy_secured(self):
        obj = [_raw_obj(5 * 60_000, "DRAGON", 7, RED_TEAM, *DRAGON_PIT)]
        result = classify_objectives(obj, [], BLUE_TEAM)
        assert result[0].secured_by_ally is False

    def test_jungler_at_pit_is_near(self):
        obj = [_raw_obj(5 * 60_000, "DRAGON", 2, BLUE_TEAM, *DRAGON_PIT)]
        result = classify_objectives(obj, [], BLUE_TEAM)
        assert result[0].was_near_pit is True
        assert result[0].jungler_distance_from_pit == 0

    def test_jungler_far_is_not_near(self):
        obj = [_raw_obj(5 * 60_000, "DRAGON", 7, RED_TEAM, 500, 500)]
        result = classify_objectives(obj, [], BLUE_TEAM)
        assert result[0].was_near_pit is False

    def test_had_vision_with_ward(self):
        ts = 5 * 60_000
        obj = [_raw_obj(ts, "DRAGON", 7, RED_TEAM, *DRAGON_PIT)]
        wards = [_ward(ts - 30_000, *DRAGON_PIT)]
        result = classify_objectives(obj, wards, BLUE_TEAM)
        assert result[0].had_vision_before is True

    def test_had_vision_false_no_wards(self):
        obj = [_raw_obj(5 * 60_000, "DRAGON", 7, RED_TEAM, *DRAGON_PIT)]
        result = classify_objectives(obj, [], BLUE_TEAM)
        assert result[0].had_vision_before is False

    def test_had_vision_false_ward_too_old(self):
        ts = 5 * 60_000
        obj = [_raw_obj(ts, "DRAGON", 7, RED_TEAM, *DRAGON_PIT)]
        wards = [_ward(ts - 120_000, *DRAGON_PIT)]  # > 60s before
        result = classify_objectives(obj, wards, BLUE_TEAM)
        assert result[0].had_vision_before is False

    def test_first_spawn_dragon_at_5min(self):
        obj = [_raw_obj(5 * 60_000, "DRAGON", 2, BLUE_TEAM, *DRAGON_PIT)]
        assert classify_objectives(obj, [], BLUE_TEAM)[0].is_first_spawn is True

    def test_not_first_spawn_at_15min(self):
        obj = [_raw_obj(15 * 60_000, "DRAGON", 2, BLUE_TEAM, *DRAGON_PIT)]
        assert classify_objectives(obj, [], BLUE_TEAM)[0].is_first_spawn is False

    def test_first_spawn_baron_at_20min(self):
        obj = [_raw_obj(20 * 60_000, "BARON_NASHOR", 2, BLUE_TEAM, *BARON_PIT)]
        assert classify_objectives(obj, [], BLUE_TEAM)[0].is_first_spawn is True

    def test_sorted_ascending(self):
        obj = [
            _raw_obj(20 * 60_000, "BARON_NASHOR", 2, BLUE_TEAM, *BARON_PIT),
            _raw_obj(5 * 60_000,  "DRAGON",       2, BLUE_TEAM, *DRAGON_PIT),
        ]
        result = classify_objectives(obj, [], BLUE_TEAM)
        assert result[0].objective_type == "DRAGON"

    def test_objective_type_preserved(self):
        obj = [_raw_obj(10 * 60_000, "RIFTHERALD", 2, BLUE_TEAM, *BARON_PIT)]
        result = classify_objectives(obj, [], BLUE_TEAM)
        assert result[0].objective_type == "RIFTHERALD"

    def test_empty_returns_empty(self):
        assert classify_objectives([], [], BLUE_TEAM) == []

    def test_jungler_killer_sets_flag_and_forces_zero_distance(self):
        # When jungler gets the smite, the per-minute position frame is unreliable —
        # distance must be forced to 0 and jungler_killed_objective set True.
        obj = [_raw_obj(5 * 60_000, "DRAGON", 2, BLUE_TEAM, 500, 500, jungler_was_killer=True)]
        ev = classify_objectives(obj, [], BLUE_TEAM)[0]
        assert ev.jungler_killed_objective is True
        assert ev.jungler_distance_from_pit == 0
        assert ev.was_near_pit is True

    def test_non_killer_jungler_distance_computed_normally(self):
        obj = [_raw_obj(5 * 60_000, "DRAGON", 3, RED_TEAM, 500, 500)]
        ev = classify_objectives(obj, [], BLUE_TEAM)[0]
        assert ev.jungler_killed_objective is False
        assert ev.jungler_distance_from_pit > 0

    def test_detect_trades_opposite_teams_within_60s(self):
        # Dragon (ally) and Herald (enemy) taken 30 s apart → both flagged
        dragon_ts = 8 * 60_000
        herald_ts = dragon_ts + 30_000
        objs = [
            _raw_obj(dragon_ts, "DRAGON",     2, BLUE_TEAM, *DRAGON_PIT),
            _raw_obj(herald_ts, "RIFTHERALD", 7, RED_TEAM,  *BARON_PIT),
        ]
        result = classify_objectives(objs, [], BLUE_TEAM)
        dragon = next(e for e in result if e.objective_type == "DRAGON")
        herald = next(e for e in result if e.objective_type == "RIFTHERALD")
        assert dragon.is_trade is True
        assert herald.is_trade is True
        assert dragon.trade_with == "RIFTHERALD"
        assert herald.trade_with == "DRAGON"

    def test_no_trade_same_team(self):
        objs = [
            _raw_obj(5 * 60_000,          "DRAGON",     2, BLUE_TEAM, *DRAGON_PIT),
            _raw_obj(5 * 60_000 + 30_000, "RIFTHERALD", 2, BLUE_TEAM, *BARON_PIT),
        ]
        result = classify_objectives(objs, [], BLUE_TEAM)
        assert all(not e.is_trade for e in result)

    def test_no_trade_outside_window(self):
        # More than 60 s apart — not a trade
        objs = [
            _raw_obj(5 * 60_000,          "DRAGON",     2, BLUE_TEAM, *DRAGON_PIT),
            _raw_obj(5 * 60_000 + 61_000, "RIFTHERALD", 7, RED_TEAM,  *BARON_PIT),
        ]
        result = classify_objectives(objs, [], BLUE_TEAM)
        assert all(not e.is_trade for e in result)

    def test_available_for_trade_lists_dragon_when_enemy_takes_baron(self):
        # Enemy takes baron at 20 min; dragon is available (no prior dragon kills)
        baron_ts = 20 * 60_000
        objs = [_raw_obj(baron_ts, "BARON_NASHOR", 7, RED_TEAM, 5000, 5000)]
        ev = classify_objectives(objs, [], BLUE_TEAM)[0]
        assert not ev.secured_by_ally
        assert any("Dragon" in a for a in ev.available_for_trade)

    def test_available_for_trade_void_grubs_counted(self):
        # Enemy takes dragon at 10 min; 4 void grubs already killed → 2 remaining
        dragon_ts = 10 * 60_000
        void_grub_kills = [
            (5 * 60_000,          RED_TEAM),
            (5 * 60_000 + 30_000, RED_TEAM),
            (6 * 60_000,          RED_TEAM),
            (6 * 60_000 + 30_000, RED_TEAM),
        ]
        objs = [_raw_obj(dragon_ts, "DRAGON", 7, RED_TEAM, 5000, 5000)]
        ev = classify_objectives(objs, [], BLUE_TEAM, void_grub_kills=void_grub_kills)[0]
        grub_entries = [a for a in ev.available_for_trade if "Void Grub" in a]
        assert len(grub_entries) == 1
        assert "2 remaining" in grub_entries[0]

    def test_available_for_trade_not_suggested_for_ally_secured(self):
        # When ally secures an objective, available_for_trade is still computed
        # but the field should exist (coach.py decides whether to surface it).
        objs = [_raw_obj(5 * 60_000, "DRAGON", 2, BLUE_TEAM, *DRAGON_PIT)]
        ev = classify_objectives(objs, [], BLUE_TEAM)[0]
        assert isinstance(ev.available_for_trade, list)


# ---------------------------------------------------------------------------
# detect_pathing_issues
# ---------------------------------------------------------------------------

class TestDetectPathingIssues:
    def test_in_base_blue(self):
        bx, by = BLUE_BASE
        frames = [
            PositionFrame(minute=0, x=5000, y=5000),
            PositionFrame(minute=1, x=bx, y=by),
        ]
        issues = detect_pathing_issues(_data(BLUE_TEAM, frames))
        assert any(i.issue == "in_base" for i in issues)

    def test_in_base_red(self):
        bx, by = RED_BASE
        frames = [
            PositionFrame(minute=0, x=5000, y=5000),
            PositionFrame(minute=1, x=bx, y=by),
        ]
        issues = detect_pathing_issues(_data(RED_TEAM, frames))
        assert any(i.issue == "in_base" for i in issues)

    def test_idle_less_than_800_units(self):
        frames = [
            PositionFrame(minute=0, x=5000, y=5000),
            PositionFrame(minute=1, x=5100, y=5100),  # ~141 units moved
        ]
        issues = detect_pathing_issues(_data(BLUE_TEAM, frames))
        assert any(i.issue == "idle" for i in issues)

    def test_active_pathing_no_issue(self):
        frames = [
            PositionFrame(minute=0, x=5000, y=5000),
            PositionFrame(minute=1, x=6500, y=6500),  # ~2121 units
        ]
        issues = detect_pathing_issues(_data(BLUE_TEAM, frames))
        idle_issues = [i for i in issues if i.issue == "idle"]
        assert len(idle_issues) == 0

    def test_minute_zero_never_flagged(self):
        bx, by = BLUE_BASE
        frames = [PositionFrame(minute=0, x=bx, y=by)]
        issues = detect_pathing_issues(_data(BLUE_TEAM, frames))
        assert len(issues) == 0

    def test_in_base_minute_stored(self):
        bx, by = BLUE_BASE
        frames = [
            PositionFrame(minute=0, x=5000, y=5000),
            PositionFrame(minute=3, x=bx, y=by),
        ]
        issues = detect_pathing_issues(_data(BLUE_TEAM, frames))
        assert issues[0].minute == 3

    def test_timestamp_str_format(self):
        bx, by = BLUE_BASE
        frames = [
            PositionFrame(minute=0, x=5000, y=5000),
            PositionFrame(minute=2, x=bx, y=by),
        ]
        issues = detect_pathing_issues(_data(BLUE_TEAM, frames))
        in_base = [i for i in issues if i.issue == "in_base"]
        assert in_base[0].timestamp_str == "02:00"

    def test_sorted_by_minute(self):
        bx, by = BLUE_BASE
        frames = [
            PositionFrame(minute=0, x=5000, y=5000),
            PositionFrame(minute=4, x=bx, y=by),
            PositionFrame(minute=2, x=bx, y=by),
        ]
        issues = detect_pathing_issues(_data(BLUE_TEAM, frames))
        in_base = [i for i in issues if i.issue == "in_base"]
        assert in_base[0].minute < in_base[1].minute

    def test_empty_frames_returns_empty(self):
        assert detect_pathing_issues(_data(BLUE_TEAM, [])) == []
