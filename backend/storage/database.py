"""Shared SQLite location. Migrations retain existing rows and local files."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3

DB_NAME = str(Path(__file__).resolve().parents[2] / "frontend" / "users.db")


@contextmanager
def get_connection():
    connection = sqlite3.connect(DB_NAME, timeout=30)
    try:
        with connection:
            yield connection
    finally:
        connection.close()
