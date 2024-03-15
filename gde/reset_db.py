from database_io import DB_player

db = DB_player("/home/morten/Develop/packing-report/Goal-Difference-Elo-GDE/GDE.db")

db.session.query(db.Elo).delete()
db.session.commit()
db.session.query(db.Player).delete()
db.session.commit()
db.session.query(db.Games).delete()
db.session.commit()

db.session.close()