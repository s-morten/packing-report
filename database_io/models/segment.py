from sqlalchemy import Column, Float, ForeignKey, Integer

from database_io.models.base import Base


class GameSegment(Base):
    """One contiguous stretch of a match during which the set of players on the pitch is constant.

    Segment boundaries are substitution minutes (plus 0 and the end of the match). A match is
    therefore split into ``len(boundaries) - 1`` segments, each of which yields exactly one
    observation for the plus-minus regression (see ``insights/metrics/high_level/xtpm``).

    Both dependent variables are stored so that the xT arm and the goal-difference arm of the
    model share one design matrix and can be compared without recomputing anything: the design
    matrix ``x`` depends only on who was on the pitch, never on the DV, so ``A = sum(w x x^T)``
    is identical for both. Only the right-hand side differs.

    Every value is from the perspective of the *home* team unless the name says otherwise.
    """

    __tablename__ = "GAME_SEGMENT"
    __table_args__ = {"schema": "METRICS"}

    game_id = Column(Integer, ForeignKey("BASIS.GAME.id"), primary_key=True)
    segment_index = Column(Integer, primary_key=True)

    start_minute = Column(Float)
    end_minute = Column(Float)
    duration_minutes = Column(Float)

    n_players_home = Column(Integer)
    n_players_away = Column(Integer)

    # xT arm: expected-threat value of every action in the segment, summed per side.
    xt_home = Column(Float)
    xt_away = Column(Float)
    net_xt = Column(Float)
    # Per-90 normalised dependent variable actually fed to the regression. Normalisation is what
    # keeps an 18-minute red-card-truncated segment on the same scale as a full half hour.
    net_xt_per90 = Column(Float)

    # Goal-difference arm: the classical plus-minus dependent variable, same normalisation.
    goals_home = Column(Integer)
    goals_away = Column(Integer)
    gd90 = Column(Float)
