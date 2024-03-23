import os 
print(os.getcwd())
from gde.database_io.db_handler import DB_handler
from gde.database_io.dims import Elo, Games
from gde.database_io.faks import Player
db = DB_handler("/home/morten/Develop/packing-report/gde/GDE.db")

db.elo.session.query(Elo).delete()
db.elo.session.commit()
db.player.session.query(Player).delete()
db.player.session.commit()
db.games.session.query(Games).delete()
db.games.session.commit()

db.games.session.close()