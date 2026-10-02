"""Authenticated repository-aware FastAPI application.

Thread checkpoints and review proposals are process-local: run one API worker.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import threading
import uuid
from dataclasses import dataclass
from urllib.parse import quote

from dotenv import load_dotenv
load_dotenv()
if not os.getenv("JWT_SECRET_KEY", "").strip():
    raise RuntimeError("JWT_SECRET_KEY must be configured before starting the backend.")

import jwt
from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from langgraph.types import Command
from workflow.graph import graph
from workflow.safety import target_path
from storage.auth import get_gitlab_token, get_user
from storage.database import get_connection
from storage.approval_history import get_merge_request_approvals
from storage.account_routes import app as accounts
from gitlab import client
from elasticsearch_client import search_merge_requests, bulk_index_merge_requests, get_mr_context_for_suggestions
from ai_review import review_code, suggest_code

app = FastAPI()
app.include_router(accounts)
security = HTTPBearer(auto_error=False)
JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
chat_sessions = {}
proposals = {}
state_lock = threading.RLock()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials is None:
        raise HTTPException(401, "Authentication required.")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=["HS256"], options={"require": ["exp", "sub"]})
        username = payload["sub"]
        if not isinstance(username, str) or not username or not get_user(username):
            raise HTTPException(401, "Invalid authentication token.")
        return username
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid or expired authentication token.") from None


@dataclass
class Repository:
    username: str
    project_id: int
    token: str
    project: dict


def authorize_project(username, project_id):
    token = get_gitlab_token(username)
    if not token:
        raise HTTPException(400, "No GitLab token configured for this account.")
    project = client.get("", project_id, token)
    return Repository(username, project_id, token, project)


def selected_repository(project_id: int = Query(gt=0), username: str = Depends(get_current_user)):
    return authorize_project(username, project_id)


class BranchRequest(BaseModel):
    branch_name: str
    ref: str

class MergeRequest(BaseModel):
    source_branch: str
    target_branch: str
    title: str

class CommentRequest(BaseModel):
    body: str

class ChatRequest(BaseModel):
    message: str = ""
    thread_id: str | None = None
    project_id: int | None = Field(default=None, gt=0)
    default_branch: str | None = None
    clone_url: str | None = None

class ChatDecisionRequest(BaseModel):
    thread_id: str
    workflow_id: str
    project_id: int = Field(gt=0)
    approved: bool
    branch_name: str | None = None
    use_existing_branch: bool = False

class PostSuggestionRequest(BaseModel):
    suggestion: str

class AcceptSuggestionRequest(BaseModel):
    proposal_id: str

class PostReviewRequest(BaseModel):
    review_id: str


def make_gitlab_request(endpoint, project_id=None, gitlab_token=None):
    return client.get(endpoint, project_id, gitlab_token)


def make_gitlab_post_request(endpoint, payload, project_id=None, gitlab_token=None):
    return client.post(endpoint, payload, project_id, gitlab_token)


def create_gitlab_branch(branch_name, ref, project_id=None, gitlab_token=None):
    result = client.post("repository/branches", {"branch": branch_name, "ref": ref}, project_id, gitlab_token)
    if not result.get("name"):
        raise HTTPException(502, "GitLab did not confirm branch creation.")
    return result


def create_gitlab_merge_request(source, target, title, project_id=None, gitlab_token=None):
    result = client.post("merge_requests", {"source_branch": source, "target_branch": target, "title": title}, project_id, gitlab_token)
    if not result.get("iid") or not result.get("web_url"):
        raise HTTPException(502, "GitLab did not confirm Merge Request creation.")
    return result


@app.get("/")
def home():
    return {"message": "Welcome to GitLab Resource Management API"}

@app.get("/branches")
def branches(repo: Repository = Depends(selected_repository)):
    return client.pages("repository/branches", repo.project_id, repo.token)

@app.get("/commit/{commit_sha}")
def commit(commit_sha: str, repo: Repository = Depends(selected_repository)):
    return client.get(f"repository/commits/{quote(commit_sha, safe='')}", repo.project_id, repo.token)

@app.get("/pipeline/{pipeline_id}")
def pipeline(pipeline_id: int, repo: Repository = Depends(selected_repository)):
    return client.get(f"pipelines/{pipeline_id}", repo.project_id, repo.token)

@app.post("/create-branch")
def create_branch(request: BranchRequest, repo: Repository = Depends(selected_repository)):
    return create_gitlab_branch(request.branch_name, request.ref, repo.project_id, repo.token)

@app.post("/create-merge-request")
def create_merge_request(request: MergeRequest, repo: Repository = Depends(selected_repository)):
    return create_gitlab_merge_request(request.source_branch, request.target_branch, request.title, repo.project_id, repo.token)

@app.get("/merge-requests")
def merge_requests(repo: Repository = Depends(selected_repository)):
    rows = client.pages("merge_requests", repo.project_id, repo.token)
    bulk_index_merge_requests([{"project_id": repo.project_id, "mr_id": mr["iid"], "title": mr.get("title", ""),
        "description": mr.get("description", ""), "state": mr.get("state"), "author": (mr.get("author") or {}).get("name", "")} for mr in rows])
    return rows

@app.get("/merge-request/{mr_iid}")
def get_merge_request(mr_iid: int, repo: Repository = Depends(selected_repository)):
    return client.get(f"merge_requests/{mr_iid}", repo.project_id, repo.token)

@app.post("/merge-request/{mr_iid}/comment")
def comment(mr_iid: int, request: CommentRequest, repo: Repository = Depends(selected_repository)):
    result = client.post(f"merge_requests/{mr_iid}/notes", {"body": request.body}, repo.project_id, repo.token)
    if not result.get("id"):
        raise HTTPException(502, "GitLab did not confirm the comment.")
    return result

@app.get("/search")
def search(query: str, repo: Repository = Depends(selected_repository)):
    return search_merge_requests(query, repo.project_id)

@app.get("/merge-request/{mr_iid}/approval-history")
def approval_history(mr_iid: int, repo: Repository = Depends(selected_repository)):
    return {"project_id": repo.project_id, "mr_iid": mr_iid, "approvals": get_merge_request_approvals(mr_iid, repo.project_id)}

@app.get("/gitlab/projects")
def projects(username: str = Depends(get_current_user)):
    token = get_gitlab_token(username)
    if not token:
        raise HTTPException(400, "No GitLab token configured.")
    rows, page = [], 1
    while True:
        data, headers = client.api_request("GET", "projects", token, params={"membership": "true", "simple": "true",
            "per_page": 100, "page": page, "order_by": "last_activity_at", "sort": "desc"})
        rows.extend(data)
        following = headers.get("X-Next-Page")
        if not following:
            break
        page = int(following)
    keys = ("id", "name", "path", "path_with_namespace", "web_url", "default_branch", "http_url_to_repo",
            "ssh_url_to_repo", "visibility", "last_activity_at")
    result = [{**{k: row.get(k) for k in keys}, "namespace": (row.get("namespace") or {}).get("full_path")} for row in rows]
    return {"projects": result, "total_projects": len(result)}


def head(mr):
    value = (mr.get("diff_refs") or {}).get("head_sha") or mr.get("sha")
    if not value:
        raise HTTPException(409, "MR revision is not ready; retry after GitLab computes its diff.")
    return value


def get_file_content_by_ref(file_path, ref_sha, project_id, token):
    data = client.file_data(file_path, ref_sha, project_id, token)
    try:
        return base64.b64decode(data["content"]).decode("utf-8")
    except (ValueError, UnicodeDecodeError, KeyError):
        return "(Binary or undecodable file)"


def code_diffs(mr_iid, repo):
    mr = get_merge_request(mr_iid, repo)
    refs = mr.get("diff_refs") or {}
    base, revision = refs.get("base_sha"), head(mr)
    if not base:
        raise HTTPException(409, "MR base revision unavailable.")
    changes = client.pages(f"merge_requests/{mr_iid}/diffs", repo.project_id, repo.token)
    files = []
    for change in changes:
        old, new = change.get("old_path"), change.get("new_path")
        files.append({**change, "diff_git": change.get("diff", ""),
            "original_code": None if change.get("new_file") else get_file_content_by_ref(old, base, repo.project_id, repo.token),
            "modified_code": None if change.get("deleted_file") else get_file_content_by_ref(new, revision, repo.project_id, repo.token)})
    return {"mr_iid": mr_iid, "project_id": repo.project_id, "title": mr.get("title"), "source_branch": mr.get("source_branch"),
            "target_branch": mr.get("target_branch"), "base_sha": base, "head_sha": revision, "files": files, "total_files": len(files)}

@app.get("/merge-request/{mr_iid}/code-diffs")
def get_code_diffs(mr_iid: int, repo: Repository = Depends(selected_repository)):
    return code_diffs(mr_iid, repo)

@app.get("/merge-request/{mr_iid}/code-diffs/raw")
def raw_code(mr_iid: int, file_path: str, version: str = "modified", repo: Repository = Depends(selected_repository)):
    if version not in ("original", "modified"):
        raise HTTPException(400, "Version must be original or modified.")
    data = code_diffs(mr_iid, repo)
    key = "old_path" if version == "original" else "new_path"
    for file in data["files"]:
        if file.get(key) == file_path and file[f"{version}_code"] is not None:
            return {"file_path": file_path, "version": version, "content": file[f"{version}_code"],
                    "commit_sha": data["base_sha" if version == "original" else "head_sha"]}
    raise HTTPException(404, "File is not present in this MR revision.")


def save_proposal(repo, mr_iid, revision, kind, **data):
    proposal_id = str(uuid.uuid4())
    with state_lock:
        proposals[proposal_id] = dict(username=repo.username, project_id=repo.project_id, mr_iid=mr_iid,
            revision=revision, kind=kind, **data)
    return proposal_id


def owned_proposal(proposal_id, repo, mr_iid, kind):
    item = proposals.get(proposal_id)
    if not item or (item["username"], item["project_id"], item["mr_iid"], item["kind"]) != (repo.username, repo.project_id, mr_iid, kind):
        raise HTTPException(404, "Proposal not found for this account/project/MR.")
    return item

@app.get("/review/{mr_iid}")
def review_merge_request(mr_iid: int, repo: Repository = Depends(selected_repository)):
    data = code_diffs(mr_iid, repo)
    review = review_code("\n".join(f"File: {f['new_path']}\n{f['diff_git']}" for f in data["files"])) if data["files"] else "No changes found."
    review_id = save_proposal(repo, mr_iid, data["head_sha"], "review", text=review)
    return {"type": "review", "mr_iid": mr_iid, "review": review, "review_id": review_id, "head_sha": data["head_sha"]}

@app.post("/review/{mr_iid}/post")
def post_review(mr_iid: int, request: PostReviewRequest, repo: Repository = Depends(selected_repository)):
    with state_lock:
        item = owned_proposal(request.review_id, repo, mr_iid, "review")
        if item.get("result"):
            return item["result"]
        if head(get_merge_request(mr_iid, repo)) != item["revision"]:
            raise HTTPException(409, "Stale review: MR changed. Generate a new review.")
        result = client.post(f"merge_requests/{mr_iid}/notes", {"body": item["text"]}, repo.project_id, repo.token)
        if not result.get("id"):
            raise HTTPException(502, "GitLab did not confirm the posted review.")
        item["result"] = {"status": "posted", "review": item["text"], "note_id": result["id"]}
        return item["result"]

@app.get("/suggest/{mr_iid}")
def suggest_merge_request(mr_iid: int, repo: Repository = Depends(selected_repository)):
    data = code_diffs(mr_iid, repo)
    files = [{"file": f["new_path"], "content": f["modified_code"]} for f in data["files"] if f["modified_code"] is not None]
    context = get_mr_context_for_suggestions(mr_iid, data.get("title", ""), project_id=repo.project_id)
    if not files:
        return {"type": "suggestion", "mr_iid": mr_iid, "suggestions": []}
    raw = suggest_code(files, context)
    try:
        suggestions = json.loads(raw[raw.index("{"):raw.rindex("}")+1]).get("suggestions", [])
    except (ValueError, TypeError):
        raise HTTPException(502, "AI returned invalid suggestions.") from None
    by_path = {f["file"]: f["content"] for f in files}
    accepted = []
    for item in suggestions:
        if not isinstance(item, dict):
            continue
        path, current, suggested = item.get("file"), item.get("current_code"), item.get("suggested_code")
        if path not in by_path or not isinstance(current, str) or not current or not isinstance(suggested, str):
            continue
        if by_path[path].count(current) != 1:
            continue
        item["proposal_id"] = save_proposal(repo, mr_iid, data["head_sha"], "suggestion", file=path,
            current_code=current, suggested_code=suggested, source_branch=data["source_branch"],
            content_sha256=hashlib.sha256(by_path[path].encode()).hexdigest())
        accepted.append(item)
    return {"type": "suggestion", "mr_iid": mr_iid, "suggestions": accepted}

@app.post("/suggest/{mr_iid}/post")
def post_suggestion(mr_iid: int, request: PostSuggestionRequest, repo: Repository = Depends(selected_repository)):
    result = client.post(f"merge_requests/{mr_iid}/notes", {"body": request.suggestion}, repo.project_id, repo.token)
    if not result.get("id"):
        raise HTTPException(502, "GitLab did not confirm the note.")
    return {"status": "posted", "note_id": result["id"]}

@app.post("/suggest/{mr_iid}/accept")
def accept_suggestion(mr_iid: int, request: AcceptSuggestionRequest, repo: Repository = Depends(selected_repository)):
    with state_lock:
        item = owned_proposal(request.proposal_id, repo, mr_iid, "suggestion")
        if item.get("result"):
            return item["result"]
        mr = get_merge_request(mr_iid, repo)
        if mr.get("source_project_id", repo.project_id) != repo.project_id:
            raise HTTPException(409, "Fork MR writes require separate source-project authorization.")
        if head(mr) != item["revision"] or mr["source_branch"] != item["source_branch"]:
            raise HTTPException(409, "Stale suggestion: regenerate for the current MR revision.")
        data = client.file_data(item["file"], mr["source_branch"], repo.project_id, repo.token)
        content = base64.b64decode(data["content"]).decode("utf-8")
        if (hashlib.sha256(content.encode()).hexdigest() != item["content_sha256"]
                or content.count(item["current_code"]) != 1 or not data.get("last_commit_id")):
            raise HTTPException(409, "File changed or replacement is ambiguous; regenerate suggestion.")
        result = client.post("repository/commits", {"branch": mr["source_branch"],
            "commit_message": f"Apply AI code suggestion to {item['file']}", "actions": [{"action": "update",
            "file_path": item["file"], "content": content.replace(item["current_code"], item["suggested_code"], 1),
            "last_commit_id": data["last_commit_id"]}]}, repo.project_id, repo.token)
        if not result.get("id"):
            raise HTTPException(502, "GitLab did not confirm the commit.")
        item["result"] = {"status": "accepted", "commit_sha": result["id"], "commit_url": result.get("web_url", "")}
        return item["result"]


def session_for(thread_id, username):
    session = chat_sessions.get(thread_id)
    if not session or session["username"] != username:
        raise HTTPException(404, "Thread not found for this account.")
    return session


def workflow_response(result, thread_id):
    interrupts = result.get("__interrupt__", [])
    if interrupts:
        return {"status": "waiting_for_approval", "thread_id": thread_id, **interrupts[0].value}
    return {"status": "completed", "thread_id": thread_id, "result": result, "mr_url": result.get("mr_url", "")}

@app.post("/chat")
def chat(request: ChatRequest, username: str = Depends(get_current_user)):
    with state_lock:
        thread_id = request.thread_id or str(uuid.uuid4())
        if request.thread_id:
            session = session_for(thread_id, username)
        else:
            session = {"username": username, "status": "idle"}
            chat_sessions[thread_id] = session
        if session["status"] in ("running", "waiting_for_approval", "failed"):
            raise HTTPException(409, "Resolve this workflow before continuing; use New Chat for a separate workflow.")
        bound = session.get("project_id")
        if bound and request.project_id and bound != request.project_id:
            raise HTTPException(409, "Repository is bound to this thread. Change repository starts a new chat.")
        project_id = bound or request.project_id
        if not project_id:
            if not request.message.strip():
                raise HTTPException(400, "Enter a development request.")
            session.setdefault("pending_message", request.message.strip())
            return {"type": "repository_selection", "thread_id": thread_id,
                    "message": "Select an authorized GitLab repository to continue your request."}
        repo = authorize_project(username, project_id)
        session["project_id"] = project_id
        message = session.get("pending_message") or request.message.strip()
        if not message:
            raise HTTPException(400, "Enter a development request.")
        session["status"] = "running"
    try:
        lower = message.lower()
        match = re.search(r"(?:mr|merge request)\s*!?(\d+)", lower)
        intent = "review" if "review" in lower else "suggestion" if "suggest" in lower else None
        mr_iid = int(match.group(1)) if match else None
        if message.isdigit() and session.get("intent"):
            mr_iid, intent = int(message), session["intent"]
        if intent and (match or "mr" in lower or "merge request" in lower or message.isdigit()):
            if mr_iid is None:
                rows = client.pages("merge_requests", project_id, repo.token, {"state": "opened"})
                session["intent"] = intent
                response = {"type": "mr_selection", "intent": intent, "message": "Select a Merge Request.",
                    "merge_requests": [{"mr_iid": r["iid"], "title": r["title"], "source_branch": r["source_branch"]} for r in rows]}
            else:
                response = review_merge_request(mr_iid, repo) if intent == "review" else suggest_merge_request(mr_iid, repo)
                session.pop("intent", None)
            response["thread_id"] = thread_id
            next_status = "idle"
        else:
            branch = repo.project.get("default_branch")
            if not branch:
                raise HTTPException(400, "Initialize a default branch in this repository first.")
            target = target_path(os.getenv("GENERATED_CODE_FILE", "generated_feature.py"))
            # Each development request gets a fresh graph state while retaining conversation binding.
            workflow_id = str(uuid.uuid4())
            session["workflow_id"] = workflow_id
            result = graph.invoke({"username": username, "gitlab_project_id": project_id,
                "gitlab_default_branch": branch, "gitlab_clone_url": repo.project.get("http_url_to_repo", ""),
                "user_request": message, "thread_id": workflow_id, "target_file": target},
                config={"configurable": {"thread_id": workflow_id}})
            response = workflow_response(result, thread_id)
            response["workflow_id"] = workflow_id
            next_status = response["status"]
        response["repository"] = {k: repo.project.get(k) for k in ("id", "name", "path_with_namespace", "default_branch", "http_url_to_repo")}
        with state_lock:
            session.pop("pending_message", None)
            session.update(status=next_status, response=response)
        return response
    except Exception:
        with state_lock:
            session["status"] = "failed"
        raise

@app.post("/chat/decision")
def chat_decision(request: ChatDecisionRequest, username: str = Depends(get_current_user)):
    with state_lock:
        session = session_for(request.thread_id, username)
        if request.project_id != session.get("project_id"):
            raise HTTPException(409, "Project does not match the thread binding.")
        authorize_project(username, request.project_id)
        previous = session.get("decisions", {}).get(request.workflow_id)
        if previous:
            return previous
        if request.workflow_id != session.get("workflow_id"):
            raise HTTPException(409, "Decision does not match the current workflow proposal.")
        if session["status"] != "waiting_for_approval":
            raise HTTPException(409, "Workflow is not awaiting approval; do not retry partial writes.")
        config = {"configurable": {"thread_id": session["workflow_id"]}}
        values = graph.get_state(config).values
        if values.get("username") != username or values.get("gitlab_project_id") != request.project_id:
            raise HTTPException(403, "Workflow ownership mismatch.")
        session["status"] = "running"
    try:
        update = {}
        if request.approved and request.branch_name:
            update = {"branch_name": request.branch_name, "use_existing_branch": request.use_existing_branch}
        result = graph.invoke(Command(update=update, resume=request.approved), config=config)
        response = workflow_response(result, request.thread_id) if request.approved else {
            "status": "rejected", "thread_id": request.thread_id, "message": "Workflow rejected."}
        response["workflow_id"] = request.workflow_id
        with state_lock:
            session.setdefault("decisions", {})[request.workflow_id] = response
            session.update(status=response["status"], response=response)
        return response
    except Exception:
        with state_lock:
            session["status"] = "failed"
        raise

@app.post("/webhook/gitlab")
def webhook(payload: dict, x_gitlab_token: str | None = Header(default=None),
            x_gitlab_event_uuid: str | None = Header(default=None)):
    secret = os.getenv("GITLAB_WEBHOOK_SECRET", "")
    if not secret or not x_gitlab_token or not hmac.compare_digest(secret, x_gitlab_token):
        raise HTTPException(401, "Invalid webhook secret.")
    project_id = (payload.get("project") or {}).get("id")
    allowed = {v.strip() for v in os.getenv("GITLAB_WEBHOOK_PROJECT_IDS", "").split(",") if v.strip()}
    if str(project_id) not in allowed:
        raise HTTPException(403, "Webhook project is not allowlisted.")
    token = os.getenv("GITLAB_WEBHOOK_TOKEN")
    if not token:
        raise HTTPException(503, "Webhook service token is not configured.")
    event = f"{project_id}:" + (x_gitlab_event_uuid or hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest())
    with get_connection() as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS webhook_events (event_id TEXT PRIMARY KEY, status TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        inserted = connection.execute("INSERT OR IGNORE INTO webhook_events(event_id,status) VALUES (?, 'processing')", (event,)).rowcount
    if not inserted:
        return {"status": "duplicate", "event_id": event}
    try:
        if any(c.get("message", "").startswith("Apply AI code suggestion") for c in payload.get("commits", [])):
            result = {"status": "ignored", "reason": "AI suggestion commit"}
        else:
            repo = Repository("webhook", int(project_id), token, {})
            kind = payload.get("object_kind")
            if kind == "merge_request":
                ids = [(payload.get("object_attributes") or {}).get("iid")]
            elif kind == "push":
                branch = payload.get("ref", "").removeprefix("refs/heads/")
                ids = [r["iid"] for r in client.pages("merge_requests", repo.project_id, token, {"source_branch": branch, "state": "opened"})]
            else:
                ids = []
            for mr_iid in filter(None, ids):
                suggestions = suggest_merge_request(mr_iid, repo)["suggestions"]
                if suggestions:
                    post_suggestion(mr_iid, PostSuggestionRequest(suggestion=json.dumps(suggestions, indent=2)), repo)
            result = {"status": "completed"}
        with get_connection() as connection:
            connection.execute("UPDATE webhook_events SET status='completed' WHERE event_id=?", (event,))
        return result
    except Exception:
        with get_connection() as connection:
            connection.execute("UPDATE webhook_events SET status='failed' WHERE event_id=?", (event,))
        raise
