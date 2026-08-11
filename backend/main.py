from fastapi import FastAPI
import requests
from dotenv import load_dotenv
import os
from pydantic import BaseModel
from elasticsearch_client import (
    index_merge_request,
    search_merge_requests,
    merge_request_exists,
    get_merge_request_from_es,
    update_merge_request,
    bulk_index_merge_requests
)
from ai_review import review_code,suggest_code
import uuid

from pydantic import BaseModel
from langgraph.types import Command

from workflow.graph import graph

# created a FastAPI application
app = FastAPI()

# Load environment variables from .env
load_dotenv()

# Read values from .env
TOKEN = os.getenv("GITLAB_TOKEN")
PROJECT_ID = os.getenv("GITLAB_PROJECT_ID")

# GitLab authentication header
headers = {
    "PRIVATE-TOKEN": TOKEN
}

#pydantic model for creating a new branch
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
    message: str


class ChatDecisionRequest(BaseModel):
    thread_id: str
    approved: bool


#reusable gitlab function for get
def make_gitlab_request(endpoint: str):

    url = f"https://gitlab.com/api/v4/projects/{PROJECT_ID}/{endpoint}"

    response = requests.get(
        url,
        headers=headers
    )

    if response.status_code == 200:
        return response.json()

    return {
        "error": response.status_code,
        "message": response.text
    }
def get_commit_diff(commit_sha: str):

    endpoint = f"repository/commits/{commit_sha}/diff"

    return make_gitlab_request(endpoint)

def extract_diff_text(changes):

    diff_text = ""

    for change in changes:

        diff_text += f"\nFile: {change.get('new_path')}\n"
        diff_text += change.get("diff", "")
        diff_text += "\n"

    return diff_text

def get_merge_request_changes(mr_iid: int):

    endpoint = f"merge_requests/{mr_iid}/changes"

    return make_gitlab_request(endpoint)

#reusable gitlab function for post
def make_gitlab_post_request(endpoint: str, payload: dict):

    url = f"https://gitlab.com/api/v4/projects/{PROJECT_ID}/{endpoint}"

    response = requests.post(
        url,
        headers=headers,
        data=payload
    )

    if response.status_code in [200, 201]:
        return response.json()

    return {
        "error": response.status_code,
        "message": response.text
    }

# Home endpoint
@app.get("/")
async def home():
    return {
        # converts automatically to JSON
        "message": "Welcome to GitLab Resource Management API"

    }

#get branches endpoint
@app.get("/branches")
async def get_branches():
    return make_gitlab_request("repository/branches")

    #get commits endpoint
@app.get("/commit/{commit_sha}")
async def get_commit(commit_sha: str):

    endpoint = f"repository/commits/{commit_sha}"

    return make_gitlab_request(endpoint)

#get pipelines endpoint
@app.get("/pipeline/{pipeline_id}")
async def get_pipeline(pipeline_id: int):

    endpoint = f"pipelines/{pipeline_id}"

    return make_gitlab_request(endpoint)

#get merge requests
@app.get("/merge-requests")
async def get_merge_requests():

    # Fetch merge requests from GitLab
    merge_requests = make_gitlab_request("merge_requests")

    # List to store only new merge requests
    new_documents = []

    # Store merge requests in Elasticsearch
    if isinstance(merge_requests, list):

        for mr in merge_requests:

            document = {
                "mr_id": mr["iid"],
                "title": mr["title"],
                "description": mr["description"],
                "state": mr["state"],
                "author": mr["author"]["name"],
                "created_at": mr["created_at"]
            }

            if merge_request_exists(document["mr_id"]):

                existing_document = get_merge_request_from_es(document["mr_id"])

                if existing_document == document:
                    print(f"MR {document['mr_id']} unchanged")

                else:
                    update_merge_request(document)
                    print(f"MR {document['mr_id']} updated")

            else:
                new_documents.append(document)
                print(f"MR {document['mr_id']} queued for bulk insert")

        # Bulk insert all new merge requests
        if new_documents:
            bulk_index_merge_requests(new_documents)

    return merge_requests

def create_gitlab_branch(branch_name: str, ref: str):

    payload = {
        "branch": branch_name,
        "ref": ref
    }

    return make_gitlab_post_request(
        "repository/branches",
        payload
    )

#post endpoint for creating branch
@app.post("/create-branch")
async def create_branch(branch: BranchRequest):

    return create_gitlab_branch(
        branch.branch_name,
        branch.ref
    )

def create_gitlab_merge_request(source:str,target:str,title:str):
    payload = {
        "source_branch": source,
        "target_branch": target,
        "title": title
    }

    return make_gitlab_post_request(
        "merge_requests",
        payload
    )

#merge request endpoint
@app.post("/create-merge-request")
async def create_merge_request(mr: MergeRequest):
    return create_gitlab_merge_request(
        mr.source_branch,
        mr.target_branch,
        mr.title
    )


#endpoint for merge comments
@app.post("/merge-request/{mr_iid}/comment")
async def comment_on_merge_request(
        mr_iid: int,
        comment: CommentRequest
):

    endpoint = f"merge_requests/{mr_iid}/notes"

    payload = {
        "body": comment.body
    }

    return make_gitlab_post_request(
        endpoint,
        payload
    )

#enpoint to read a specific merge request
@app.get("/merge-request/{mr_iid}")
async def get_merge_request(mr_iid: int):

    endpoint = f"merge_requests/{mr_iid}"

    return make_gitlab_request(endpoint)

@app.get("/search")
async def search(query: str):

    return search_merge_requests(query)

@app.get("/review/{mr_iid}")
async def review_merge_request(mr_iid: int):

    changes = get_merge_request_changes(mr_iid)

    if "changes" not in changes:
        return changes

    diff_text = ""

    for change in changes["changes"]:
        diff_text += change["diff"] + "\n"

    review = review_code(diff_text)

    return {
        "review": review
    }

@app.get("/suggest/{mr_iid}")
async def suggest_merge_request(mr_iid: int):

    changes = get_merge_request_changes(mr_iid)

    if not changes["changes"]:
        return {"suggestion": "No changes found."}

    diff = ""

    for change in changes["changes"]:
        diff += change["diff"] + "\n"

    suggestion = suggest_code(diff)

    return {"suggestion": suggestion}

@app.post("/chat")
async def chat(request: ChatRequest):

    thread_id = str(uuid.uuid4())

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    result = graph.invoke(
        {
            "user_request": request.message
        },
        config=config
    )

    interrupts = result.get("__interrupt__", [])

    if interrupts:

        approval_request = interrupts[0].value

        return {
            "status": "waiting_for_approval",
            "thread_id": thread_id,
            "analysis": approval_request["analysis"],
            "branch_name": approval_request["branch_name"],
            "commit_message": approval_request["commit_message"],
            "mr_title": approval_request["mr_title"]
        }

    return {
        "status": "completed",
        "thread_id": thread_id,
        "result": result
    }

@app.post("/chat/decision")
async def chat_decision(request: ChatDecisionRequest):

    config = {
        "configurable": {
            "thread_id": request.thread_id
        }
    }

    result = graph.invoke(
        Command(resume=request.approved),
        config=config
    )

    if request.approved:

        return {
            "status": "completed",
            "thread_id": request.thread_id,
            "mr_url": result.get("mr_url", ""),
            "result": result
        }

    return {
        "status": "rejected",
        "thread_id": request.thread_id,
        "message": "Workflow rejected by user."
    }



@app.post("/webhook/gitlab")
async def gitlab_webhook(payload: dict):
    print("🔥 NEW WEBHOOK CODE IS RUNNING", flush=True)

    print("\n========== GITLAB WEBHOOK ==========")

    event_type = payload.get("object_kind")
    project_name = payload.get("project", {}).get("name")
    branch = payload.get("ref", "").replace("refs/heads/", "")
    commit_sha = payload.get("after")
    user_name = payload.get("user_name")

    print("Event type:", event_type)
    print("Project:", project_name)
    print("Branch:", branch)
    print("Commit SHA:", commit_sha)
    print("User:", user_name)

    commits = payload.get("commits", [])

    print("\nCommits:")

    for commit in commits:
        print("  Commit:", commit.get("id"))
        print("  Message:", commit.get("message"))
        print("  Author:", commit.get("author", {}).get("name"))
        print("  Modified:", commit.get("modified"))
        print("  Added:", commit.get("added"))
        print("  Removed:", commit.get("removed"))
        print()

    print("====================================\n")

    return {
        "status": "received",
        "event_type": event_type,
        "project": project_name,
        "branch": branch,
        "commit_sha": commit_sha
    }