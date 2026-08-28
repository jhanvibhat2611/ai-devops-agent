import sqlite3
import os


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

DB_NAME = os.path.join(
    PROJECT_DIR,
    "frontend",
    "users.db"
)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():

    return sqlite3.connect(
        DB_NAME
    )


# ============================================================
# SAVE APPROVAL
# ============================================================

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


# ============================================================
# GET APPROVAL HISTORY
# ============================================================

def get_merge_request_approvals(
    mr_iid
):

    connection = get_connection()

    try:

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
            (
                mr_iid,
            )
        )

        approvals = cursor.fetchall()

        return [
            {
                "mr_iid": approval[0],
                "username": approval[1],
                "status": approval[2],
                "approved_at": approval[3]
            }
            for approval in approvals
        ]

    finally:

        connection.close()