import requests

BASE_URL = "http://127.0.0.1:8000"

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

def start_chat(message):

    response = requests.post(
        f"{BASE_URL}/chat",
        json={
            "message": message
        }
    )

    return response.json()


def send_chat_decision(thread_id, approved):

    response = requests.post(
        f"{BASE_URL}/chat/decision",
        json={
            "thread_id": thread_id,
            "approved": approved
        }
    )

    return response.json()