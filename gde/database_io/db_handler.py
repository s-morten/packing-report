import sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from gde.database_io.dims.player import DB_player

class DB_handler:
    def __init__(self, db_path):
        engine = create_engine(f'sqlite:///{db_path}', echo=False)
        self.session = Session(engine)

        self.player = DB_player(self.session)
        #self.db_connection = sqlite3.connect(db_path)

