from database_io.db_handler import DB_handler
from database_io.models import Game, Player, PlayerGame, PlayerGameMetric, ScrapeLog
from database_io.models.scrape import FootballsquadsRaw

db = DB_handler()

session = db.player.session

session.query(PlayerGameMetric).delete()
session.query(Player).delete()
session.query(Game).delete()
session.query(PlayerGame).delete()
session.query(FootballsquadsRaw).delete()
session.query(ScrapeLog).delete()
session.commit()

session.close()
