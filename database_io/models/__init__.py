__all__ = [
    "Birthday_Footballsquads",
    "FootballsquadsRaw",
    "Game",
    "Games",
    "Metric",
    "Player",
    "PlayerAlias",
    "PlayerGame",
    "PlayerGameMetric",
    "Prediction",
    "Processed_Footballsquads",
    "Schedule",
    "ScrapeLog",
    "Squads",
    "Team",
]

from database_io.models.game import Game
from database_io.models.legacy import (
    Birthday_Footballsquads,
    Games,
    Metric,
    Prediction,
    Processed_Footballsquads,
    Schedule,
    Squads,
)
from database_io.models.metric import PlayerGameMetric
from database_io.models.player import Player, PlayerAlias
from database_io.models.player_game import PlayerGame
from database_io.models.scrape import FootballsquadsRaw, ScrapeLog
from database_io.models.team import Team
