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

Therefore, return ONLY executable Python source code.
"""

    print("🤖 Generating code using Qwen...")

    response = llm1.invoke(prompt)

    generated_code = response.content.strip()

    # ------------------------------------------------------------
    # Clean accidental Markdown code fences
    # ------------------------------------------------------------

    lines = generated_code.splitlines()

    opening_fence_index = None
    closing_fence_index = None

    # Find the first Markdown code fence
    for index, line in enumerate(lines):

        if line.strip().startswith("```"):
            opening_fence_index = index
            break

    # If a code fence exists, extract only the code inside it
    if opening_fence_index is not None:

        for index in range(
            opening_fence_index + 1,
            len(lines)
        ):

            if lines[index].strip() == "```":
                closing_fence_index = index
                break

        if closing_fence_index is not None:

            lines = lines[
                opening_fence_index + 1:
                closing_fence_index
            ]

        else:

            # Opening fence exists but no closing fence
            lines = lines[
                opening_fence_index + 1:
            ]

        generated_code = "\n".join(lines).strip()

    # ------------------------------------------------------------
    # Validate generated Python
    # ------------------------------------------------------------

    try:

        compile(
            generated_code,
            "<generated_code>",
            "exec"
        )

    except SyntaxError as error:

        print("❌ Qwen generated invalid Python.")

        print("\n========== INVALID GENERATED CODE ==========")
        print(generated_code)
        print("============================================")

        raise ValueError(
            "Generated code contains invalid Python syntax."
        ) from error

    # ------------------------------------------------------------
    # Final generated code
    # ------------------------------------------------------------

    print("\n========== GENERATED CODE ==========")
    print(generated_code)
    print("====================================")

    return {
        "generated_code": generated_code
    }

def unit_test_agent(state: WorkflowState):

    import os
    import re
    import sys
    import subprocess
    import tempfile

    print("\n========== UNIT TEST AGENT ==========")

    generated_code = state["generated_code"]

    if not generated_code.strip():
        return {
            "test_result": "No generated code available for testing.",
            "test_passed": False
        }

    # ------------------------------------------------------------
    # Ask Qwen to generate tests
    # ------------------------------------------------------------

    prompt = f"""
You are a senior Python test engineer.

Generate pytest unit tests for the following Python source code.

============================================================
SOURCE CODE
============================================================

{generated_code}

============================================================
IMPORTANT TEST REQUIREMENTS
============================================================

- Use pytest.
- The source code will be saved as "generated_feature.py".
- Import the required objects from generated_feature.
- Do NOT recreate or rewrite the application code inside the test.
- Test the actual code from generated_feature.py.
- Test the main functionality of the generated code.
- Test important edge cases only when they are actually relevant.
- Do not invent functionality that does not exist.

============================================================
FASTAPI REQUIREMENT
============================================================

If the source code contains a FastAPI application named "app":

- Import it using:

from generated_feature import app

- Use FastAPI's TestClient:

from fastapi.testclient import TestClient

- Create the client using:

client = TestClient(app)

- Do NOT use:
  app.test_client()

- Do NOT use Flask testing APIs.

For example, if the source code contains:

@app.get("/health")
def health_check():
    return {{"status": "healthy"}}

the test should use:

response = client.get("/health")

and verify:

response.status_code == 200

and:

response.json() == {{"status": "healthy"}}

============================================================
OUTPUT REQUIREMENTS
============================================================

- Return ONLY executable Python test code.
- Do NOT include explanations.
- Do NOT include Markdown.
- Do NOT use Markdown code fences.
- Do NOT include text before or after the Python code.
- Do NOT include the original source code again.
- Do NOT include comments explaining the answer.

The generated response will be saved directly as a Python
test file and executed using pytest.

Therefore, return ONLY valid Python code.
"""

    print("🤖 Generating tests using Qwen...")

    response = llm1.invoke(prompt)

    test_code = response.content.strip()

    # ------------------------------------------------------------
    # Remove accidental Markdown code fences
    # ------------------------------------------------------------

    fenced_match = re.search(
        r"```(?:python|py)?\s*(.*?)```",
        test_code,
        re.DOTALL | re.IGNORECASE
    )

    if fenced_match:

        test_code = fenced_match.group(1).strip()

    else:

        lines = test_code.splitlines()

        # Remove accidental opening fence
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]

        # Remove accidental closing fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        test_code = "\n".join(lines).strip()

    # ------------------------------------------------------------
    # Make sure generated tests import the generated source
    # ------------------------------------------------------------

    if "from generated_feature import" not in test_code:

        test_code = (
            "from generated_feature import *\n\n"
            + test_code
        )

    # ------------------------------------------------------------
    # Validate generated test syntax
    # ------------------------------------------------------------

    try:

        compile(
            test_code,
            "generated_test.py",
            "exec"
        )

    except SyntaxError as error:

        print(
            f"❌ Generated tests contain invalid Python: {error}"
        )

        print(
            "\n========== INVALID TEST CODE =========="
        )
        print(test_code)
        print("=======================================")

        return {
            "test_result": (
                f"Generated tests contain invalid Python: {error}"
            ),
            "test_passed": False
        }

    print("\n========== GENERATED TESTS ==========")
    print(test_code)
    print("=====================================")

    # ------------------------------------------------------------
    # Create temporary testing directory
    # ------------------------------------------------------------

    with tempfile.TemporaryDirectory() as temp_dir:

        source_file = os.path.join(
            temp_dir,
            "generated_feature.py"
        )

        test_file = os.path.join(
            temp_dir,
            "test_generated_feature.py"
        )

        # --------------------------------------------------------
        # Write generated source code
        # --------------------------------------------------------

        with open(
            source_file,
            "w",
            encoding="utf-8"
        ) as file:

            file.write(generated_code)

        # --------------------------------------------------------
        # Write generated tests
        # --------------------------------------------------------

        with open(
            test_file,
            "w",
            encoding="utf-8"
        ) as file:

            file.write(test_code)

        # --------------------------------------------------------
        # Run pytest using the same Python interpreter
        # running the backend
        # --------------------------------------------------------

        print("\n🧪 Running pytest...")

        print(
            "Python interpreter:",
            sys.executable
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                test_file,
                "-v"
            ],
            cwd=temp_dir,
            capture_output=True,
            text=True
        )

        test_output = (
            result.stdout
            + "\n"
            + result.stderr
        ).strip()

        print("\n========== TEST RESULT ==========")
        print(test_output)
        print("=================================")

        # --------------------------------------------------------
        # Determine result
        # --------------------------------------------------------

        if result.returncode == 0:

            print(
                "✅ All generated tests passed."
            )

            return {
                "test_result": test_output,
                "test_passed": True
            }

        else:

            print(
                "❌ Generated tests failed."
            )

            return {
                "test_result": test_output,
                "test_passed": False
            }
def unit_test_router(state: WorkflowState):

    if state["test_passed"]:
        return "passed"

    return "failed"
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

