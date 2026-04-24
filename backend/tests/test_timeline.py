"""Tests for analysis/postgame/timeline.py — timeline extraction logic."""

import pytest

from analysis.postgame.timeline import (
    BLUE_TEAM,
    RED_TEAM,
    dist,
    extract_jungler_data,
    PositionFrame,
    RawGank,
    RawObjective,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _participant(
    pid: int,
    team_id: int,
    position: str,
    champion: str,
    puuid: str = "",
) -> dict:
    return {
        "participantId": pid,
        "puuid": puuid or f"puuid-{pid}",
        "teamId": team_id,
        "teamPosition": position,
        "championName": champion,
    }


def _match(participants: list[dict]) -> dict:
    return {"info": {"participants": participants}}


def _frame(
    timestamp_ms: int,
    positions: dict[int, tuple[int, int]],
    events: list[dict] | None = None,
) -> dict:
    return {
        "timestamp": timestamp_ms,
        "participantFrames": {
            str(pid): {"position": {"x": x, "y": y}}
            for pid, (x, y) in positions.items()
        },
        "events": events or [],
    }


def _timeline(frames: list[dict]) -> dict:
    return {"info": {"frames": frames}}


# 10-player match: blue jungler = participant 2 (Vi), red jungler = 7 (Hecarim)
_PARTICIPANTS = [
    _participant(1,  BLUE_TEAM, "TOP",     "Darius",  "puuid-b1"),
    _participant(2,  BLUE_TEAM, "JUNGLE",  "Vi",      "puuid-b2"),
    _participant(3,  BLUE_TEAM, "MIDDLE",  "Zed",     "puuid-b3"),
    _participant(4,  BLUE_TEAM, "BOTTOM",  "Jinx",    "puuid-b4"),
    _participant(5,  BLUE_TEAM, "UTILITY", "Thresh",  "puuid-b5"),
    _participant(6,  RED_TEAM,  "TOP",     "Garen",   "puuid-r1"),
    _participant(7,  RED_TEAM,  "JUNGLE",  "Hecarim", "puuid-r2"),
    _participant(8,  RED_TEAM,  "MIDDLE",  "Syndra",  "puuid-r3"),
    _participant(9,  RED_TEAM,  "BOTTOM",  "Caitlyn", "puuid-r4"),
    _participant(10, RED_TEAM,  "UTILITY", "Lux",     "puuid-r5"),
]
_MATCH = _match(_PARTICIPANTS)


# ---------------------------------------------------------------------------
# dist()
# ---------------------------------------------------------------------------

class TestDist:
    def test_same_point_is_zero(self):
        assert dist(5, 5, 5, 5) == 0.0

    def test_horizontal(self):
        assert dist(0, 0, 3, 0) == 3.0

    def test_pythagorean(self):
        assert abs(dist(0, 0, 3, 4) - 5.0) < 1e-9


# ---------------------------------------------------------------------------
# Jungler identification
# ---------------------------------------------------------------------------

class TestFindJungler:
    def test_blue_jungler_by_default(self):
        data = extract_jungler_data(_MATCH, _timeline([]))
        assert data.champion_name == "Vi"
        assert data.team_id == BLUE_TEAM

    def test_finds_jungler_for_blue_puuid(self):
        data = extract_jungler_data(_MATCH, _timeline([]), target_puuid="puuid-b2")
        assert data.champion_name == "Vi"

    def test_target_is_jungler_themselves(self):
        # puuid-b2 IS the jungler — returns directly
        data = extract_jungler_data(_MATCH, _timeline([]), target_puuid="puuid-b2")
        assert data.puuid == "puuid-b2"

    def test_non_jungler_target_picks_team_jungler(self):
        # Target is blue ADC → should find Vi (blue jungler)
        data = extract_jungler_data(_MATCH, _timeline([]), target_puuid="puuid-b4")
        assert data.champion_name == "Vi"

    def test_red_team_target_picks_red_jungler(self):
        data = extract_jungler_data(_MATCH, _timeline([]), target_puuid="puuid-r1")
        assert data.champion_name == "Hecarim"

    def test_raises_when_no_jungler_present(self):
        no_jungle = _match([
            _participant(1, BLUE_TEAM, "TOP",    "Darius"),
            _participant(2, BLUE_TEAM, "MIDDLE", "Zed"),
        ])
        with pytest.raises(ValueError, match="No JUNGLE participant"):
            extract_jungler_data(no_jungle, _timeline([]))

    def test_champion_name_in_data(self):
        data = extract_jungler_data(_MATCH, _timeline([]))
        assert data.champion_name == "Vi"

    def test_participant_id_in_data(self):
        data = extract_jungler_data(_MATCH, _timeline([]))
        assert data.participant_id == 2


# ---------------------------------------------------------------------------
# Position frame extraction
# ---------------------------------------------------------------------------

class TestPositionFrames:
    def test_position_per_frame(self):
        frames = [
            _frame(0,       {2: (1000, 2000)}),
            _frame(60_000,  {2: (3000, 4000)}),
            _frame(120_000, {2: (5000, 6000)}),
        ]
        data = extract_jungler_data(_MATCH, _timeline(frames))
        assert len(data.position_frames) == 3
        assert data.position_frames[0].x == 1000
        assert data.position_frames[1].y == 4000
        assert data.position_frames[2].x == 5000

    def test_missing_participant_frame_skipped(self):
        frames = [_frame(60_000, {})]  # jungler (2) absent from participantFrames
        data = extract_jungler_data(_MATCH, _timeline(frames))
        assert len(data.position_frames) == 0

    def test_minute_rounded_from_ms(self):
        frames = [_frame(90_000, {2: (5000, 5000)})]  # 90s → round(1.5) = 2
        data = extract_jungler_data(_MATCH, _timeline(frames))
        assert data.position_frames[0].minute == 2


# ---------------------------------------------------------------------------
# Champion kill (gank) extraction
# ---------------------------------------------------------------------------

class TestChampionKillExtraction:
    def _kill(
        self,
        ts_ms: int,
        killer: int,
        victim: int,
        assisting: list[int] | None = None,
        x: int = 7000,
        y: int = 5000,
    ) -> dict:
        return {
            "type": "CHAMPION_KILL",
            "timestamp": ts_ms,
            "killerId": killer,
            "victimId": victim,
            "assistingParticipantIds": assisting or [],
            "position": {"x": x, "y": y},
        }

    def test_jungler_kill_recorded(self):
        evt = self._kill(90_000, killer=2, victim=8)
        data = extract_jungler_data(_MATCH, _timeline([_frame(90_000, {2: (7000, 5000)}, [evt])]))
        assert len(data.ganks) == 1
        assert data.ganks[0].killer_id == 2
        assert data.ganks[0].victim_id == 8

    def test_jungler_assist_recorded(self):
        evt = self._kill(90_000, killer=3, victim=8, assisting=[2])
        data = extract_jungler_data(_MATCH, _timeline([_frame(90_000, {2: (7000, 5000)}, [evt])]))
        assert len(data.ganks) == 1
        assert data.ganks[0].killer_id == 3

    def test_kill_without_jungler_ignored(self):
        evt = self._kill(90_000, killer=3, victim=8, assisting=[4, 5])
        data = extract_jungler_data(_MATCH, _timeline([_frame(90_000, {2: (500, 500)}, [evt])]))
        assert len(data.ganks) == 0

    def test_kill_position_stored(self):
        evt = self._kill(90_000, killer=2, victim=8, x=8000, y=3000)
        data = extract_jungler_data(_MATCH, _timeline([_frame(90_000, {2: (8000, 3000)}, [evt])]))
        assert data.ganks[0].position_x == 8000
        assert data.ganks[0].position_y == 3000

    def test_multiple_kills_across_frames(self):
        e1 = self._kill(60_000, killer=2, victim=8)
        e2 = self._kill(120_000, killer=2, victim=6)
        data = extract_jungler_data(_MATCH, _timeline([
            _frame(60_000, {2: (7000, 5000)}, [e1]),
            _frame(120_000, {2: (2000, 12000)}, [e2]),
        ]))
        assert len(data.ganks) == 2


# ---------------------------------------------------------------------------
# Objective extraction
# ---------------------------------------------------------------------------

class TestObjectiveExtraction:
    def _objective(self, ts_ms: int, monster: str, killer: int) -> dict:
        return {
            "type": "ELITE_MONSTER_KILL",
            "timestamp": ts_ms,
            "monsterType": monster,
            "killerId": killer,
        }

    def test_dragon_recorded(self):
        evt = self._objective(5 * 60_000, "DRAGON", 2)
        data = extract_jungler_data(_MATCH, _timeline([_frame(5 * 60_000, {2: (9866, 4414)}, [evt])]))
        assert len(data.objectives) == 1
        assert data.objectives[0].monster_type == "DRAGON"

    def test_baron_recorded(self):
        evt = self._objective(20 * 60_000, "BARON_NASHOR", 2)
        data = extract_jungler_data(_MATCH, _timeline([_frame(20 * 60_000, {2: (5007, 10471)}, [evt])]))
        assert data.objectives[0].monster_type == "BARON_NASHOR"

    def test_herald_recorded(self):
        evt = self._objective(10 * 60_000, "RIFTHERALD", 2)
        data = extract_jungler_data(_MATCH, _timeline([_frame(10 * 60_000, {2: (5007, 10471)}, [evt])]))
        assert data.objectives[0].monster_type == "RIFTHERALD"

    def test_horde_not_in_objectives(self):
        # HORDE (Void Grubs) is routed to void_grub_kills, not objectives
        evt = self._objective(6 * 60_000, "HORDE", 2)
        data = extract_jungler_data(_MATCH, _timeline([_frame(6 * 60_000, {2: (5000, 5000)}, [evt])]))
        assert len(data.objectives) == 0

    def test_horde_goes_to_void_grub_kills(self):
        evt = self._objective(6 * 60_000, "HORDE", 2)  # jungler (blue) kills a void grub
        data = extract_jungler_data(_MATCH, _timeline([_frame(6 * 60_000, {2: (5000, 5000)}, [evt])]))
        assert len(data.void_grub_kills) == 1
        ts, team = data.void_grub_kills[0]
        assert ts == 6 * 60_000
        assert team == BLUE_TEAM

    def test_multiple_void_grubs_tracked(self):
        evts = [self._objective(6 * 60_000 + i * 10_000, "HORDE", 2) for i in range(3)]
        data = extract_jungler_data(_MATCH, _timeline([_frame(6 * 60_000, {2: (5000, 5000)}, evts)]))
        assert len(data.void_grub_kills) == 3

    def test_jungler_killer_sets_was_killer_true(self):
        # Participant 2 is the jungler — getting the kill sets jungler_was_killer
        evt = self._objective(5 * 60_000, "DRAGON", 2)
        data = extract_jungler_data(_MATCH, _timeline([_frame(5 * 60_000, {2: (9866, 4414)}, [evt])]))
        assert data.objectives[0].jungler_was_killer is True

    def test_non_jungler_killer_was_killer_false(self):
        # Participant 3 (mid laner) gets the kill — jungler_was_killer stays False
        evt = self._objective(5 * 60_000, "DRAGON", 3)
        data = extract_jungler_data(_MATCH, _timeline([_frame(5 * 60_000, {2: (5000, 5000)}, [evt])]))
        assert data.objectives[0].jungler_was_killer is False

    def test_killer_team_resolved(self):
        # Killer is participant 2 (blue team)
        evt = self._objective(5 * 60_000, "DRAGON", 2)
        data = extract_jungler_data(_MATCH, _timeline([_frame(5 * 60_000, {2: (9866, 4414)}, [evt])]))
        assert data.objectives[0].killer_team_id == BLUE_TEAM

    def test_enemy_killer_team_resolved(self):
        evt = self._objective(5 * 60_000, "DRAGON", 7)  # Hecarim (red)
        data = extract_jungler_data(_MATCH, _timeline([_frame(5 * 60_000, {2: (5000, 5000)}, [evt])]))
        assert data.objectives[0].killer_team_id == RED_TEAM


# ---------------------------------------------------------------------------
# Ward extraction
# ---------------------------------------------------------------------------

class TestWardExtraction:
    def test_ward_placed_by_jungler(self):
        evt = {
            "type": "WARD_PLACED",
            "timestamp": 60_000,
            "creatorId": 2,
            "position": {"x": 9000, "y": 4000},
        }
        data = extract_jungler_data(_MATCH, _timeline([_frame(60_000, {2: (9000, 4000)}, [evt])]))
        assert len(data.wards) == 1
        assert data.wards[0].placer_id == 2
        assert data.wards[0].x == 9000

    def test_ward_placed_by_ally_also_recorded(self):
        # We record all wards (not just jungler wards) for vision checks
        evt = {
            "type": "WARD_PLACED",
            "timestamp": 60_000,
            "creatorId": 5,  # Thresh (support)
            "position": {"x": 9000, "y": 4000},
        }
        data = extract_jungler_data(_MATCH, _timeline([_frame(60_000, {2: (500, 500)}, [evt])]))
        assert len(data.wards) == 1
        assert data.wards[0].placer_id == 5
