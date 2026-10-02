"""HTTP client. Repository operations are bound to the current Flet page."""
import os
import requests
BASE_URL = os.getenv("AGENT_API_URL", "http://127.0.0.1:8003")


def request(method, path, *, token=None, project_id=None, payload=None, params=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    query = dict(params or {})
    if project_id is not None:
        query["project_id"] = project_id
    try:
        response = requests.request(method, BASE_URL + path, json=payload, params=query, headers=headers, timeout=(10, 300))
        data = response.json()
        if not response.ok:
            message = data.get("detail", "Request failed.")
            return {"error": True, "status": "error", "message": message, "detail": message}
        return data
    except (requests.RequestException, ValueError):
        return {"error": True, "status": "error", "message": "Backend unavailable or returned invalid data. Retry after checking its status."}


def login_user(username, password):
    return request("POST", "/login", payload={"username": username, "password": password})


def register_user(username, password, gitlab_token):
    return request("POST", "/register", payload=dict(username=username, password=password, gitlab_token=gitlab_token))


def get_home():
    return request("GET", "/")


def get_gitlab_projects(token):
    return request("GET", "/gitlab/projects", token=token)


class RepositoryAPI:
    def __init__(self, page):
        self.page = page

    def call(self, method, path, payload=None, params=None):
        project_id = getattr(self.page, "gitlab_project_id", None)
        if not project_id:
            return {"error": True, "message": "Select a repository in AI Agent chat first."}
        return request(method, path, token=self.page.auth_token, project_id=project_id, payload=payload, params=params)

    def get_branches(self):
        return self.call("GET", "/branches")

    def create_branch(self, branch_name, ref):
        return self.call("POST", "/create-branch", dict(branch_name=branch_name, ref=ref))

    def get_merge_requests(self):
        return self.call("GET", "/merge-requests")

    def create_merge_request(self, source, target, title):
        return self.call("POST", "/create-merge-request", dict(source_branch=source, target_branch=target, title=title))

    def get_merge_request(self, mr_id):
        return self.call("GET", f"/merge-request/{mr_id}")

    def get_mr_changes(self, mr_id):
        return self.call("GET", f"/merge-request/{mr_id}/code-diffs")

    def add_comment(self, mr_id, comment):
        return self.call("POST", f"/merge-request/{mr_id}/comment", {"body": comment})

    def review_merge_request(self, mr_id):
        return self.call("GET", f"/review/{mr_id}")

    def post_ai_review(self, mr_id, review_id):
        return self.call("POST", f"/review/{mr_id}/post", {"review_id": review_id})

    def post_ai_suggestion(self, mr_id, suggestion):
        return self.call("POST", f"/suggest/{mr_id}/post", {"suggestion": suggestion})

    def accept_ai_suggestion(self, mr_id, proposal_id):
        return self.call("POST", f"/suggest/{mr_id}/accept", {"proposal_id": proposal_id})

    def suggest_merge_request(self, mr_id):
        return self.call("GET", f"/suggest/{mr_id}")

    def search_merge_requests(self, query):
        return self.call("GET", "/search", params={"query": query})

    def get_merge_request_approval_history(self, mr_id):
        return self.call("GET", f"/merge-request/{mr_id}/approval-history")

    def start_chat(self, message, thread_id=None):
        return request("POST", "/chat", token=self.page.auth_token, payload={"message": message,
            "thread_id": thread_id, "project_id": getattr(self.page, "gitlab_project_id", None)})

    def send_chat_decision(self, thread_id, workflow_id, approved, branch_name=None, use_existing_branch=False):
        return self.call("POST", "/chat/decision", dict(thread_id=thread_id, approved=approved,
            workflow_id=workflow_id, project_id=self.page.gitlab_project_id, branch_name=branch_name, use_existing_branch=use_existing_branch))
