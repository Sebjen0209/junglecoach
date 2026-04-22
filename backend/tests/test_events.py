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


def _raw_obj(ts_ms: int, monster: str, killer_id: int, killer_team: int, jx: int, jy: int) -> RawObjective:
    return RawObjective(
        timestamp_ms=ts_ms,
        monster_type=monster,
        killer_id=killer_id,
        killer_team_id=killer_team,
        jungler_x=jx,
        jungler_y=jy,
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
        assert _classify_lane(7000, 2000) == "bot"

    def test_high_y_is_top(self):
        assert _classify_lane(3000, 12000) == "top"

    def test_middle_y_is_mid(self):
        assert _classify_lane(7000, 7000) == "mid"

    def test_at_bot_boundary(self):
        assert _classify_lane(5000, 4999) == "bot"
        assert _classify_lane(5000, 5001) == "mid"

    def test_at_top_boundary(self):
        assert _classify_lane(5000, 9999) == "mid"
        assert _classify_lane(5000, 10001) == "top"


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
        ganks = [_raw_gank(90_000, self.JUNGLER, 9, [], x=8000, y=2000)]
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
