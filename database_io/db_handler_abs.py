from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import os
import oracledb

class DB_handler_connection:
    def __init__(self):
        username = "ADMIN"
        password = os.environ.get("ORACLE_DB_PWD")
        dsn = "most"
        self.connection = oracledb.connect(user=username, password=password,
                            dsn=dsn, config_dir="/etc/")

        self.engine = create_engine('oracle+oracledb://', creator=lambda: self.connection)
        
        self.session = Session(self.engine)