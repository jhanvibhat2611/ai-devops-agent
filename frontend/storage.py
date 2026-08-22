import sqlite3
import os

from cryptography.fernet import Fernet


DB_NAME = "users.db"
KEY_FILE = "secret.key"


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

    connection.commit()
    connection.close()


# ============================================================
# USER FUNCTIONS
# ============================================================

def user_exists(username):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT username FROM users WHERE username = ?",
        (username,)
    )

    user = cursor.fetchone()

    connection.close()

    return user is not None


def verify_user(username, password):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT password
        FROM users
        WHERE username = ?
        """,
        (username,)
    )

    user = cursor.fetchone()

    connection.close()

    if user is None:
        return False

    return user[0] == password


def create_user(
    username,
    password,
    gitlab_username,
    gitlab_token
):

    # Encrypt the GitLab token before storing it
    encrypted_token = cipher.encrypt(
        gitlab_token.encode()
    ).decode()

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO users (
            username,
            password,
            gitlab_username,
            gitlab_token
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            username,
            password,
            gitlab_username,
            encrypted_token
        )
    )

    connection.commit()
    connection.close()


# ============================================================
# GET DECRYPTED GITLAB TOKEN
# ============================================================

def get_gitlab_token(username):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT gitlab_token
        FROM users
        WHERE username = ?
        """,
        (username,)
    )

    user = cursor.fetchone()

    connection.close()

    if user is None:
        return None

    encrypted_token = user[0]

    decrypted_token = cipher.decrypt(
        encrypted_token.encode()
    ).decode()

    return decrypted_token


# ============================================================
# MERGE REQUEST APPROVAL FUNCTIONS
# ============================================================

def save_merge_request_approval(
    mr_iid,
    username,
    status
):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO merge_request_approvals (
            mr_iid,
            username,
            status
        )
        VALUES (?, ?, ?)
        """,
        (
            mr_iid,
            username,
            status
        )
    )

    connection.commit()
    connection.close()


def get_merge_request_approvals(mr_iid):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            mr_iid,
            username,
            status,
            approved_at
        FROM merge_request_approvals
        WHERE mr_iid = ?
        ORDER BY approved_at DESC
        """,
        (mr_iid,)
    )

    approvals = cursor.fetchall()

    connection.close()

    return [
        {
            "mr_iid": approval[0],
            "username": approval[1],
            "status": approval[2],
            "approved_at": approval[3]
        }
        for approval in approvals
    ]

if __name__ == "__main__":
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT username, gitlab_token FROM users"
    )

    users = cursor.fetchall()

    for user in users:
        print(user)

    connection.close()