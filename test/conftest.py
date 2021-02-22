import os
from pathlib import Path

os.environ["PYTEST"] = "YES"

if Path("./validation.db").exists():
    os.remove(Path("./validation.db").absolute())
from sqlalchemy.engine import Engine
from sqlalchemy import event

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()