import requests



BASE_URL = "http://127.0.0.1:8000"

def get_headers(token=None):

    headers = {}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    return headers

def login_user(username, password):

    response = requests.post(
        f"{BASE_URL}/login",
        json={
            "username": username,
            "password": password
        }
    )

    return response.json()


def get_home():
    response = requests.get(f"{BASE_URL}/")
    return response.json()

def get_branches():
    response = requests.get(f"{BASE_URL}/branches")
    return response.json()
def create_branch(branch_name, ref):
    payload = {
        "branch_name": branch_name,
        "ref": ref
    }

    response = requests.post(
        f"{BASE_URL}/create-branch",
        json=payload
    )

    return response.json()

def get_merge_requests():
    response = requests.get(f"{BASE_URL}/merge-requests")
    return response.json()
def create_merge_request(source, target, title):

    payload = {
        "source_branch": source,
        "target_branch": target,
        "title": title
    }

    response = requests.post(
        f"{BASE_URL}/create-merge-request",
        json=payload
    )

    return response.json()

def get_merge_request(mr_id):
    response = requests.get(
        f"{BASE_URL}/merge-request/{mr_id}"
    )

    return response.json()

def add_comment(mr_id, comment):

    payload = {
        "body": comment
    }

    response = requests.post(
        f"{BASE_URL}/merge-request/{mr_id}/comment",
        json=payload
    )

    return response.json()

def review_merge_request(mr_id):

    response = requests.get(
        f"{BASE_URL}/review/{mr_id}"
    )

    return response.json()
def post_ai_review(mr_id):
    response = requests.post(
        f"{BASE_URL}/review/{mr_id}/post"
    )

    return response.json()

def post_ai_suggestion(mr_id, suggestion):

    response = requests.post(
        f"{BASE_URL}/suggest/{mr_id}/post",
        json={
            "suggestion": suggestion
        }
    )

    return response.json()

def accept_ai_suggestion(
    mr_id,
    file,
    previous_code,
    current_code,
    suggested_code
):
    response = requests.post(
        f"{BASE_URL}/suggest/{mr_id}/accept",
        json={
            "file": file,
            "previous_code": previous_code,
            "current_code": current_code,
            "suggested_code": suggested_code
        }
    )

    return response.json()

def suggest_merge_request(mr_id):

    response = requests.get(
        f"{BASE_URL}/suggest/{mr_id}"
    )

    return response.json()

def search_merge_requests(query):

    response = requests.get(
        f"{BASE_URL}/search",
        params={
            "query": query
        }
    )

    return response.json()

def start_chat(message, thread_id=None, token=None):

    payload = {
        "message": message
    }

    if thread_id:
        payload["thread_id"] = thread_id

    response = requests.post(
        f"{BASE_URL}/chat",
        json=payload,
        headers=get_headers(token)
    )

    print("========== CHAT RESPONSE ==========")
    print("STATUS:", response.status_code)
    print("TEXT:", response.text)
    print("===================================")

    try:
        return response.json()

    except ValueError:
        return {
            "status": "error",
            "message": (
                f"Backend returned invalid response: "
                f"{response.text}"
            )
        }

def send_chat_decision(
    thread_id,
    approved,
    username,
    token=None,
    branch_name=None,
    use_existing_branch=False
):

    payload = {
        "thread_id": thread_id,
        "approved": approved,
        "username": username,
        "use_existing_branch": use_existing_branch
    }

    if branch_name:
        payload["branch_name"] = branch_name

    response = requests.post(
        f"{BASE_URL}/chat/decision",
        json=payload,
        headers=get_headers(token)
    )

    print(
        "\n========== CHAT DECISION RESPONSE =========="
    )
    print("STATUS:", response.status_code)
    print("TEXT:", response.text)
    print(
        "============================================\n"
    )

    response.raise_for_status()

    if response.text.strip():
        return response.json()

    return {}
def get_merge_request_approval_history(mr_id):

    response = requests.get(
        f"{BASE_URL}/merge-request/{mr_id}/approval-history"
    )

    return response.json()