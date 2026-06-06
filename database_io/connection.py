import os

import oracledb
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

load_dotenv()


class DB_handler_connection:
    def __init__(self):
        username = os.environ.get("ORACLE_DB_USER", "ADMIN")
        password = os.environ.get("ORACLE_DB_PWD")
        dsn = os.environ.get("ORACLE_DSN", "most")
        config_dir = os.environ.get("ORACLE_CONFIG_DIR", "/etc/")
        self.connection = oracledb.connect(user=username, password=password, dsn=dsn, config_dir=config_dir)

        self.engine = create_engine("oracle+oracledb://", creator=lambda: self.connection)

        self.session = Session(self.engine)
