import json
import os
import re
import subprocess

from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langgraph.types import interrupt

from workflow.state import WorkflowState
from elasticsearch_client import search_merge_requests


# ============================================================
# ENVIRONMENT + LLM
# ============================================================

load_dotenv()

llm1 = ChatOllama(
    model=os.getenv("OLLAMA_AI_MODEL")
)


# ============================================================
# VALIDATE USER REQUEST
# ============================================================

def validate_request(state: WorkflowState):

    request = state["user_request"].strip()

    if not request:
        return {
            "request_valid": False,
            "validation_message": "Please provide a development task."
        }

    vague_requests = [
        "hi",
        "hello",
        "hey",
        "test",
        "help",
        "ok",
        "okay"
    ]

    if request.lower() in vague_requests:
        return {
            "request_valid": False,
            "validation_message": (
                "Please describe a development task. "
                "For example: 'Create a login system using JWT.'"
            )
        }

    return {
        "request_valid": True,
        "validation_message": ""
    }


# ============================================================
# VALIDATION ROUTER
# ============================================================

def validation_router(state: WorkflowState):

    if state["request_valid"]:
        return "valid"

    return "invalid"


# ============================================================
# RETRIEVE RELATED MERGE REQUESTS
# ============================================================

def retrieve_context(state: WorkflowState):

    print("\n========== ELASTICSEARCH CONTEXT ==========")
    print("🔍 Searching Elasticsearch...")

    results = search_merge_requests(
        state["user_request"]
    )

    print(
        f"✅ Found {len(results)} similar merge requests."
    )

    return {
        "context": results
    }


# ============================================================
# ANALYZE REQUIREMENT
# ============================================================

def analyze_requirement(state: WorkflowState):

    print("\n========== ANALYZE REQUIREMENT ==========")

    context_text = ""

    for mr in state.get("context", []):

        context_text += f"""
Title: {mr.get("title", "")}
Description: {mr.get("description", "")}
Author: {mr.get("author", "")}

"""

    if not context_text:
        context_text = (
            "No similar merge requests were found."
        )

    prompt = f"""
You are an AI DevOps Assistant.

Analyze the user's development request.

Use the related Merge Requests below as context.

============================================================
RELATED MERGE REQUESTS
============================================================

{context_text}

============================================================
USER REQUEST
============================================================

{state["user_request"]}

============================================================
INSTRUCTIONS
============================================================

Determine:

1. What needs to be implemented.
2. A suitable unique Git branch name.
3. A suitable commit message.
4. A suitable Merge Request title.

If similar Merge Requests exist:
- Take them into consideration.
- Do not blindly duplicate them.
- Generate a different branch name where appropriate.

Keep the analysis practical and concise.

============================================================
OUTPUT FORMAT
============================================================

Return ONLY valid JSON.

{{
    "analysis": "clear explanation of what needs to be implemented",
    "branch_name": "feature/example-name",
    "commit_message": "Implement example feature",
    "mr_title": "Implement example feature"
}}

Do not return Markdown.
Do not return code fences.
Do not return anything outside the JSON object.
"""

    print("🤖 Calling Qwen...")

    response = llm1.invoke(prompt)

    response_text = response.content.strip()

    print("\n========== AI REQUIREMENT RESPONSE ==========")
    print(response_text)
    print("==============================================")

    # --------------------------------------------------------
    # Extract JSON safely
    # --------------------------------------------------------

    json_start = response_text.find("{")
    json_end = response_text.rfind("}") + 1

    if json_start == -1 or json_end <= json_start:
        raise ValueError(
            "Qwen did not return a valid JSON object."
        )

    json_text = response_text[
        json_start:json_end
    ]

    try:
        data = json.loads(json_text)

    except json.JSONDecodeError as error:

        print("❌ Invalid JSON from Qwen:")
        print(json_text)

        raise ValueError(
            "Could not parse requirement analysis JSON."
        ) from error

    # --------------------------------------------------------
    # Validate required fields
    # --------------------------------------------------------

    required_fields = [
        "analysis",
        "branch_name",
        "commit_message",
        "mr_title"
    ]

    for field in required_fields:

        if not data.get(field):

            raise ValueError(
                f"Qwen response is missing '{field}'."
            )

    print("\n===== AI REQUIREMENT ANALYSIS =====")
    print("Analysis:", data["analysis"])
    print("Branch:", data["branch_name"])
    print("Commit:", data["commit_message"])
    print("MR Title:", data["mr_title"])
    print("===================================\n")

    return {
        "analysis": data["analysis"],
        "branch_name": data["branch_name"],
        "commit_message": data["commit_message"],
        "mr_title": data["mr_title"]
    }


# ============================================================
# GENERATE CODE
# ============================================================

def generate_code(state: WorkflowState):

    print("\n========== GENERATE CODE ==========")

    prompt = f"""
You are a senior Python software engineer.

Generate production-ready Python code for the requested development task.

============================================================
REQUIREMENT ANALYSIS
============================================================

{state["analysis"]}

============================================================
USER REQUEST
============================================================

{state["user_request"]}

============================================================
IMPORTANT REQUIREMENTS
============================================================

- Generate only the Python code required for this feature.
- Keep the implementation simple and maintainable.
- Use appropriate Python best practices.
- Include all required imports.
- Do not invent unrelated functionality.
- Do not include explanations.
- Do not include Markdown.
- Do not use Markdown code fences.
- Return only valid Python source code.

The generated code will be written directly into a Python file
inside a local GitLab repository.

Therefore the response must contain ONLY valid Python code.
"""

    print("🤖 Generating code using Qwen...")

    response = llm1.invoke(prompt)

    generated_code = response.content.strip()

    # --------------------------------------------------------
    # Remove accidental Markdown code fences
    # --------------------------------------------------------

    if generated_code.startswith("```"):

        lines = generated_code.splitlines()

        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        generated_code = "\n".join(lines).strip()

    # --------------------------------------------------------
    # Validate generated Python
    # --------------------------------------------------------

    try:
        compile(
            generated_code,
            "<generated_code>",
            "exec"
        )

    except SyntaxError as error:

        print("❌ Qwen generated invalid Python.")
        print(generated_code)

        raise ValueError(
            "Generated code contains invalid Python syntax."
        ) from error

    print("\n========== GENERATED CODE ==========")
    print(generated_code)
    print("====================================")

    return {
        "generated_code": generated_code
    }


# ============================================================
# CREATE GITLAB BRANCH
# ============================================================

def create_branch(state: WorkflowState):

    from main import create_gitlab_branch

    branch_name = state["branch_name"]

    print("\n========== CREATE BRANCH ==========")
    print("Branch:", branch_name)

    result = create_gitlab_branch(
        branch_name=branch_name,
        ref="main"
    )

    print("GitLab branch response:")
    print(result)

    return {
        "branch_name": branch_name
    }


# ============================================================
# COMMIT GENERATED CODE LOCALLY
# ============================================================

def commit_generated_code(state: WorkflowState):

    print("\n========== LOCAL GIT COMMIT ==========")

    repo_path = os.getenv(
        "LOCAL_REPO_PATH"
    )

    file_path = os.getenv(
        "GENERATED_CODE_FILE"
    )

    if not repo_path:
        raise ValueError(
            "LOCAL_REPO_PATH is not configured in .env"
        )

    if not file_path:
        raise ValueError(
            "GENERATED_CODE_FILE is not configured in .env"
        )

    branch_name = state["branch_name"]
    generated_code = state["generated_code"]
    commit_message = state["commit_message"]

    print("Local repository:", repo_path)
    print("Branch:", branch_name)
    print("Generated file:", file_path)

    # --------------------------------------------------------
    # Make sure repository exists
    # --------------------------------------------------------

    if not os.path.isdir(repo_path):

        raise ValueError(
            f"Local Git repository does not exist: {repo_path}"
        )

    # --------------------------------------------------------
    # Fetch the branch created on GitLab
    # --------------------------------------------------------

    print("\n🔄 Fetching remote branch...")

    subprocess.run(
        [
            "git",
            "-C",
            repo_path,
            "fetch",
            "origin",
            branch_name
        ],
        check=True
    )

    # --------------------------------------------------------
    # Checkout remote branch locally
    # --------------------------------------------------------

    print("🌿 Checking out branch locally...")

    subprocess.run(
        [
            "git",
            "-C",
            repo_path,
            "checkout",
            "-B",
            branch_name,
            f"origin/{branch_name}"
        ],
        check=True
    )

    # --------------------------------------------------------
    # Write generated code
    # --------------------------------------------------------

    full_file_path = os.path.join(
        repo_path,
        file_path
    )

    directory = os.path.dirname(
        full_file_path
    )

    if directory:
        os.makedirs(
            directory,
            exist_ok=True
        )

    print("📝 Writing generated code...")

    with open(
        full_file_path,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            generated_code.rstrip() + "\n"
        )

    print(
        "✅ File written:",
        full_file_path
    )

    # --------------------------------------------------------
    # Git status
    # --------------------------------------------------------

    print("\n========== GIT STATUS ==========")

    subprocess.run(
        [
            "git",
            "-C",
            repo_path,
            "status"
        ],
        check=True
    )

    # --------------------------------------------------------
    # Stage file
    # --------------------------------------------------------

    print("\n📦 Staging generated file...")

    subprocess.run(
        [
            "git",
            "-C",
            repo_path,
            "add",
            "--",
            file_path
        ],
        check=True
    )

    # --------------------------------------------------------
    # Commit
    # --------------------------------------------------------

    print("💾 Creating commit...")

    commit_result = subprocess.run(
        [
            "git",
            "-C",
            repo_path,
            "commit",
            "-m",
            commit_message
        ],
        check=False,
        capture_output=True,
        text=True
    )

    print(commit_result.stdout)

    if commit_result.returncode != 0:

        print(commit_result.stderr)

        raise RuntimeError(
            "Git commit failed."
        )

    # --------------------------------------------------------
    # Push
    # --------------------------------------------------------

    print("\n🚀 Pushing branch to GitLab...")

    subprocess.run(
        [
            "git",
            "-C",
            repo_path,
            "push",
            "-u",
            "origin",
            branch_name
        ],
        check=True
    )

    print(
        "\n✅ Generated code committed and pushed successfully."
    )

    return {
        "generated_code": generated_code
    }


# ============================================================
# CREATE MERGE REQUEST
# ============================================================

def create_merge_request(state: WorkflowState):

    from main import create_gitlab_merge_request

    print("\n========== CREATE MERGE REQUEST ==========")

    result = create_gitlab_merge_request(
        source=state["branch_name"],
        target="main",
        title=state["mr_title"]
    )

    print(
        "Merge Request Response:",
        result
    )

    return {
        "mr_url": result.get(
            "web_url",
            ""
        )
    }


# ============================================================
# HUMAN APPROVAL
# ============================================================

def human_approval(state: WorkflowState):

    approval_request = {
        "analysis": state["analysis"],
        "branch_name": state["branch_name"],
        "commit_message": state["commit_message"],
        "mr_title": state["mr_title"],
        "generated_code": state.get("generated_code", "")
    }

    decision = interrupt(approval_request)

    return {
        "approved": decision
    }

# ============================================================
# APPROVAL ROUTER
# ============================================================

def approval_router(state: WorkflowState):

    if state["approved"]:
        return "approved"

    return "rejected"

