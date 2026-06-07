import os
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

_engine = None
_SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
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
