"""Non-destructive project identity migration for existing approval history."""
from .database import get_connection


def migrate(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS merge_request_approvals (
        id INTEGER PRIMARY KEY AUTOINCREMENT, mr_iid INTEGER NOT NULL,
        username TEXT NOT NULL, status TEXT NOT NULL,
        approved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, project_id INTEGER, thread_id TEXT)""")
    columns = {row[1] for row in connection.execute("PRAGMA table_info(merge_request_approvals)")}
    for name, kind in (("project_id", "INTEGER"), ("thread_id", "TEXT")):
        if name not in columns:
            connection.execute(f"ALTER TABLE merge_request_approvals ADD COLUMN {name} {kind}")
    connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS approval_workflow ON merge_request_approvals(thread_id) WHERE thread_id IS NOT NULL")


def save_merge_request_approval(mr_iid, username, status, project_id, thread_id=None):
    with get_connection() as connection:
        migrate(connection)
        connection.execute("INSERT OR IGNORE INTO merge_request_approvals (project_id,mr_iid,username,status,thread_id) VALUES (?,?,?,?,?)",
                           (project_id, mr_iid, username, status, thread_id))


def get_merge_request_approvals(mr_iid, project_id):
    with get_connection() as connection:
        migrate(connection)
        rows = connection.execute("SELECT project_id,mr_iid,username,status,approved_at,thread_id FROM merge_request_approvals WHERE project_id=? AND mr_iid=? ORDER BY approved_at DESC", (project_id, mr_iid))
        return [dict(zip(("project_id", "mr_iid", "username", "status", "approved_at", "thread_id"), row)) for row in rows]
