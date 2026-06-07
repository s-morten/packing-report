from database_io.connection import get_session
from database_io.models import Game, Player, PlayerGame, PlayerGameMetric, ScrapeLog
from database_io.models.scrape import FootballsquadsRaw

with get_session() as session:
    session.query(PlayerGameMetric).delete()
    session.query(Player).delete()
    session.query(Game).delete()
    session.query(PlayerGame).delete()
    session.query(FootballsquadsRaw).delete()
    session.query(ScrapeLog).delete()
