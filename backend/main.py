from fastapi import FastAPI
import requests
from dotenv import load_dotenv
import os
import json
import re
from pydantic import BaseModel
from elasticsearch_client import (
    index_merge_request,
    search_merge_requests,
    merge_request_exists,
    get_merge_request_from_es,
    update_merge_request,
    bulk_index_merge_requests,
    get_mr_context_for_suggestions
)
from ai_review import review_code,suggest_code
import uuid

from pydantic import BaseModel
from langgraph.types import Command

from workflow.graph import graph
import base64
from urllib.parse import quote
chat_sessions = {}
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
    thread_id: str | None = None

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
def get_open_merge_requests():

    endpoint = (
        "merge_requests"
        "?state=opened"
        "&per_page=20"
    )

    result = make_gitlab_request(endpoint)

    if isinstance(result, dict) and "error" in result:
        return result

    if not isinstance(result, list):
        return []

    return result
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
    # Get the ACTUAL current file from the source branch
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
            "error": 500,
            "message": "Could not retrieve the current file content."
        }

    # ------------------------------------------------------------
    # Decode the file
    # ------------------------------------------------------------

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
    # Normalize only line endings for comparison
    # ------------------------------------------------------------

    normalized_current_code = (
        current_code
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )

    normalized_file_content = (
        current_file_content
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )

    # ------------------------------------------------------------
    # Make sure the function has not changed
    # ------------------------------------------------------------

    if normalized_current_code not in normalized_file_content:

        return {
            "error": 409,
            "message": (
                "The selected code has changed since the "
                "suggestion was generated. Please generate "
                "a new suggestion before accepting it."
            )
        }

    # ------------------------------------------------------------
    # Replace ONLY the selected function
    # ------------------------------------------------------------

    updated_file_content = normalized_file_content.replace(
        normalized_current_code,
        suggested_code.strip(),
        1
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

    # ------------------------------------------------------------
    # 1. Get Merge Request details
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
            "message": "Could not determine source branch."
        }

    # ------------------------------------------------------------
    # 2. Get changed files
    # ------------------------------------------------------------

    changes = get_merge_request_changes(mr_iid)

    if "error" in changes:
        return changes

    if not changes.get("changes"):
        return {
            "type": "suggestion",
            "mr_iid": mr_iid,
            "suggestions": []
        }

    # ------------------------------------------------------------
    # 3. Get ACTUAL current code from source branch
    # ------------------------------------------------------------

    file_contents = []

    for change in changes["changes"]:

        file_path = change.get("new_path")

        if not file_path:
            continue

        file_result = get_file_content(
            file_path,
            source_branch
        )

        # get_file_content() returns None if the file
        # could not be retrieved.
        if file_result is None:
            continue

        file_contents.append({
            "file": file_path,
            "content": file_result
        })

    if not file_contents:
        return {
            "type": "suggestion",
            "mr_iid": mr_iid,
            "suggestions": []
        }

    # ------------------------------------------------------------
    # 4. Search Elasticsearch for related Merge Requests
    # ------------------------------------------------------------

    print(
        "\n🔍 Searching Elasticsearch for related Merge Requests..."
    )

    query_parts = []

    if mr.get("title"):
        query_parts.append(
            mr.get("title")
        )

    if mr.get("description"):
        query_parts.append(
            mr.get("description")
        )

    search_query = " ".join(
        query_parts
    ).strip()

    mr_context = []

    if search_query:

        try:

            mr_context = search_merge_requests(
                search_query
            )

            # Do not use the current MR as its own context.
            mr_context = [
                related_mr
                for related_mr in mr_context
                if str(
                    related_mr.get("mr_id")
                ) != str(mr_iid)
            ]

            # Keep only a small amount of relevant context.
            mr_context = mr_context[:3]

        except Exception as e:

            print(
                "⚠️ Elasticsearch search failed:",
                e
            )

            mr_context = []

    print(
        f"✅ Found {len(mr_context)} related Merge Requests."
    )

    # ------------------------------------------------------------
    # 5. Generate context-aware AI suggestions
    # ------------------------------------------------------------

    print(
        "\n🤖 Generating context-aware AI code suggestions..."
    )

    suggestion_response = suggest_code(
        file_contents,
        mr_context
    )

    # ------------------------------------------------------------
    # 6. Parse AI response
    # ------------------------------------------------------------

    try:

        parsed_response = json.loads(
            suggestion_response
        )

        suggestions = parsed_response.get(
            "suggestions",
            []
        )

    except json.JSONDecodeError:

        suggestions = []

    # ------------------------------------------------------------
    # 7. Return suggestions
    # ------------------------------------------------------------

    return {
        "type": "suggestion",
        "mr_iid": mr_iid,
        "suggestions": suggestions
    }
@app.post("/chat")
async def chat(request: ChatRequest):

    message = request.message.strip()

    if not message:
        return {
            "status": "error",
            "message": "Please enter a message."
        }

    # ============================================================
    # CONVERSATION / THREAD SETUP
    # ============================================================

    thread_id = request.thread_id

    if not thread_id:
        thread_id = str(uuid.uuid4())

    session = chat_sessions.setdefault(
        thread_id,
        {}
    )

    lower_message = message.lower()

    # ============================================================
    # CONVERSATIONAL MR REVIEW REQUEST
    # ============================================================

    # Example:
    # "I want to review an MR"
    # "Can you review a merge request?"
    #
    # We only enter this block when the user has NOT
    # already provided an MR number.

    if (
        "review" in lower_message
        and (
            "mr" in lower_message
            or "merge request" in lower_message
        )
        and not re.search(
            r"(?:mr|merge request)\s*!?\d+",
            lower_message
        )
    ):

        merge_requests = get_open_merge_requests()

        if (
            isinstance(merge_requests, dict)
            and "error" in merge_requests
        ):
            return {
                "type": "conversation",
                "thread_id": thread_id,
                "message": (
                    "I couldn't retrieve the open "
                    "Merge Requests."
                )
            }

        if not merge_requests:

            return {
                "type": "conversation",
                "thread_id": thread_id,
                "message": (
                    "There are currently no open "
                    "Merge Requests."
                )
            }

        session["intent"] = "review"

        mr_list = []

        for mr in merge_requests:

            mr_list.append({
                "mr_iid": mr.get("iid"),
                "title": mr.get("title", ""),
                "source_branch": mr.get(
                    "source_branch",
                    ""
                )
            })

        return {
            "type": "mr_selection",
            "thread_id": thread_id,
            "intent": "review",
            "message": (
                "Sure! Which Merge Request "
                "would you like me to review?"
            ),
            "merge_requests": mr_list
        }

    # ============================================================
    # CONVERSATIONAL MR SUGGESTION REQUEST
    # ============================================================

    # Example:
    # "I want code suggestions for an MR"
    # "Give me suggestions for a merge request"
    #
    # Again, only trigger this when an MR number
    # was NOT already provided.

    if (
        "suggest" in lower_message
        and (
            "mr" in lower_message
            or "merge request" in lower_message
        )
        and not re.search(
            r"(?:mr|merge request)\s*!?\d+",
            lower_message
        )
    ):

        merge_requests = get_open_merge_requests()

        if (
            isinstance(merge_requests, dict)
            and "error" in merge_requests
        ):
            return {
                "type": "conversation",
                "thread_id": thread_id,
                "message": (
                    "I couldn't retrieve the open "
                    "Merge Requests."
                )
            }

        if not merge_requests:

            return {
                "type": "conversation",
                "thread_id": thread_id,
                "message": (
                    "There are currently no open "
                    "Merge Requests."
                )
            }

        session["intent"] = "suggestion"

        mr_list = []

        for mr in merge_requests:

            mr_list.append({
                "mr_iid": mr.get("iid"),
                "title": mr.get("title", ""),
                "source_branch": mr.get(
                    "source_branch",
                    ""
                )
            })

        return {
            "type": "mr_selection",
            "thread_id": thread_id,
            "intent": "suggestion",
            "message": (
                "Sure! Which Merge Request would "
                "you like code suggestions for?"
            ),
            "merge_requests": mr_list
        }

    # ============================================================
    # USER SELECTED AN MR FROM THE CONVERSATION
    # ============================================================

    # Example:
    #
    # User:
    # "I want code suggestions for an MR"
    #
    # Bot:
    # "Which MR?"
    #
    # User:
    # "18"
    #
    # The session remembers that the user wanted
    # a suggestion, so 18 means MR !18.

    if message.isdigit() and session.get("intent"):

        mr_iid = int(message)

        intent = session.get("intent")

        # Clear the pending intent because the user
        # has now selected the MR.
        session.pop("intent", None)

        # --------------------------------------------------------
        # REVIEW SELECTED MR
        # --------------------------------------------------------

        if intent == "review":

            changes = get_merge_request_changes(
                mr_iid
            )

            if "changes" not in changes:

                return {
                    "type": "review",
                    "thread_id": thread_id,
                    "mr_iid": mr_iid,
                    "review": changes.get(
                        "message",
                        (
                            "Unable to retrieve "
                            "Merge Request changes."
                        )
                    )
                }

            if not changes["changes"]:

                return {
                    "type": "review",
                    "thread_id": thread_id,
                    "mr_iid": mr_iid,
                    "review": (
                        "No changes found in this "
                        "Merge Request."
                    )
                }

            diff_text = ""

            for change in changes["changes"]:

                diff_text += (
                    f"\nFile: "
                    f"{change.get('new_path', 'Unknown')}\n"
                    f"{change.get('diff', '')}\n"
                )

            review = review_code(
                diff_text
            )

            return {
                "type": "review",
                "thread_id": thread_id,
                "mr_iid": mr_iid,
                "review": review
            }

        # --------------------------------------------------------
        # SUGGESTIONS FOR SELECTED MR
        # --------------------------------------------------------

        if intent == "suggestion":

            files = get_merge_request_source_files(
                mr_iid
            )

            if (
                isinstance(files, dict)
                and "error" in files
            ):

                return {
                    "type": "suggestion",
                    "thread_id": thread_id,
                    "mr_iid": mr_iid,
                    "suggestions": [],
                    "message": files.get(
                        "error",
                        (
                            "Unable to retrieve "
                            "Merge Request files."
                        )
                    )
                }

            if not files:

                return {
                    "type": "suggestion",
                    "thread_id": thread_id,
                    "mr_iid": mr_iid,
                    "suggestions": []
                }

            # ----------------------------------------------------
            # Get MR context from Elasticsearch
            # ----------------------------------------------------

            mr_details = make_gitlab_request(
                f"merge_requests/{mr_iid}"
            )

            if (
                isinstance(mr_details, dict)
                and "error" not in mr_details
            ):

                mr_context = (
                    get_mr_context_for_suggestions(
                        mr_iid,
                        mr_details.get(
                            "title",
                            ""
                        ),
                        mr_details.get(
                            "description",
                            ""
                        )
                    )
                )

            else:

                mr_context = []

            print(
                "\n🔍 Searching Elasticsearch "
                "for related Merge Requests..."
            )

            print(
                f"✅ Found {len(mr_context)} "
                "related Merge Requests."
            )

            # ----------------------------------------------------
            # Generate AI suggestions
            # ----------------------------------------------------

            print(
                "\n🤖 Generating "
                "context-aware AI code suggestions..."
            )

            suggestion_text = suggest_code(
                files,
                mr_context
            )

            # ----------------------------------------------------
            # Parse AI JSON response
            # ----------------------------------------------------

            try:

                json_start = (
                    suggestion_text.find("{")
                )

                json_end = (
                    suggestion_text.rfind("}") + 1
                )

                if (
                    json_start == -1
                    or json_end == 0
                ):
                    raise ValueError(
                        "No JSON object found"
                    )

                suggestion_data = json.loads(
                    suggestion_text[
                        json_start:json_end
                    ]
                )

            except (
                json.JSONDecodeError,
                ValueError
            ):

                return {
                    "type": "suggestion",
                    "thread_id": thread_id,
                    "mr_iid": mr_iid,
                    "suggestions": [],
                    "message": (
                        "AI returned an invalid "
                        "suggestion format."
                    ),
                    "raw_response": suggestion_text
                }

            return {
                "type": "suggestion",
                "thread_id": thread_id,
                "mr_iid": mr_iid,
                "suggestions": (
                    suggestion_data.get(
                        "suggestions",
                        []
                    )
                )
            }

    # ============================================================
    # DIRECT AI CODE REVIEW REQUEST
    # ============================================================

    # Supports:
    # "review mr 18"
    # "review MR !18"

    review_match = re.search(
        r"(?:review\s+)?(?:mr|merge request)\s*!?(\d+)",
        lower_message
    )

    if (
        "review" in lower_message
        and review_match
    ):

        mr_iid = int(
            review_match.group(1)
        )

        changes = get_merge_request_changes(
            mr_iid
        )

        if "changes" not in changes:

            return {
                "type": "review",
                "thread_id": thread_id,
                "mr_iid": mr_iid,
                "review": changes.get(
                    "message",
                    (
                        "Unable to retrieve "
                        "Merge Request changes."
                    )
                )
            }

        if not changes["changes"]:

            return {
                "type": "review",
                "thread_id": thread_id,
                "mr_iid": mr_iid,
                "review": (
                    "No changes found in this "
                    "Merge Request."
                )
            }

        diff_text = ""

        for change in changes["changes"]:

            diff_text += (
                f"\nFile: "
                f"{change.get('new_path', 'Unknown')}\n"
                f"{change.get('diff', '')}\n"
            )

        review = review_code(
            diff_text
        )

        return {
            "type": "review",
            "thread_id": thread_id,
            "mr_iid": mr_iid,
            "review": review
        }

    # ============================================================
    # DIRECT AI CODE SUGGESTION REQUEST
    # ============================================================

    # Supports:
    # "suggest for mr 18"
    # "give me suggestions for MR !18"

    suggestion_match = re.search(
        r"(?:mr|merge request)\s*!?(\d+)",
        lower_message
    )

    if (
        "suggest" in lower_message
        and suggestion_match
    ):

        mr_iid = int(
            suggestion_match.group(1)
        )

        # --------------------------------------------------------
        # Get actual source files
        # --------------------------------------------------------

        files = get_merge_request_source_files(
            mr_iid
        )

        if (
            isinstance(files, dict)
            and "error" in files
        ):

            return {
                "type": "suggestion",
                "thread_id": thread_id,
                "mr_iid": mr_iid,
                "suggestions": [],
                "message": files.get(
                    "error",
                    (
                        "Unable to retrieve "
                        "Merge Request files."
                    )
                )
            }

        if not files:

            return {
                "type": "suggestion",
                "thread_id": thread_id,
                "mr_iid": mr_iid,
                "suggestions": []
            }

        # --------------------------------------------------------
        # Get Elasticsearch context
        # --------------------------------------------------------

        mr_details = make_gitlab_request(
            f"merge_requests/{mr_iid}"
        )

        if (
            isinstance(mr_details, dict)
            and "error" not in mr_details
        ):

            mr_context = (
                get_mr_context_for_suggestions(
                    mr_iid,
                    mr_details.get(
                        "title",
                        ""
                    ),
                    mr_details.get(
                        "description",
                        ""
                    )
                )
            )

        else:

            mr_context = []

        print(
            "\n🔍 Searching Elasticsearch "
            "for related Merge Requests..."
        )

        print(
            f"✅ Found {len(mr_context)} "
            "related Merge Requests."
        )

        # --------------------------------------------------------
        # Generate suggestions
        # --------------------------------------------------------

        suggestion_text = suggest_code(
            files,
            mr_context
        )

        # --------------------------------------------------------
        # Parse AI response
        # --------------------------------------------------------

        try:

            json_start = (
                suggestion_text.find("{")
            )

            json_end = (
                suggestion_text.rfind("}") + 1
            )

            if (
                json_start == -1
                or json_end == 0
            ):
                raise ValueError(
                    "No JSON object found"
                )

            suggestion_data = json.loads(
                suggestion_text[
                    json_start:json_end
                ]
            )

        except (
            json.JSONDecodeError,
            ValueError
        ):

            return {
                "type": "suggestion",
                "thread_id": thread_id,
                "mr_iid": mr_iid,
                "suggestions": [],
                "message": (
                    "AI returned an invalid "
                    "suggestion format."
                ),
                "raw_response": suggestion_text
            }

        return {
            "type": "suggestion",
            "thread_id": thread_id,
            "mr_iid": mr_iid,
            "suggestions": (
                suggestion_data.get(
                    "suggestions",
                    []
                )
            )
        }

    # ============================================================
    # EXISTING LANGGRAPH CREATION WORKFLOW
    # ============================================================

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

    # ============================================================
    # LANGGRAPH HUMAN APPROVAL
    # ============================================================

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
            "mr_title": approval_request["mr_title"],
            "generated_code": approval_request.get(
                "generated_code",
                ""
            )
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
    branch = payload.get("ref", "").replace("refs/heads/", "")
    commit_sha = payload.get("after")
    user_name = payload.get("user_name")

    print("Event type:", event_type)
    print("Project:", project_name)
    print("Branch:", branch)
    print("Commit SHA:", commit_sha)
    print("User:", user_name)

    # ============================================================
    # IGNORE COMMITS CREATED BY "ACCEPT SUGGESTION"
    # ============================================================

    commits = payload.get("commits", [])

    for commit in commits:

        commit_message = commit.get("message", "")

        if commit_message.startswith("Apply AI code suggestion"):

            print(
                "📌 AI suggestion commit detected."
            )

            print(
                "ℹ️ Push detected from accepted suggestion."
            )

            print(
                "ℹ️ AI review/suggestion will NOT be triggered."
            )

            return {
                "status": "ignored",
                "reason": "AI suggestion commit",
                "commit_sha": commit_sha
            }

    # ============================================================
    # PUSH EVENT
    # ============================================================

    if event_type == "push":

        print("\n📌 Push event received.")

        # --------------------------------------------------------
        # Find open Merge Request for this branch
        # --------------------------------------------------------

        print(
            "\n🔍 Finding open Merge Request..."
        )

        merge_requests = get_merge_request_for_branch(branch)

        if (
            not isinstance(merge_requests, list)
            or not merge_requests
        ):

            print(
                "⚠️ No open Merge Request found for this branch."
            )

            return {
                "status": "received",
                "message": (
                    "No open Merge Request found for this branch."
                ),
                "branch": branch,
                "commit_sha": commit_sha
            }

        mr = merge_requests[0]
        mr_iid = mr["iid"]

        print(
            f"✅ Found Merge Request: !{mr_iid}"
        )

        # --------------------------------------------------------
        # Get actual source files from MR source branch
        # --------------------------------------------------------

        print(
            "\n🔍 Getting current source files..."
        )

        file_contents = get_merge_request_source_files(
            mr_iid
        )

        if (
            isinstance(file_contents, dict)
            and "error" in file_contents
        ):

            print(
                "❌ Failed to get source files:"
            )
            print(file_contents)

            return {
                "status": "error",
                "message": "Failed to get source files.",
                "details": file_contents
            }

        if not file_contents:

            print(
                "⚠️ No source files found."
            )

            return {
                "status": "received",
                "message": "No source files found.",
                "mr_iid": mr_iid
            }

        # --------------------------------------------------------
        # Generate AI code suggestions
        #
        # PUSH EVENT:
        # Do NOT use Elasticsearch MR context here.
        # --------------------------------------------------------

        print(
            "\n🤖 Generating AI code suggestions for push..."
        )

        suggestion_response = suggest_code(
            file_contents,
            []
        )

        try:

            json_start = suggestion_response.find("{")
            json_end = suggestion_response.rfind("}") + 1

            if json_start == -1 or json_end == 0:
                raise ValueError(
                    "No JSON object found in AI response."
                )

            suggestion_data = json.loads(
                suggestion_response[
                    json_start:json_end
                ]
            )

            suggestions = suggestion_data.get(
                "suggestions",
                []
            )

        except (
            json.JSONDecodeError,
            ValueError
        ):

            suggestions = []

        # --------------------------------------------------------
        # No suggestions
        # --------------------------------------------------------

        if not suggestions:

            print(
                "ℹ️ No meaningful code improvements suggested."
            )

            return {
                "status": "completed",
                "event_type": "push",
                "mr_iid": mr_iid,
                "suggestions": []
            }

        # --------------------------------------------------------
        # Post suggestions to GitLab MR
        # --------------------------------------------------------

        suggestion_text = (
            "## 🤖 AI Code Suggestions\n\n"
        )

        for index, suggestion in enumerate(
            suggestions,
            start=1
        ):

            suggestion_text += (
                f"### Suggestion {index}\n\n"
                f"**File:** "
                f"{suggestion.get('file', 'Unknown')}\n\n"
                f"**Current Code:**\n"
                f"```python\n"
                f"{suggestion.get('current_code', '')}\n"
                f"```\n\n"
                f"**Suggested Code:**\n"
                f"```python\n"
                f"{suggestion.get('suggested_code', '')}\n"
                f"```\n\n"
                f"**Reason:** "
                f"{suggestion.get('reason', '')}\n\n"
                "---\n\n"
            )

        print(
            "\n💬 Posting AI suggestions to GitLab..."
        )

        post_result = post_ai_suggestion(
            mr_iid,
            suggestion_text
        )

        print(
            "GitLab suggestion response:"
        )
        print(post_result)

        print(
            "====================================\n"
        )

        return {
            "status": "suggestions_generated",
            "event_type": "push",
            "project": project_name,
            "branch": branch,
            "commit_sha": commit_sha,
            "mr_iid": mr_iid,
            "suggestions": suggestions
        }

    # ============================================================
    # MERGE REQUEST EVENT
    # ============================================================

    if event_type == "merge_request":

        attributes = payload.get(
            "object_attributes",
            {}
        )

        mr_iid = attributes.get("iid")
        action = attributes.get("action")
        mr_title = attributes.get("title", "")
        mr_description = attributes.get("description", "")

        print(
            f"\n📌 Merge Request event received: !{mr_iid}"
        )

        print(
            f"Action: {action}"
        )

        if not mr_iid:

            return {
                "status": "error",
                "message": (
                    "Merge Request IID not found."
                )
            }

        # --------------------------------------------------------
        # Get actual source files
        # --------------------------------------------------------

        print(
            "\n🔍 Getting current source files..."
        )

        file_contents = get_merge_request_source_files(
            mr_iid
        )

        if (
            isinstance(file_contents, dict)
            and "error" in file_contents
        ):

            return {
                "status": "error",
                "message": "Failed to get MR source files.",
                "details": file_contents
            }

        if not file_contents:

            return {
                "status": "completed",
                "event_type": "merge_request",
                "mr_iid": mr_iid,
                "suggestions": []
            }

        # --------------------------------------------------------
        # Get related Merge Request context
        #
        # MR CODE SUGGESTION:
        # This is where Elasticsearch context is used.
        # --------------------------------------------------------

        print(
            "\n🔍 Searching Elasticsearch for related Merge Requests..."
        )

        mr_context = get_mr_context_for_suggestions(
            mr_iid,
            mr_title,
            mr_description
        )

        print(
            f"✅ Found {len(mr_context)} related Merge Requests."
        )

        # --------------------------------------------------------
        # Generate AI code suggestions
        # --------------------------------------------------------

        print(
            "\n🤖 Generating context-aware AI code suggestions..."
        )

        suggestion_response = suggest_code(
            file_contents,
            mr_context
        )

        try:

            json_start = suggestion_response.find("{")
            json_end = suggestion_response.rfind("}") + 1

            if json_start == -1 or json_end == 0:
                raise ValueError(
                    "No JSON object found in AI response."
                )

            suggestion_data = json.loads(
                suggestion_response[
                    json_start:json_end
                ]
            )

            suggestions = suggestion_data.get(
                "suggestions",
                []
            )

        except (
            json.JSONDecodeError,
            ValueError
        ):

            suggestions = []

        # --------------------------------------------------------
        # No suggestions
        # --------------------------------------------------------

        if not suggestions:

            print(
                "ℹ️ No meaningful code improvements suggested."
            )

            return {
                "status": "completed",
                "event_type": "merge_request",
                "mr_iid": mr_iid,
                "suggestions": []
            }

        # --------------------------------------------------------
        # Post suggestions to GitLab MR
        # --------------------------------------------------------

        suggestion_text = (
            "## 🤖 AI Code Suggestions\n\n"
        )

        for index, suggestion in enumerate(
            suggestions,
            start=1
        ):

            suggestion_text += (
                f"### Suggestion {index}\n\n"
                f"**File:** "
                f"{suggestion.get('file', 'Unknown')}\n\n"
                f"**Current Code:**\n"
                f"```python\n"
                f"{suggestion.get('current_code', '')}\n"
                f"```\n\n"
                f"**Suggested Code:**\n"
                f"```python\n"
                f"{suggestion.get('suggested_code', '')}\n"
                f"```\n\n"
                f"**Reason:** "
                f"{suggestion.get('reason', '')}\n\n"
                "---\n\n"
            )

        print(
            "\n💬 Posting AI suggestions to GitLab..."
        )

        post_result = post_ai_suggestion(
            mr_iid,
            suggestion_text
        )

        print(
            "GitLab suggestion response:"
        )
        print(post_result)

        print(
            "====================================\n"
        )

        return {
            "status": "suggestions_generated",
            "event_type": "merge_request",
            "project": project_name,
            "mr_iid": mr_iid,
            "suggestions": suggestions
        }

    # ============================================================
    # OTHER EVENTS
    # ============================================================

    print(
        f"ℹ️ Ignoring unsupported event type: {event_type}"
    )

    return {
        "status": "ignored",
        "event_type": event_type
    }