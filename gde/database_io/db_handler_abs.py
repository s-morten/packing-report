from sqlalchemy import create_engine
from sqlalchemy.orm import Session

class DB_handler_abs:
    def __init__(self, db_path):
        print("here", f" {db_path}")
        self.engine = create_engine(f'sqlite:///{db_path}', echo=False)
        self.session = Session(self.engine)

