import sqlite3
import os

from cryptography.fernet import Fernet


# ============================================================
# PROJECT PATHS
# ============================================================

BACKEND_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

PROJECT_DIR = os.path.dirname(
    BACKEND_DIR
)

FRONTEND_DIR = os.path.join(
    PROJECT_DIR,
    "frontend"
)

DB_NAME = os.path.join(
    FRONTEND_DIR,
    "users.db"
)

KEY_FILE = os.path.join(
    FRONTEND_DIR,
    "secret.key"
)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():

    return sqlite3.connect(
        DB_NAME
    )


# ============================================================
# ENCRYPTION
# ============================================================

def get_encryption_key():

    if not os.path.exists(
        KEY_FILE
    ):

        raise FileNotFoundError(
            f"Encryption key not found: {KEY_FILE}"
        )

    with open(
        KEY_FILE,
        "rb"
    ) as file:

        return file.read()


cipher = Fernet(
    get_encryption_key()
)


# ============================================================
# VERIFY USER
# ============================================================

def verify_user(
    username,
    password
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT password
        FROM users
        WHERE username = ?
        """,
        (
            username,
        )
    )

    user = cursor.fetchone()

    connection.close()

    if user is None:

        return False

    return user[0] == password


# ============================================================
# GET USER DETAILS
# ============================================================

def get_user(
    username
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            username,
            gitlab_username
        FROM users
        WHERE username = ?
        """,
        (
            username,
        )
    )

    user = cursor.fetchone()

    connection.close()

    if user is None:

        return None

    return {
        "id": user[0],
        "username": user[1],
        "gitlab_username": user[2]
    }


# ============================================================
# GET DECRYPTED GITLAB TOKEN
# ============================================================

def get_gitlab_token(
    username
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT gitlab_token
        FROM users
        WHERE username = ?
        """,
        (
            username,
        )
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

def update_gitlab_token(
    username,
    gitlab_token
):

    encrypted_token = cipher.encrypt(
        gitlab_token.encode()
    ).decode()

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE users
        SET gitlab_token = ?
        WHERE username = ?
        """,
        (
            encrypted_token,
            username
        )
    )

    connection.commit()
    connection.close()

    return True

# ============================================================
# CHECK IF USER EXISTS
# ============================================================

def user_exists(
    username
):

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE username = ?
            """,
            (
                username,
            )
        )

        user = cursor.fetchone()

        return user is not None

    finally:

        connection.close()


# ============================================================
# CREATE USER
# ============================================================

def create_user(
    username,
    password,
    gitlab_username,
    gitlab_token
):

    encrypted_token = cipher.encrypt(
        gitlab_token.encode()
    ).decode()

    connection = get_connection()

    try:

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

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()