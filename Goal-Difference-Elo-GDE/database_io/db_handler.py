from sqlalchemy import create_engine
from sqlalchemy.orm import Session
class DB_handler:
    def __init__(self, db_path):
        engine = create_engine(f'sqlite:///{db_path}', echo=False)
        self.session = Session(engine)

