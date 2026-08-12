from fastapi import FastAPI
import requests
from dotenv import load_dotenv
import os
import json
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
import base64
from urllib.parse import quote
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

class SuggestionRequest(BaseModel):
    file: str
    previous_code: str
    current_code: str
    suggested_code: str

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



def get_file_content(file_path: str, branch: str):

    encoded_path = quote(file_path, safe="")

    endpoint = (
        f"repository/files/{encoded_path}"
        f"?ref={quote(branch, safe='')}"
    )

    result = make_gitlab_request(endpoint)

    if "content" not in result:
        return None

    content = base64.b64decode(
        result["content"]
    ).decode("utf-8")

    print("========== RAW FILE CONTENT ==========")
    print(repr(content))
    print("======================================")

    return content
def get_merge_request_source_files(mr_iid: int):

    mr = fetch_merge_request(mr_iid)

    if "source_branch" not in mr:
        return {
            "error": mr.get(
                "message",
                "Unable to get source branch."
            )
        }

    source_branch = mr["source_branch"]

    changes = get_merge_request_changes(mr_iid)

    if "changes" not in changes:
        return {
            "error": changes.get(
                "message",
                "Unable to get Merge Request changes."
            )
        }

    files = []

    for change in changes["changes"]:

        file_path = change.get("new_path")

        if not file_path:
            continue

        content = get_file_content(
            file_path,
            source_branch
        )

        if content is not None:

            files.append({
                "file": file_path,
                "content": content
            })

    return files

def get_merge_request_source_branch(mr_iid: int):

    mr = make_gitlab_request(
        f"merge_requests/{mr_iid}"
    )

    if "error" in mr:
        return mr

    return {
        "source_branch": mr["source_branch"]
    }

def apply_ai_suggestion(
    mr_iid: int,
    file_path: str,
    current_code: str,
    suggested_code: str
):
    # ------------------------------------------------------------
    # Get Merge Request details
    # ------------------------------------------------------------

    mr = make_gitlab_request(
        f"merge_requests/{mr_iid}"
    )

    if "error" in mr:
        return mr

    source_branch = mr.get("source_branch")

    if not source_branch:
        return {
            "error": 400,
            "message": (
                "Could not determine the Merge Request "
                "source branch."
            )
        }

    # ------------------------------------------------------------
    # Get the ACTUAL current file from GitLab
    # ------------------------------------------------------------

    file_endpoint = (
        f"repository/files/"
        f"{quote(file_path, safe='')}"
        f"?ref={quote(source_branch, safe='')}"
    )

    file_data = make_gitlab_request(file_endpoint)

    if "error" in file_data:
        return file_data

    if "content" not in file_data:
        return {
            "error": 404,
            "message": (
                f"Could not find file '{file_path}' "
                "in the source branch."
            )
        }

    try:
        current_file_content = base64.b64decode(
            file_data["content"]
        ).decode("utf-8")

    except Exception:
        return {
            "error": 500,
            "message": (
                "Could not decode the current file content."
            )
        }

    # ------------------------------------------------------------
    # Clean accidental Git diff markers
    # ------------------------------------------------------------

    clean_current_code = "\n".join(
        line[1:] if line.startswith(("+", "-")) else line
        for line in current_code.splitlines()
    ).strip()

    clean_suggested_code = "\n".join(
        line[1:] if line.startswith(("+", "-")) else line
        for line in suggested_code.splitlines()
    ).strip()

    if not clean_suggested_code:
        return {
            "error": 400,
            "message": "Suggested code is empty."
        }

    # ------------------------------------------------------------
    # Normalize line endings
    # ------------------------------------------------------------

    actual_code = current_file_content.replace(
        "\r\n",
        "\n"
    ).replace(
        "\r",
        "\n"
    )

    clean_current_code = clean_current_code.replace(
        "\r\n",
        "\n"
    ).replace(
        "\r",
        "\n"
    )

    clean_suggested_code = clean_suggested_code.replace(
        "\r\n",
        "\n"
    ).replace(
        "\r",
        "\n"
    )

    # ------------------------------------------------------------
    # METHOD 1:
    # Exact replacement using current_code from AI
    # ------------------------------------------------------------

    if clean_current_code and clean_current_code in actual_code:

        updated_file_content = actual_code.replace(
            clean_current_code,
            clean_suggested_code,
            1
        )

    else:

        # --------------------------------------------------------
        # METHOD 2:
        # AI current_code was not exact.
        #
        # Try to identify the Python function being modified
        # and replace that function in the real GitLab file.
        # --------------------------------------------------------

        import ast

        try:
            suggested_tree = ast.parse(
                clean_suggested_code
            )

            suggested_functions = [
                node
                for node in ast.walk(suggested_tree)
                if isinstance(
                    node,
                    (ast.FunctionDef, ast.AsyncFunctionDef)
                )
            ]

        except SyntaxError:
            suggested_functions = []

        if not suggested_functions:

            return {
                "error": 409,
                "message": (
                    "The suggested code does not match the "
                    "current version of the file, and the "
                    "affected code section could not be "
                    "identified safely."
                )
            }

        function_name = suggested_functions[0].name

        # --------------------------------------------------------
        # Parse actual file
        # --------------------------------------------------------

        try:
            actual_tree = ast.parse(actual_code)

        except SyntaxError:
            return {
                "error": 500,
                "message": (
                    "The current file contains invalid Python "
                    "syntax, so the suggestion could not be "
                    "applied safely."
                )
            }

        target_function = None

        for node in ast.walk(actual_tree):

            if isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef)
            ) and node.name == function_name:

                target_function = node
                break

        if target_function is None:

            return {
                "error": 409,
                "message": (
                    "The suggested code does not match the "
                    "current version of the file. The affected "
                    "function could not be identified safely."
                )
            }

        # --------------------------------------------------------
        # Replace only the identified function
        # --------------------------------------------------------

        lines = actual_code.splitlines(
            keepends=True
        )

        start_line = target_function.lineno - 1
        end_line = target_function.end_lineno

        original_indent = len(
            lines[start_line]
        ) - len(
            lines[start_line].lstrip()
        )

        suggested_lines = clean_suggested_code.splitlines()

        # Ensure suggested function has the same indentation
        if original_indent > 0:

            indentation = " " * original_indent

            suggested_lines = [
                (
                    indentation + line
                    if line.strip()
                    else line
                )
                for line in suggested_lines
            ]

        replacement = "\n".join(
            suggested_lines
        )

        if lines[start_line].endswith("\n"):
            replacement += "\n"

        updated_file_content = (
            "".join(lines[:start_line])
            + replacement
            + "".join(lines[end_line:])
        )

    # ------------------------------------------------------------
    # Create GitLab commit
    # ------------------------------------------------------------

    payload = {
        "branch": source_branch,
        "commit_message": (
            f"Apply AI code suggestion to {file_path}"
        ),
        "actions": [
            {
                "action": "update",
                "file_path": file_path,
                "content": updated_file_content
            }
        ]
    }

    url = (
        f"https://gitlab.com/api/v4/projects/"
        f"{PROJECT_ID}/repository/commits"
    )

    response = requests.post(
        url,
        headers=headers,
        json=payload
    )

    if response.status_code == 201:
        return response.json()

    return {
        "error": response.status_code,
        "message": response.text
    }
def get_commit_diff(commit_sha: str):

    endpoint = f"repository/commits/{commit_sha}/diff"

    return make_gitlab_request(endpoint)

def get_merge_request_for_branch(branch: str):

    endpoint = f"merge_requests?source_branch={branch}&state=opened"

    return make_gitlab_request(endpoint)

def extract_diff_text(changes):

    diff_text = ""

    for change in changes:

        file_path = change.get("new_path")

        raw_diff = change.get("diff", "")

        clean_diff = []

        for line in raw_diff.splitlines():

            # Ignore Git diff metadata
            if line.startswith("@@"):
                continue

            if line.startswith("+++"):
                continue

            if line.startswith("---"):
                continue

            clean_diff.append(line)

        diff_text += (
            f"\n===== FILE: {file_path} =====\n"
        )

        diff_text += "\n".join(clean_diff)

        diff_text += (
            "\n===== END FILE =====\n"
        )

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

def fetch_merge_request(mr_iid: int):

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

@app.post("/suggest/{mr_iid}/post")
async def post_suggestion_to_gitlab(
    mr_iid: int,
    request: SuggestionRequest
):

    result = post_ai_suggestion(
        mr_iid,
        request.suggestion
    )

    if "error" in result:

        return {
            "status": "failed",
            "message": result.get(
                "message",
                "Failed to post AI suggestions."
            )
        }

    return {
        "status": "posted",
        "message": "AI suggestions successfully posted to GitLab.",
        "mr_url": result.get("web_url", "")
    }

@app.post("/suggest/{mr_iid}/accept")
async def accept_suggestion(
    mr_iid: int,
    request: SuggestionRequest
):
    result = apply_ai_suggestion(
        mr_iid,
        request.file,
        request.current_code,
        request.suggested_code
    )

    if "error" in result:
        return {
            "status": "failed",
            "message": result.get(
                "message",
                "Failed to apply AI suggestion."
            )
        }

    return {
        "status": "accepted",
        "message": "AI suggestion applied and committed successfully.",
        "commit_sha": result.get("id", ""),
        "commit_url": result.get("web_url", "")
    }

@app.post("/review/{mr_iid}/post")
async def post_ai_review_to_gitlab(mr_iid: int):

    changes = get_merge_request_changes(mr_iid)

    if "changes" not in changes:
        return changes

    if not changes["changes"]:
        return {
            "status": "error",
            "message": "No changes found in this Merge Request."
        }

    diff_text = ""

    for change in changes["changes"]:
        diff_text += (
            f"\nFile: {change.get('new_path')}\n"
            f"{change.get('diff', '')}\n"
        )

    review = review_code(diff_text)

    result = post_ai_review(
        mr_iid,
        review
    )

    return {
        "status": "posted",
        "mr_iid": mr_iid,
        "review": review,
        "gitlab_response": result
    }
def post_ai_review(mr_iid: int, review: str):

    endpoint = f"merge_requests/{mr_iid}/notes"

    payload = {
        "body": f"## 🤖 AI Code Review\n\n{review}"
    }

    return make_gitlab_post_request(
        endpoint,
        payload
    )

def post_ai_suggestion(mr_iid: int, suggestion: str):

    endpoint = f"merge_requests/{mr_iid}/notes"

    payload = {
        "body": f"## 💡 AI Code Suggestions\n\n{suggestion}"
    }

    return make_gitlab_post_request(
        endpoint,
        payload
    )

@app.get("/suggest/{mr_iid}")
async def suggest_merge_request(mr_iid: int):

    # Get MR details
    mr = make_gitlab_request(
        f"merge_requests/{mr_iid}"
    )

    if "error" in mr:
        return mr

    source_branch = mr.get("source_branch")

    if not source_branch:
        return {
            "error": 400,
            "message": "Could not determine source branch."
        }

    # Get changed files
    changes = get_merge_request_changes(mr_iid)

    if "error" in changes:
        return changes

    if not changes.get("changes"):
        return {
            "type": "suggestion",
            "mr_iid": mr_iid,
            "suggestions": []
        }

    # Get ACTUAL current code from source branch
    file_contents = []

    for change in changes["changes"]:

        file_path = change.get("new_path")

        if not file_path:
            continue

        file_result = get_file_content(
            file_path,
            source_branch
        )

        if "error" in file_result:
            continue

        file_contents.append(file_result)

    if not file_contents:
        return {
            "type": "suggestion",
            "mr_iid": mr_iid,
            "suggestions": []
        }

    # Send actual source code to AI
    suggestion_response = suggest_code(file_contents)

    try:
        parsed_response = json.loads(suggestion_response)
        suggestions = parsed_response.get("suggestions", [])

    except json.JSONDecodeError:
        suggestions = []

    return {
        "type": "suggestion",
        "mr_iid": mr_iid,
        "suggestions": suggestions
    }

@app.post("/chat")
async def chat(request: ChatRequest):

    message = request.message.strip()

    # ============================================================
    # AI CODE REVIEW REQUEST
    # ============================================================

    if message.lower().startswith("review mr"):

        parts = message.split()

        if len(parts) < 3 or not parts[2].isdigit():
            return {
                "type": "review",
                "mr_iid": None,
                "review": "Please provide a valid Merge Request ID."
            }

        mr_iid = int(parts[2])

        changes = get_merge_request_changes(mr_iid)

        if "changes" not in changes:
            return {
                "type": "review",
                "mr_iid": mr_iid,
                "review": changes.get(
                    "message",
                    "Unable to retrieve Merge Request changes."
                )
            }

        if not changes["changes"]:
            return {
                "type": "review",
                "mr_iid": mr_iid,
                "review": "No changes found in this Merge Request."
            }

        diff_text = ""

        for change in changes["changes"]:

            diff_text += (
                f"\nFile: {change.get('new_path', 'Unknown')}\n"
                f"{change.get('diff', '')}\n"
            )

        review = review_code(diff_text)

        return {
            "type": "review",
            "mr_iid": mr_iid,
            "review": review
        }

    # ============================================================
    # AI CODE SUGGESTION REQUEST
    # ============================================================

    if (
            "suggest" in message.lower()
            and "mr" in message.lower()
    ):

        import re

        match = re.search(
            r"mr\s*!?(\d+)",
            message.lower()
        )

        if not match:
            return {
                "type": "suggestion",
                "mr_iid": None,
                "suggestions": [],
                "message": "Please provide a valid Merge Request ID."
            }

        mr_iid = int(match.group(1))

        # --------------------------------------------------------
        # Get actual source files from the MR source branch
        # --------------------------------------------------------

        files = get_merge_request_source_files(mr_iid)

        # --------------------------------------------------------
        # Check GitLab response
        # --------------------------------------------------------

        if isinstance(files, dict) and "error" in files:
            return {
                "type": "suggestion",
                "mr_iid": mr_iid,
                "suggestions": [],
                "message": files.get(
                    "error",
                    "Unable to retrieve Merge Request files."
                )
            }

        if not files:
            return {
                "type": "suggestion",
                "mr_iid": mr_iid,
                "suggestions": []
            }

        # --------------------------------------------------------
        # Send actual source code to AI
        # --------------------------------------------------------

        suggestion_text = suggest_code(files)

        # --------------------------------------------------------
        # Parse AI JSON response
        # --------------------------------------------------------

        try:

            json_start = suggestion_text.find("{")
            json_end = suggestion_text.rfind("}") + 1

            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON object found")

            suggestion_data = json.loads(
                suggestion_text[json_start:json_end]
            )

        except (json.JSONDecodeError, ValueError):

            return {
                "type": "suggestion",
                "mr_iid": mr_iid,
                "suggestion": suggestion_text
            }

        # --------------------------------------------------------
        # Return suggestions to frontend
        # --------------------------------------------------------

        return {
            "type": "suggestion",
            "mr_iid": mr_iid,
            "suggestions": suggestion_data.get(
                "suggestions",
                []
            )
        }
        # --------------------------------------------------------
        # Convert GitLab changes into file_contents format
        # expected by suggest_code()
        # --------------------------------------------------------

        # Get Merge Request details to find source branch

        mr_details = get_merge_request(mr_iid)

        if "source_branch" not in mr_details:
            return {
                "type": "suggestion",
                "mr_iid": mr_iid,
                "suggestions": [],
                "message": "Unable to determine Merge Request source branch."
            }

        source_branch = mr_details["source_branch"]

        # Fetch ACTUAL source code from the source branch

        file_contents = []

        for change in changes["changes"]:

            file_path = change.get(
                "new_path",
                change.get("old_path")
            )

            if not file_path:
                continue

            file_data = get_file_content(
                file_path,
                source_branch
            )

            if "error" not in file_data:
                file_contents.append(file_data)

        # Debugging
        print("========== FILE CONTENTS ==========")
        print(file_contents)
        print("===================================")

        if not file_contents:
            return {
                "type": "suggestion",
                "mr_iid": mr_iid,
                "suggestions": []
            }

        # --------------------------------------------------------
        # Generate AI suggestions
        # --------------------------------------------------------

        suggestion_text = suggest_code(
            file_contents
        )

        # --------------------------------------------------------
        # Parse AI JSON response
        # --------------------------------------------------------

        try:

            json_start = suggestion_text.find("{")
            json_end = suggestion_text.rfind("}") + 1

            if json_start == -1 or json_end == 0:
                raise ValueError(
                    "No JSON object found"
                )

            suggestion_data = json.loads(
                suggestion_text[
                    json_start:json_end
                ]
            )

        except (json.JSONDecodeError, ValueError):

            return {
                "type": "suggestion",
                "mr_iid": mr_iid,
                "suggestions": [],
                "message": (
                    "AI returned an invalid suggestion format."
                ),
                "raw_response": suggestion_text
            }

        return {
            "type": "suggestion",
            "mr_iid": mr_iid,
            "suggestions": suggestion_data.get(
                "suggestions",
                []
            )
        }

    # ============================================================
    # EXISTING LANGGRAPH WORKFLOW
    # ============================================================

    thread_id = str(uuid.uuid4())

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    result = graph.invoke(
        {
            "user_request": message
        },
        config=config
    )

    interrupts = result.get(
        "__interrupt__",
        []
    )

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

    print("\n========== GITLAB WEBHOOK ==========")

    event_type = payload.get("object_kind")
    project_name = payload.get("project", {}).get("name")
    branch = payload.get("ref", "").replace(
        "refs/heads/",
        ""
    )
    commit_sha = payload.get("after")
    user_name = payload.get("user_name")

    print("Event type:", event_type)
    print("Project:", project_name)
    print("Branch:", branch)
    print("Commit SHA:", commit_sha)
    print("User:", user_name)

    # ============================================================
    # PUSH EVENT
    # ============================================================

    if event_type == "push":

        print("\n📌 Push event received.")

        print(
            "ℹ️ Push detected. "
            "AI review will NOT be triggered automatically."
        )

        return {
            "status": "received",
            "event_type": "push",
            "project": project_name,
            "branch": branch,
            "commit_sha": commit_sha,
            "message": (
                "Push received. "
                "No automatic AI review triggered."
            )
        }

    # ============================================================
    # MERGE REQUEST EVENT
    # ============================================================

    if event_type == "merge_request":

        print("\n📌 Merge Request event received.")

        # --------------------------------------------------------
        # Get Merge Request information
        # --------------------------------------------------------

        attributes = payload.get(
            "object_attributes",
            {}
        )

        mr_iid = attributes.get("iid")

        if not mr_iid:

            print(
                "❌ Could not determine Merge Request IID."
            )

            return {
                "status": "error",
                "message": (
                    "Merge Request IID not found in webhook payload."
                )
            }

        print(
            f"✅ Merge Request found: !{mr_iid}"
        )

        # --------------------------------------------------------
        # Get Merge Request changes
        # --------------------------------------------------------

        print(
            "\n🔍 Getting Merge Request changes from GitLab..."
        )

        changes = get_merge_request_changes(mr_iid)

        if (
            not isinstance(changes, dict)
            or "changes" not in changes
        ):

            print(
                "❌ Failed to get Merge Request changes:"
            )
            print(changes)

            return {
                "status": "error",
                "message": (
                    "Failed to get Merge Request changes."
                ),
                "details": changes
            }

        if not changes["changes"]:

            print(
                "⚠️ No changes found in Merge Request."
            )

            return {
                "status": "received",
                "event_type": "merge_request",
                "mr_iid": mr_iid,
                "message": "No changes found."
            }

        # --------------------------------------------------------
        # Build diff for AI review
        # --------------------------------------------------------

        diff_text = ""

        for change in changes["changes"]:

            file_path = change.get(
                "new_path",
                "Unknown"
            )

            file_diff = change.get(
                "diff",
                ""
            )

            diff_text += (
                f"\n===== FILE: {file_path} =====\n"
                f"{file_diff}\n"
                f"===== END FILE =====\n"
            )

        print(
            "\n========== CODE DIFF =========="
        )
        print(diff_text)

        # --------------------------------------------------------
        # AI CODE REVIEW
        # --------------------------------------------------------

        print(
            "\n========== AI REVIEW =========="
        )
        print(
            "🤖 Sending Merge Request changes to AI..."
        )

        review = review_code(diff_text)

        print(
            "\n===== AI REVIEW RESULT ====="
        )
        print(review)

        # --------------------------------------------------------
        # Post review to GitLab MR
        # --------------------------------------------------------

        print(
            "\n💬 Posting AI review to GitLab..."
        )

        comment_result = post_ai_review(
            mr_iid,
            review
        )

        print(
            "GitLab comment response:"
        )
        print(comment_result)

        print(
            "====================================\n"
        )

        return {
            "status": "reviewed",
            "event_type": "merge_request",
            "project": project_name,
            "mr_iid": mr_iid,
            "review": review
        }

    # ============================================================
    # OTHER EVENTS
    # ============================================================

    print(
        f"⚠️ Ignoring unsupported webhook event: {event_type}"
    )

    return {
        "status": "ignored",
        "event_type": event_type,
        "message": "Webhook event not handled."
    }