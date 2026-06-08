import os
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

_engine = None
_SessionLocal = None


def _db_type():
    return os.environ.get("DB_TYPE", "postgres").lower()


def _get_engine():
    global _engine
    if _engine is None:
        db_type = _db_type()

        if db_type == "postgres":
            user = os.environ.get("PG_USER", "postgres")
            password = os.environ.get("PG_PASSWORD", "")
            host = os.environ.get("PG_HOST", "localhost")
            port = os.environ.get("PG_PORT", "5432")
            dbname = os.environ.get("PG_DBNAME", "packing_report")
            schema_map = {
                "BASIS": os.environ.get("PG_SCHEMA_BASIS", "public"),
                "METRICS": os.environ.get("PG_SCHEMA_METRICS", "public"),
                "SCRAPING": os.environ.get("PG_SCHEMA_SCRAPING", "public"),
            }
            _engine = create_engine(
                f"postgresql+psycopg://{user}:{password}@{host}:{port}/{dbname}",
                schema_translate_map=schema_map,
            )

        elif db_type == "oracle":
            username = os.environ.get("ORACLE_DB_USER", "ADMIN")
            password = os.environ.get("ORACLE_DB_PWD")
            dsn = os.environ.get("ORACLE_DSN", "most")
            config_dir = os.environ.get("ORACLE_CONFIG_DIR", "/etc/")
            _engine = create_engine(
                "oracle+oracledb://",
                connect_args={
                    "user": username,
                    "password": password,
                    "dsn": dsn,
                    "config_dir": config_dir,
                },
            )

        else:
            raise ValueError(f"Unsupported DB_TYPE '{db_type}'. Expected 'postgres' or 'oracle'.")

    return _engine


def _get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=_get_engine())
    return _SessionLocal


@contextmanager
def get_session():
    session = _get_session_factory()()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()
