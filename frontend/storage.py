import sqlite3
import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from backend.storage.approval_history import migrate

from cryptography.fernet import Fernet


BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DB_NAME = os.path.join(
    BASE_DIR,
    "users.db"
)

KEY_FILE = os.path.join(
    BASE_DIR,
    "secret.key"
)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():
    return sqlite3.connect(DB_NAME)


# ============================================================
# ENCRYPTION KEY
# ============================================================

def get_encryption_key():

    if not os.path.exists(KEY_FILE):

        if os.path.exists(DB_NAME):
            with sqlite3.connect(DB_NAME) as connection:
                table = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
                if table and connection.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                    raise RuntimeError("Existing accounts require their original secret.key. Restore that key; do not replace it.")

        key = Fernet.generate_key()

        with open(KEY_FILE, "wb") as file:
            file.write(key)

    else:

        with open(KEY_FILE, "rb") as file:
            key = file.read()

    return key


cipher = Fernet(
    get_encryption_key()
)


# ============================================================
# INITIALIZE DATABASE
# ============================================================

def initialize_database():

    connection = get_connection()
    cursor = connection.cursor()

    # --------------------------------------------------------
    # USERS TABLE
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            gitlab_username TEXT NOT NULL,
            gitlab_token TEXT NOT NULL
        )
    """)

    # --------------------------------------------------------
    # MERGE REQUEST APPROVAL HISTORY
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS merge_request_approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mr_iid INTEGER NOT NULL,
            username TEXT NOT NULL,
            status TEXT NOT NULL,
            approved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    migrate(connection)
    connection.commit()
    connection.close()
