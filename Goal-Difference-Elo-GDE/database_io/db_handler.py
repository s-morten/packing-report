import sqlite3

class DB_handler:
    def __init__(self, db_path):
        self.db_connection = sqlite3.connect(db_path)

