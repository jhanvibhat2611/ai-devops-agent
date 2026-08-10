import json

from backend.workflow.state import WorkflowState
from backend.main import create_gitlab_branch
from backend.main import create_gitlab_merge_request
from backend.elasticsearch_client import search_merge_requests
import os
from langchain_ollama import ChatOllama
from dotenv import load_dotenv

load_dotenv()
llm1 = ChatOllama(
    model=os.getenv("OLLAMA_MODEL")
)

def retrieve_context(state: WorkflowState):

    print("🔍 Searching Elasticsearch...")

    results = search_merge_requests(state["user_request"])

    print(f"Found {len(results)} similar merge requests.")

    return {
        "context": results
    }

def analyze_requirement(state: WorkflowState):
    print("\n========== ANALYZE REQUIREMENT ==========")

    # Build context from retrieved merge requests
    context_text = ""

    for mr in state["context"]:
        context_text += f"""
Title: {mr.get("title", "")}
Description: {mr.get("description", "")}
Author: {mr.get("author", "")}

"""

    prompt = f"""
You are an AI DevOps Assistant.

Below are similar merge requests from this project.

{context_text}

Analyze the user's request using the retrieved merge requests as context.

If a similar merge request already exists:
- Mention it in the analysis.
- Avoid generating the exact same branch name or MR title.
- Generate a unique branch name and merge request title whenever possible.

Return ONLY a valid JSON object.

Do not include:
- Explanations
- Markdown
- Introductory text
- Closing remarks

Output must start with '{{' and end with '}}'.

{{
  "analysis": "...",
  "branch_name": "feature/...",
  "commit_message": "...",
  "mr_title": "..."
}}

User Request:
{state["user_request"]}
"""

    print("🤖 Calling Ollama...")

    response = llm1.invoke(prompt)

    print("✅ Response received from Ollama.")

    json_start = response.content.find("{")
    json_end = response.content.rfind("}") + 1

    if json_start == -1 or json_end == 0:
        raise ValueError("Ollama did not return a valid JSON object.")

    json_text = response.content[json_start:json_end]

    data = json.loads(json_text)

    print("\n===== AI Suggestions =====")
    print(f"Analysis: {data['analysis']}")
    print(f"Branch: {data['branch_name']}")
    print(f"Commit: {data['commit_message']}")
    print(f"MR Title: {data['mr_title']}")
    print("==========================\n")

    return {
        "analysis": data["analysis"],
        "branch_name": data["branch_name"],
        "commit_message": data["commit_message"],
        "mr_title": data["mr_title"],
    }

def create_branch(state: WorkflowState):

    branch_name = state["branch_name"]
    print("Branch from LLM:", state["branch_name"])
    result = create_gitlab_branch(
        branch_name=branch_name,
        ref="main"
    )

    print(result)

    return {
        "branch_name": branch_name
    }


def create_merge_request(state: WorkflowState):

    result = create_gitlab_merge_request(
        source=state["branch_name"],
        target="main",
        title=state["mr_title"]
    )

    print("Merge Request Response:", result)

    return {
        "mr_url": result.get("web_url", "")
    }

def human_approval(state: WorkflowState):

    print("\n===== AI Suggestions =====")
    print("Analysis:", state["analysis"])
    print("Branch:", state["branch_name"])
    print("Commit:", state["commit_message"])
    print("MR Title:", state["mr_title"])

    choice = input("\nApprove? (y/n): ")

    return {
        "approved": choice.lower() == "y"
    }
def approval_router(state: WorkflowState):
    if state["approved"]:
        return "approved"

    return "rejected"

