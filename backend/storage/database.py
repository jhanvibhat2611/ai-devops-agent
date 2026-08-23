import sqlite3
import os


BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

DB_NAME = os.path.join(
    BASE_DIR,
    "frontend",
    "users.db"
)


def get_connection():

    return sqlite3.connect(
        DB_NAME
    )


def save_merge_request_approval(
    mr_iid,
    username,
    status
):

    connection = get_connection()

    try:

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

        print(
            f"✅ Approval history saved for MR !{mr_iid}"
        )

    except Exception as error:

        connection.rollback()

        print(
            f"❌ Failed to save approval history: {error}"
        )

        raise

    finally:

        connection.close()