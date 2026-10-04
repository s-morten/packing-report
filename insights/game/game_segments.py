"""Split a match into segments during which the set of players on the pitch is constant.

This module owns *where* the segment boundaries are and *who* was on the pitch during each
segment. It deliberately does not price any action: the xT value of every action is computed
exactly once per game by :class:`metrics.low_level.xt.Xt`, which then fans that single pricing
pass out to both the per-player ``xt`` metric and the per-segment dependent variable.

Design notes
------------
Boundaries come from ``game_facts.players_dict`` (on/off minutes, produced by
:class:`metrics.low_level.minutes.Minutes`) plus ``game_facts.end_of_game``. That means:

* A segment boundary is created by a **substitution** and nothing else. Sending-off does not
  create a boundary.
* The match **ends at the first red card**, because ``Minutes.calculate`` already truncates
  ``end_of_game`` to ``min(natural end, first SecondYellow/Red)``. Every surviving segment is
  therefore 11-v-11, which is also why the model carries no red-card dummy variables: with no
  post-card segments there is nothing for them to explain.
* All minutes are clipped to ``[0, end_of_game]`` by ``Minutes``, so no clamping is repeated
  here.

A player is on the pitch for segment ``[b_k, b_k+1)`` iff ``on <= b_k and off >= b_k+1``. This is
the same condition the existing per-player metrics use (``on < minute < off``), so a refactor
that routes them through segments leaves their values unchanged.

A consequence worth stating explicitly: red-card matches contribute only their truncated portion
(observed rate ~25% of matches, occasionally ending before half time). That is the intended
policy -- the game state has changed fundamentally at that point -- but it does mean the model
never learns a red-card cost, and short segments are noisier. Per-90 normalisation is what keeps
a truncated segment on the same scale as a full one.
"""

from dataclasses import dataclass, field

from utils.football_data_utils import get_score


@dataclass(frozen=True)
class Segment:
    """One observation of the plus-minus regression.

    ``start_minute`` is inclusive, ``end_minute`` is exclusive. ``home`` / ``away`` hold player
    ids; a player id appears in at most one of the two sets.
    """

    index: int
    start_minute: float
    end_minute: float
    home: frozenset[int]
    away: frozenset[int]

    @property
    def duration_minutes(self) -> float:
        return self.end_minute - self.start_minute

    @property
    def is_home_advantage(self) -> bool:
        return len(self.home) >= len(self.away)


def segment_boundaries(game_facts) -> list[float]:
    """Sorted, de-duplicated boundary minutes spanning ``[0, end_of_game]``."""
    end_of_game = float(game_facts.end_of_game)
    if end_of_game <= 0:
        raise ValueError(f"game {game_facts.game_id}: end_of_game must be positive, got {end_of_game}")

    candidates = {0.0, end_of_game}
    for info in game_facts.players_dict.values():
        on = float(info["on"])
        off = float(info["off"])
        if 0.0 < on < end_of_game:
            candidates.add(on)
        if 0.0 < off < end_of_game:
            candidates.add(off)

    return sorted(candidates)


def is_present(on: float, off: float, start_minute: float, end_minute: float) -> bool:
    """Whether a player occupies the half-open segment ``[start_minute, end_minute)``."""
    return on <= start_minute and off >= end_minute


def build_segments(game_facts) -> list[Segment]:
    """Build every segment of a match from ``players_dict`` and ``end_of_game``."""
    boundaries = segment_boundaries(game_facts)
    home_team_id = int(game_facts.home_team_id)

    segments = []
    for index in range(len(boundaries) - 1):
        start, end = boundaries[index], boundaries[index + 1]
        home: list[int] = []
        away: list[int] = []
        for player_id, info in game_facts.players_dict.items():
            if not is_present(float(info["on"]), float(info["off"]), start, end):
                continue
            if int(info["team_id"]) == home_team_id:
                home.append(int(player_id))
            else:
                away.append(int(player_id))
        segments.append(
            Segment(
                index=index,
                start_minute=start,
                end_minute=end,
                home=frozenset(home),
                away=frozenset(away),
            )
        )
    return segments


@dataclass
class SegmentGoals:
    """Goals scored inside each segment, from both teams' perspectives."""

    home: list[int] = field(default_factory=list)
    away: list[int] = field(default_factory=list)

    @property
    def total_home(self) -> int:
        return sum(self.home)

    @property
    def total_away(self) -> int:
        return sum(self.away)


def goals_per_segment(game_facts, segments: list[Segment]) -> SegmentGoals:
    """Count home and away goals in each segment.

    A goal at minute ``m`` belongs to the segment whose half-open interval contains ``m``; a goal
    exactly on a boundary is attributed to the segment that starts there, matching the presence
    rule above. Own goals are credited to the team that benefits, which is what
    :func:`utils.football_data_utils.get_score` already resolves via ``goal_team_id``.

    Goals outside every segment are ignored. That happens in red-card matches when the feed keeps
    emitting events past the truncated ``end_of_game``, and those minutes are not part of any
    observation, so counting them would leak into a segment that did not contain them.
    """
    home_team_id = int(game_facts.home_team_id)
    score = get_score(game_facts.events, game_facts.df_teams)

    home_counts = [0] * len(segments)
    away_counts = [0] * len(segments)
    for minute, team_id in zip(score["expanded_minute"], score["goal_team_id"], strict=True):
        minute = float(minute)
        for segment in segments:
            if segment.start_minute <= minute < segment.end_minute:
                if int(team_id) == home_team_id:
                    home_counts[segment.index] += 1
                else:
                    away_counts[segment.index] += 1
                break

    return SegmentGoals(home=home_counts, away=away_counts)


def segments_from_rows(segment_rows, player_game_rows) -> list[Segment]:
    """Rebuild one game's segments from the database instead of from raw events.

    Stage 1 already persisted everything stage 2 needs: ``METRICS.GAME_SEGMENT`` holds the segment
    boundaries, and ``BASIS.PLAYER_GAME.on_minute`` / ``off_minute`` / ``is_home`` hold each
    player's presence interval. Applying the same :func:`is_present` rule to those intervals
    reproduces exactly the line-ups :func:`build_segments` derived in memory, so the plus-minus
    runner never has to touch the event feed or the xT model.

    Parameters
    ----------
    segment_rows
        ``GAME_SEGMENT`` rows for a single game, ordered by ``segment_index``.
    player_game_rows
        ``PLAYER_GAME`` rows for the same game.
    """
    home: list[int] = []
    away: list[int] = []
    intervals = [
        (
            int(row["player_id"]),
            float(row["on_minute"]),
            float(row["off_minute"]),
        )
        for row in player_game_rows
    ]
    is_home = {int(row["player_id"]): int(row["is_home"]) for row in player_game_rows}

    segments = []
    for row in sorted(segment_rows, key=lambda r: int(r["segment_index"])):
        start = float(row["start_minute"])
        end = float(row["end_minute"])
        for player_id, on, off in intervals:
            if is_present(on, off, start, end):
                (home if is_home[player_id] else away).append(player_id)
        segments.append(
            Segment(
                index=int(row["segment_index"]),
                start_minute=start,
                end_minute=end,
                home=frozenset(home),
                away=frozenset(away),
            )
        )
        home, away = [], []
    return segments
