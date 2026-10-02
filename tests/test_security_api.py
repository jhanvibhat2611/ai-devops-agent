import base64
import hashlib
from datetime import datetime, timedelta, timezone
import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock
import jwt
import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from fastapi.testclient import TestClient
import main
from storage import auth, database, account_routes, approval_history


@pytest.fixture
def api(monkeypatch, tmp_path):
    path = str(tmp_path / "users.db")
    monkeypatch.setattr(auth, "DB_NAME", path)
    monkeypatch.setattr(database, "DB_NAME", path)
    monkeypatch.setattr(auth, "cipher", Fernet(Fernet.generate_key()))
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT UNIQUE,password TEXT,gitlab_username TEXT,gitlab_token TEXT)")
        for name in ("alice", "bob"):
            connection.execute("INSERT INTO users(username,password,gitlab_username,gitlab_token) VALUES (?,?,?,?)",
                (name, "legacy-password", name, auth.cipher.encrypt((name + "-token").encode()).decode()))
    main.chat_sessions.clear()
    main.proposals.clear()
    return TestClient(main.app)


def headers(name="alice"):
    token = jwt.encode({"sub": name, "exp": datetime.now(timezone.utc)+timedelta(hours=1)}, main.JWT_SECRET_KEY, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def gitlab(monkeypatch):
    calls = []
    def get(endpoint, project_id, token):
        calls.append((endpoint, project_id, token))
        if endpoint == "":
            return {"id": project_id, "name": f"repo-{project_id}", "path_with_namespace": f"owner/repo-{project_id}",
                    "default_branch": "main", "http_url_to_repo": f"https://gitlab.com/owner/repo-{project_id}.git"}
        if endpoint.startswith("merge_requests/"):
            return {"iid": 1, "source_branch": "feature", "source_project_id": project_id, "diff_refs": {"head_sha": "head-1", "base_sha": "base-1"}}
        return {"ok": True}
    monkeypatch.setattr(main.client, "get", get)
    monkeypatch.setattr(main.client, "pages", lambda endpoint, pid, token, params=None: calls.append((endpoint,pid,token)) or [])
    return calls


def test_login_migrates_legacy_password(api):
    assert api.post("/login", json={"username":"alice", "password":"wrong"}).status_code == 401
    response = api.post("/login", json={"username":"alice", "password":"legacy-password"})
    assert response.status_code == 200
    token = response.json()["access_token"]
    assert jwt.decode(token, main.JWT_SECRET_KEY, algorithms=["HS256"])["sub"] == "alice"
    with sqlite3.connect(auth.DB_NAME) as connection:
        stored = connection.execute("SELECT password FROM users WHERE username='alice'").fetchone()[0]
    assert stored.startswith("scrypt$")
    assert auth.verify_user("alice", "legacy-password")
    assert not auth.verify_user("alice", "wrong")


def test_registration_hashes_and_encrypts(api, monkeypatch):
    monkeypatch.setattr(account_routes.requests, "get", lambda *a, **k: SimpleNamespace(status_code=200, json=lambda: {"username":"gitlab-user"}))
    result = api.post("/register", json={"username":"new", "password":"password", "gitlab_token":"new-token"})
    assert result.status_code == 200
    with sqlite3.connect(auth.DB_NAME) as connection:
        password, token = connection.execute("SELECT password,gitlab_token FROM users WHERE username='new'").fetchone()
    assert password.startswith("scrypt$") and token != "new-token"
    assert auth.get_gitlab_token("new") == "new-token"


@pytest.mark.parametrize("path", ["/branches", "/merge-requests", "/commit/sha", "/pipeline/1", "/merge-request/1", "/review/1", "/suggest/1", "/search?query=x", "/merge-request/1/approval-history", "/merge-request/1/code-diffs", "/merge-request/1/code-diffs/raw?file_path=x.py", "/gitlab/projects"])
def test_get_routes_reject_missing_and_invalid_jwt(api, path):
    assert api.get(path).status_code == 401
    assert api.get(path, headers={"Authorization":"Bearer invalid"}).status_code == 401


@pytest.mark.parametrize("path,body", [("/create-branch",{"branch_name":"feature","ref":"main"}), ("/create-merge-request",{"source_branch":"f","target_branch":"main","title":"test"}), ("/merge-request/1/comment",{"body":"test"}), ("/review/1/post",{"review_id":"x"}), ("/suggest/1/post",{"suggestion":"x"}), ("/suggest/1/accept",{"proposal_id":"x"}), ("/chat",{"message":"x"}), ("/chat/decision",{"thread_id":"x","project_id":1,"approved":True})])
def test_write_routes_require_jwt(api, path, body):
    assert api.post(path,json=body).status_code == 401


def test_repository_isolation(api, gitlab):
    for project, user in ((11,"alice"),(22,"bob")):
        assert api.get(f"/branches?project_id={project}", headers=headers(user)).status_code == 200
        assert ("repository/branches",project,user+"-token") in gitlab
    assert api.get("/branches",headers=headers()).status_code == 422
    with pytest.raises(HTTPException):
        main.client.request("GET", "repository/branches", None, None)


def test_inline_pending_request_and_binding(api, gitlab, monkeypatch):
    graph = Mock()
    graph.invoke.return_value = {"__interrupt__":[SimpleNamespace(value={"analysis":"plan","target_file":"generated_feature.py"})]}
    monkeypatch.setattr(main,"graph",graph)
    initial = api.post("/chat",json={"message":"Multiply a number by 3"},headers=headers()).json()
    assert initial["type"] == "repository_selection"
    graph.invoke.assert_not_called()
    thread = initial["thread_id"]
    selected = api.post("/chat",json={"message":"", "thread_id":thread,"project_id":22,"clone_url":"https://evil.example/repo.git"},headers=headers())
    assert selected.status_code == 200
    state = graph.invoke.call_args.args[0]
    assert state["user_request"] == "Multiply a number by 3"
    assert state["gitlab_project_id"] == 22
    assert state["gitlab_clone_url"] == "https://gitlab.com/owner/repo-22.git"
    assert api.post("/chat",json={"message":"switch","thread_id":thread,"project_id":11},headers=headers()).status_code == 409
    assert api.post("/chat",json={"message":"steal","thread_id":thread},headers=headers("bob")).status_code == 404


def test_approval_ownership_and_idempotency(api, gitlab, monkeypatch):
    main.chat_sessions["thread"] = {"username":"alice","project_id":11,"status":"waiting_for_approval","workflow_id":"graph-thread"}
    graph = Mock()
    graph.get_state.return_value = SimpleNamespace(values={"username":"alice","gitlab_project_id":11})
    graph.invoke.return_value = {"mr_url":"https://gitlab.example/mr/1"}
    monkeypatch.setattr(main,"graph",graph)
    body = {"thread_id":"thread","workflow_id":"graph-thread","project_id":11,"approved":True}
    assert api.post("/chat/decision",json=body,headers=headers("bob")).status_code == 404
    assert api.post("/chat/decision",json={**body,"project_id":22},headers=headers()).status_code == 409
    first = api.post("/chat/decision",json=body,headers=headers())
    second = api.post("/chat/decision",json=body,headers=headers())
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    graph.invoke.assert_called_once()
    # A delayed retry must not approve a subsequent workflow in the same chat.
    main.chat_sessions["thread"].update(status="waiting_for_approval", workflow_id="new-workflow")
    assert api.post("/chat/decision",json=body,headers=headers()).json() == first.json()
    graph.invoke.assert_called_once()


def test_review_posts_exact_stored_text_and_stale_rejected(api, gitlab, monkeypatch):
    repo = main.authorize_project("alice",11)
    review_id = main.save_proposal(repo,1,"head-1","review",text="Exact displayed review")
    post = Mock(return_value={"id":77})
    monkeypatch.setattr(main.client,"post",post)
    result = api.post("/review/1/post?project_id=11",json={"review_id":review_id},headers=headers())
    assert result.json()["status"] == "posted"
    assert post.call_args.args[1]["body"] == "Exact displayed review"
    stale = main.save_proposal(repo,1,"old-head","review",text="Old review")
    assert api.post("/review/1/post?project_id=11",json={"review_id":stale},headers=headers()).status_code == 409
    assert api.post("/review/1/post?project_id=22",json={"review_id":review_id},headers=headers()).status_code == 404


def test_suggestion_atomic_revision_and_write_failure(api, gitlab, monkeypatch):
    repo = main.authorize_project("alice",11)
    proposal = main.save_proposal(repo,1,"head-1","suggestion",file="file.py",current_code="return 2",suggested_code="return 3",source_branch="feature",content_sha256=hashlib.sha256(b"def f(): return 2").hexdigest())
    monkeypatch.setattr(main.client,"file_data",lambda *args: {"content":base64.b64encode(b"def f(): return 2").decode(),"last_commit_id":"file-head"})
    post = Mock(return_value={"id":"commit","web_url":"commit-url"})
    monkeypatch.setattr(main.client,"post",post)
    result = api.post("/suggest/1/accept?project_id=11",json={"proposal_id":proposal},headers=headers())
    assert result.json()["status"] == "accepted"
    payload = post.call_args.args[1]
    assert payload["branch"] == "feature"
    assert payload["actions"][0]["last_commit_id"] == "file-head"
    assert post.call_args.args[2:] == (11,"alice-token")
    post.side_effect = HTTPException(400,"GitLab rejected write")
    failed = api.post("/suggest/1/post?project_id=11",json={"suggestion":"text"},headers=headers())
    assert failed.status_code == 400
    assert failed.json().get("status") != "posted"


@pytest.mark.parametrize("revision,content", [("stale-head", "def f(): return 2"), ("head-1", "# concurrent edit\ndef f(): return 2")])
def test_stale_suggestions_cannot_commit(api, gitlab, monkeypatch, revision, content):
    repo = main.authorize_project("alice",11)
    proposal = main.save_proposal(repo,1,revision,"suggestion",file="file.py",current_code="return 2",suggested_code="return 3",source_branch="feature",content_sha256=hashlib.sha256(b"def f(): return 2").hexdigest())
    monkeypatch.setattr(main.client,"file_data",lambda *args: {"content":base64.b64encode(content.encode()).decode(),"last_commit_id":"new-file-head"})
    post = Mock()
    monkeypatch.setattr(main.client,"post",post)
    result = api.post("/suggest/1/accept?project_id=11",json={"proposal_id":proposal},headers=headers())
    assert result.status_code == 409
    post.assert_not_called()


def test_history_migration_preserves_unknown_project_rows(api):
    with sqlite3.connect(auth.DB_NAME) as connection:
        connection.execute("CREATE TABLE merge_request_approvals(id INTEGER PRIMARY KEY,mr_iid INTEGER,username TEXT,status TEXT,approved_at TEXT)")
        connection.execute("INSERT INTO merge_request_approvals VALUES(1,1,'legacy','approved','old-date')")
    approval_history.save_merge_request_approval(1,"alice","approved",11,"thread-a")
    approval_history.save_merge_request_approval(1,"bob","approved",22,"thread-b")
    assert [r["username"] for r in approval_history.get_merge_request_approvals(1,11)] == ["alice"]
    assert [r["username"] for r in approval_history.get_merge_request_approvals(1,22)] == ["bob"]
    with sqlite3.connect(auth.DB_NAME) as connection:
        assert connection.execute("SELECT count(*) FROM merge_request_approvals").fetchone()[0] == 3


def test_webhook_auth_and_persistent_deduplication(api, monkeypatch):
    monkeypatch.setenv("GITLAB_WEBHOOK_SECRET","hook-secret")
    monkeypatch.setenv("GITLAB_WEBHOOK_PROJECT_IDS","11")
    monkeypatch.setenv("GITLAB_WEBHOOK_TOKEN","service-token")
    payload = {"project":{"id":11},"object_kind":"push", "commits":[{"message":"Apply AI code suggestion test"}]}
    assert api.post("/webhook/gitlab",json=payload).status_code == 401
    hdr = {"X-Gitlab-Token":"hook-secret","X-Gitlab-Event-UUID":"unique"}
    assert api.post("/webhook/gitlab",json=payload,headers=hdr).json()["status"] == "ignored"
    assert api.post("/webhook/gitlab",json=payload,headers=hdr).json()["status"] == "duplicate"
    assert api.post("/webhook/gitlab",json={"project":{"id":22}},headers=hdr).status_code == 403
