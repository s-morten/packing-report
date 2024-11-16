from database_io.db_handler import DB_handler
from database_io.dims import Elo, Games
from database_io.faks import Player, Squads
db = DB_handler()

db.elo.session.query(Elo).delete()
db.elo.session.commit()
db.player.session.query(Player).delete()
db.player.session.commit()
db.games.session.query(Games).delete()
db.games.session.commit()
db.squads.session.query(Squads).delete()
db.squads.session.commit()


db.games.session.close()