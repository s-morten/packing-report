from types import SimpleNamespace

import pandas as pd
import pytest
from game.game_segments import (
    Segment,
    SegmentGoals,
    build_segments,
    goals_per_segment,
    is_present,
    segment_boundaries,
    segments_from_rows,
)


def make_facts(players, end_of_game=90.0, home_team_id=1, events=None, df_teams=None):
    """Minimal stand-in for ``GameFacts`` -- only the attributes segmentation touches."""
    return SimpleNamespace(
        game_id=1,
        end_of_game=end_of_game,
        players_dict=players,
        home_team_id=home_team_id,
        events=events if events is not None else _empty_events(),
        df_teams=df_teams if df_teams is not None else pd.DataFrame({"team_id": [1, 2]}),
    )


def _empty_events():
    return pd.DataFrame(
        {
            "is_goal": pd.Series([], dtype=object),
            "qualifiers": [],
            "team_id": pd.Series([], dtype=float),
            "expanded_minute": pd.Series([], dtype=float),
        }
    )


def eleven_home():
    return {player: {"team_id": 1, "on": 0.0, "off": 90.0} for player in range(1, 12)}


def eleven_away():
    return {player: {"team_id": 2, "on": 0.0, "off": 90.0} for player in range(101, 112)}


class TestSegmentBoundaries:
    def test_no_substitutions_gives_one_segment(self):
        players = {**eleven_home(), **eleven_away()}

        assert segment_boundaries(make_facts(players)) == [0.0, 90.0]

    def test_substitution_minutes_become_boundaries(self):
        players = {**eleven_home(), **eleven_away(), 12: {"team_id": 1, "on": 60.0, "off": 90.0}}
        players[11] = {"team_id": 1, "on": 0.0, "off": 60.0}

        assert segment_boundaries(make_facts(players)) == [0.0, 60.0, 90.0]

    def test_boundaries_are_sorted_and_unique(self):
        players = {**eleven_home(), **eleven_away(), 12: {"team_id": 1, "on": 70.0, "off": 90.0}}
        players[13] = {"team_id": 1, "on": 70.0, "off": 90.0}
        players[11] = {"team_id": 1, "on": 0.0, "off": 70.0}

        boundaries = segment_boundaries(make_facts(players))

        assert boundaries == sorted(set(boundaries))
        assert boundaries == [0.0, 70.0, 90.0]

    def test_boundaries_always_span_zero_to_end_of_game(self):
        players = {**eleven_home(), **eleven_away(), 12: {"team_id": 1, "on": 45.0, "off": 50.0}}

        boundaries = segment_boundaries(make_facts(players, end_of_game=93.0))

        assert boundaries[0] == 0.0
        assert boundaries[-1] == 93.0

    def test_minutes_outside_the_match_are_dropped(self):
        # ``Minutes`` clips on/off to [0, end_of_game], so this should never occur; if it does the
        # extra boundaries must not escape the match.
        players = {**eleven_home(), **eleven_away(), 12: {"team_id": 1, "on": 0.0, "off": 120.0}}

        assert segment_boundaries(make_facts(players, end_of_game=90.0)) == [0.0, 90.0]

    def test_red_card_match_is_truncated_at_the_card(self):
        # ``Minutes`` sets end_of_game to the first red card, so the whole model is 11-v-11 and the
        # remaining minutes of that match are simply not observed.
        players = {
            **{p: {"team_id": 1, "on": 0.0, "off": 18.0} for p in range(1, 12)},
            **{p: {"team_id": 2, "on": 0.0, "off": 18.0} for p in range(101, 112)},
        }

        assert segment_boundaries(make_facts(players, end_of_game=18.0)) == [0.0, 18.0]

    def test_non_positive_end_of_game_raises(self):
        with pytest.raises(ValueError, match="end_of_game must be positive"):
            segment_boundaries(make_facts({}, end_of_game=0.0))


class TestIsPresent:
    def test_player_spanning_the_whole_segment_is_present(self):
        assert is_present(0.0, 90.0, 30.0, 60.0)

    def test_player_coming_on_at_the_boundary_is_present(self):
        # The segment rule is inclusive at both ends, which is what makes it equivalent to the
        # per-player metrics' ``on < minute < off`` apart from the boundary minute itself.
        assert is_present(30.0, 90.0, 30.0, 60.0)

    def test_player_leaving_at_the_boundary_is_present(self):
        assert is_present(0.0, 60.0, 30.0, 60.0)

    def test_player_arriving_mid_segment_is_absent(self):
        assert not is_present(45.0, 90.0, 30.0, 60.0)

    def test_player_leaving_mid_segment_is_absent(self):
        assert not is_present(0.0, 45.0, 30.0, 60.0)


class TestBuildSegments:
    def test_typical_match_yields_seven_to_nine_segments(self):
        players = {**eleven_home(), **eleven_away()}
        for index in range(6):
            players[2 + index] = {"team_id": 1, "on": 0.0, "off": 60.0 + index}
            players[20 + index] = {"team_id": 1, "on": 60.0 + index, "off": 90.0}
            players[102 + index] = {"team_id": 2, "on": 0.0, "off": 60.0 + index}
            players[120 + index] = {"team_id": 2, "on": 60.0 + index, "off": 90.0}

        segments = build_segments(make_facts(players))

        assert 7 <= len(segments) <= 9

    def test_every_segment_is_eleven_versus_eleven(self):
        # Each substitute has to replace somebody, otherwise the XI grows past 11.
        players = {**eleven_home(), **eleven_away()}
        for index in range(4):
            players[2 + index] = {"team_id": 1, "on": 0.0, "off": 60.0 + index}
            players[20 + index] = {"team_id": 1, "on": 60.0 + index, "off": 90.0}
            players[102 + index] = {"team_id": 2, "on": 0.0, "off": 60.0 + index}
            players[120 + index] = {"team_id": 2, "on": 60.0 + index, "off": 90.0}

        for segment in build_segments(make_facts(players)):
            assert len(segment.home) == 11
            assert len(segment.away) == 11

    def test_segments_tile_the_match_without_gaps_or_overlaps(self):
        players = {**eleven_home(), **eleven_away(), 12: {"team_id": 1, "on": 70.0, "off": 90.0}}
        players[11] = {"team_id": 1, "on": 0.0, "off": 70.0}

        segments = build_segments(make_facts(players, end_of_game=93.0))

        assert segments[0].start_minute == 0.0
        assert segments[-1].end_minute == 93.0
        for earlier, later in zip(segments, segments[1:], strict=False):
            assert earlier.end_minute == later.start_minute

    def test_sides_are_split_by_home_team_id(self):
        players = {**eleven_home(), **eleven_away()}

        segment = build_segments(make_facts(players))[0]

        assert segment.home == frozenset(range(1, 12))
        assert segment.away == frozenset(range(101, 112))
        assert segment.is_home_advantage

    def test_a_player_id_never_appears_on_both_sides(self):
        players = {**eleven_home(), **eleven_away(), 12: {"team_id": 2, "on": 60.0, "off": 90.0}}
        players[11] = {"team_id": 1, "on": 0.0, "off": 60.0}

        for segment in build_segments(make_facts(players)):
            assert not segment.home & segment.away

    def test_indices_are_consecutive_from_zero(self):
        players = {**eleven_home(), **eleven_away(), 12: {"team_id": 1, "on": 70.0, "off": 90.0}}
        players[11] = {"team_id": 1, "on": 0.0, "off": 70.0}

        segments = build_segments(make_facts(players))

        assert [segment.index for segment in segments] == list(range(len(segments)))

    def test_duration_minutes_is_the_segment_length(self):
        segment = Segment(index=0, start_minute=10.0, end_minute=25.0, home=frozenset(), away=frozenset())

        assert segment.duration_minutes == 15.0

    def test_substitute_is_absent_from_every_segment_before_coming_on(self):
        players = {**eleven_home(), **eleven_away(), 12: {"team_id": 1, "on": 70.0, "off": 90.0}}
        players[11] = {"team_id": 1, "on": 0.0, "off": 70.0}

        segments = build_segments(make_facts(players))

        assert all(12 not in segment.home for segment in segments if segment.end_minute <= 70.0)
        assert all(12 in segment.home for segment in segments if segment.start_minute >= 70.0)
        assert all(11 not in segment.home for segment in segments if segment.start_minute >= 70.0)


class TestGoalsPerSegment:
    def _events(self, goals):
        return pd.DataFrame(
            {
                "is_goal": [True] * len(goals) + [None] * (4 - len(goals)),
                "qualifiers": [[]] * len(goals) + [None] * (4 - len(goals)),
                "team_id": [team_id for _, team_id in goals] + [0.0] * (4 - len(goals)),
                "expanded_minute": [minute for minute, _ in goals] + [0.0] * (4 - len(goals)),
            }
        )

    def test_goals_are_binned_by_minute(self):
        players = {**eleven_home(), **eleven_away(), 12: {"team_id": 1, "on": 70.0, "off": 90.0}}
        players[11] = {"team_id": 1, "on": 0.0, "off": 70.0}
        facts = make_facts(players, events=self._events([(30.0, 1), (80.0, 2)]))

        segments = build_segments(facts)
        goals = goals_per_segment(facts, segments)

        assert goals.home == [1, 0]
        assert goals.away == [0, 1]
        assert goals.total_home == 1
        assert goals.total_away == 1

    def test_goal_on_a_boundary_belongs_to_the_segment_starting_there(self):
        players = {**eleven_home(), **eleven_away(), 12: {"team_id": 1, "on": 70.0, "off": 90.0}}
        players[11] = {"team_id": 1, "on": 0.0, "off": 70.0}
        facts = make_facts(players, events=self._events([(70.0, 1)]))

        goals = goals_per_segment(facts, build_segments(facts))

        assert goals.home == [0, 1]

    def test_goals_past_the_truncated_end_of_game_are_ignored(self):
        # After a red card the feed keeps emitting events; those minutes belong to no segment.
        players = {
            **{p: {"team_id": 1, "on": 0.0, "off": 18.0} for p in range(1, 12)},
            **{p: {"team_id": 2, "on": 0.0, "off": 18.0} for p in range(101, 112)},
        }
        facts = make_facts(players, end_of_game=18.0, events=self._events([(10.0, 1), (75.0, 1)]))

        goals = goals_per_segment(facts, build_segments(facts))

        assert goals.total_home == 1

    def test_no_goals_at_all(self):
        players = {**eleven_home(), **eleven_away()}
        facts = make_facts(players, events=self._events([]))

        goals = goals_per_segment(facts, build_segments(facts))

        assert goals.total_home == 0
        assert goals.total_away == 0

    def test_segment_goals_defaults_to_empty(self):
        goals = SegmentGoals()

        assert goals.home == []
        assert goals.away == []
        assert goals.total_home == 0


class TestSegmentsFromRows:
    """Stage 2 rebuilds segments from the database instead of the event feed."""

    def _player_game_rows(self, substitution=None):
        """Mirror of ``PLAYER_GAME`` for one match: 11 a side, optionally one substitution.

        ``substitution`` is ``(player_off_id, player_on_id, minute)``.
        """
        rows = [{"player_id": player, "on_minute": 0.0, "off_minute": 90.0, "is_home": 1} for player in range(1, 12)]
        rows += [
            {"player_id": player, "on_minute": 0.0, "off_minute": 90.0, "is_home": 0} for player in range(101, 112)
        ]
        if substitution is not None:
            player_off, player_on, minute = substitution
            for row in rows:
                if row["player_id"] == player_off:
                    row["off_minute"] = minute
            rows.append({"player_id": player_on, "on_minute": minute, "off_minute": 90.0, "is_home": 1})
        return rows

    def _segment_rows(self, boundary=45.0):
        return [
            {"segment_index": 0, "start_minute": 0.0, "end_minute": boundary},
            {"segment_index": 1, "start_minute": boundary, "end_minute": 90.0},
        ]

    def test_rebuilt_segments_match_build_segments(self):
        players = {**eleven_home(), **eleven_away(), 12: {"team_id": 1, "on": 45.0, "off": 90.0}}
        players[11] = {"team_id": 1, "on": 0.0, "off": 45.0}
        expected = build_segments(make_facts(players))

        rebuilt = segments_from_rows(self._segment_rows(), self._player_game_rows(substitution=(11, 12, 45.0)))

        assert [s.index for s in rebuilt] == [s.index for s in expected]
        assert [s.start_minute for s in rebuilt] == [s.start_minute for s in expected]
        assert [s.end_minute for s in rebuilt] == [s.end_minute for s in expected]
        assert [s.home for s in rebuilt] == [s.home for s in expected]
        assert [s.away for s in rebuilt] == [s.away for s in expected]

    def test_sides_come_from_is_home(self):
        rebuilt = segments_from_rows(self._segment_rows(), self._player_game_rows())

        assert rebuilt[0].home == frozenset(range(1, 12))
        assert rebuilt[0].away == frozenset(range(101, 112))

    def test_players_are_not_shared_between_segments(self):
        rebuilt = segments_from_rows(self._segment_rows(), self._player_game_rows())

        assert rebuilt[0].home is not rebuilt[1].home
        assert len(rebuilt[0].home) == len(rebuilt[1].home) == 11

    def test_unordered_rows_are_sorted_by_segment_index(self):
        rows = list(reversed(self._segment_rows()))

        rebuilt = segments_from_rows(rows, self._player_game_rows())

        assert [s.index for s in rebuilt] == [0, 1]

    def test_player_off_before_a_segment_is_absent_from_it(self):
        rows = self._player_game_rows()
        for row in rows:
            if row["player_id"] == 1:
                row["off_minute"] = 45.0
        rows.append({"player_id": 12, "on_minute": 45.0, "off_minute": 90.0, "is_home": 1})

        rebuilt = segments_from_rows(self._segment_rows(), rows)

        assert 1 in rebuilt[0].home
        assert 1 not in rebuilt[1].home
        assert 12 not in rebuilt[0].home
        assert 12 in rebuilt[1].home

    def test_no_segments_yields_empty_list(self):
        assert segments_from_rows([], self._player_game_rows()) == []
