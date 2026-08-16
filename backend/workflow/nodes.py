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

    import ast
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
    # Extract source function/class names
    # Used to prevent Qwen from simply copying the implementation
    # ------------------------------------------------------------

    try:

        source_tree = ast.parse(generated_code)

        source_function_names = {
            node.name
            for node in ast.walk(source_tree)
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef
                )
            )
        }

    except SyntaxError as error:

        return {
            "test_result": (
                f"Generated source code is invalid Python: {error}"
            ),
            "test_passed": False
        }

    # ------------------------------------------------------------
    # Test generation prompt
    # ------------------------------------------------------------

    prompt = f"""
You are a senior Python test engineer.

Generate pytest unit tests for the following Python source code.

============================================================
SOURCE CODE
============================================================

{generated_code}

============================================================
CORE RULE
============================================================

You are writing a TEST FILE.

You are NOT rewriting the source code.

The source code already exists in a file called:

generated_feature.py

Your test file will be:

test_generated_feature.py

The test file will import and test the code from
generated_feature.py.

============================================================
STRICT REQUIREMENTS
============================================================

1. You MUST generate at least one function whose name starts
   with "test_".

2. Every actual test must be a pytest test function.

3. Do NOT recreate any function from the source code.

4. Do NOT copy the implementation into the test file.

5. Do NOT create another version of the application.

6. Do NOT create another FastAPI app.

7. Do NOT define the same functions that already exist in
   generated_feature.py.

8. Import the existing functions/classes/app from
   generated_feature.py instead.

9. Test the actual imported implementation.

10. Use pytest appropriately.

11. Test the main functionality.

12. Test relevant edge cases when appropriate.

13. Do not invent functionality that does not exist.

============================================================
FASTAPI TESTING
============================================================

If the source code contains:

app = FastAPI()

use:

from generated_feature import app
from fastapi.testclient import TestClient

client = TestClient(app)

Do NOT use:

app.test_client()

Do NOT use Flask testing APIs.

For example, if the source code contains:

@app.get("/health")
def health_check():
    return {{"status": "healthy"}}

generate a test such as:

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {{"status": "healthy"}}

============================================================
NORMAL PYTHON FUNCTIONS
============================================================

If the source code contains a normal Python function such as:

def add(a, b):
    return a + b

generate a test such as:

def test_add():
    assert add(2, 3) == 5

Do NOT redefine add().

============================================================
SIDE EFFECTS
============================================================

If the source code uses things such as:

- input()
- os.system()
- subprocess
- file operations
- external services

do NOT execute dangerous real-world operations during testing.

Use pytest tools such as:

- monkeypatch
- mocks
- temporary files

when appropriate.

For example, if a function calls input(), monkeypatch input()
instead of waiting for real user input.

If a function calls os.system(), mock os.system() instead of
actually executing a system command.

============================================================
OUTPUT REQUIREMENTS
============================================================

Return ONLY valid executable Python test code.

Do NOT return:

- explanations
- Markdown
- Markdown code fences
- the original source code
- copied implementations
- text before the tests
- text after the tests

The response will be saved directly as:

test_generated_feature.py

and executed using pytest.

Therefore, return ONLY the test code.
"""

    # ------------------------------------------------------------
    # Generate tests
    # ------------------------------------------------------------

    print("🤖 Generating tests using Qwen...")

    response = llm1.invoke(prompt)

    test_code = response.content.strip()

    # ------------------------------------------------------------
    # Remove accidental Markdown fences
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

        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        test_code = "\n".join(lines).strip()

    # ------------------------------------------------------------
    # Validate generated test code
    # ------------------------------------------------------------

    def validate_test_code(code):

        try:

            tree = ast.parse(code)

        except SyntaxError as error:

            return False, (
                f"Generated tests contain invalid Python: {error}"
            )

        # Find actual pytest test functions
        test_functions = [
            node.name
            for node in ast.walk(tree)
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef
                )
            )
            and node.name.startswith("test_")
        ]

        # --------------------------------------------------------
        # No test functions = not a test file
        # --------------------------------------------------------

        if not test_functions:

            return False, (
                "Qwen did not generate any pytest test functions."
            )

        # --------------------------------------------------------
        # Detect copied source implementation
        # --------------------------------------------------------

        copied_functions = [
            node.name
            for node in ast.walk(tree)
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef
                )
            )
            and node.name in source_function_names
            and not node.name.startswith("test_")
        ]

        if copied_functions:

            return False, (
                "Qwen recreated source functions instead of "
                f"testing them: {', '.join(copied_functions)}"
            )

        return True, ""

    valid_tests, validation_message = validate_test_code(
        test_code
    )

    # ------------------------------------------------------------
    # Retry once if Qwen failed to produce actual tests
    # ------------------------------------------------------------

    if not valid_tests:

        print(
            f"⚠️ Initial test generation rejected: "
            f"{validation_message}"
        )

        print(
            "🔄 Asking Qwen to regenerate the tests..."
        )

        retry_prompt = f"""
You previously failed to generate a valid test file.

Generate ONLY pytest tests for this Python source code:

============================================================
SOURCE CODE
============================================================

{generated_code}

============================================================
ABSOLUTE RULES
============================================================

The source code already exists in:

generated_feature.py

You MUST import and test it.

DO NOT recreate any source function.

DO NOT copy the implementation.

DO NOT create another application.

You MUST generate at least ONE function whose name starts
with:

test_

Every test must actually test something.

If this is FastAPI, use:

from generated_feature import app
from fastapi.testclient import TestClient

client = TestClient(app)

Do NOT use Flask's app.test_client().

If the source uses input(), os.system(), subprocess, or other
side effects, mock them instead of performing real operations.

Return ONLY valid Python pytest code.

No Markdown.
No code fences.
No explanations.
"""

        retry_response = llm1.invoke(
            retry_prompt
        )

        test_code = retry_response.content.strip()

        # Remove fences from retry response

        fenced_match = re.search(
            r"```(?:python|py)?\s*(.*?)```",
            test_code,
            re.DOTALL | re.IGNORECASE
        )

        if fenced_match:

            test_code = fenced_match.group(1).strip()

        else:

            lines = test_code.splitlines()

            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            test_code = "\n".join(lines).strip()

        # Validate retry

        valid_tests, validation_message = validate_test_code(
            test_code
        )

    # ------------------------------------------------------------
    # Stop if Qwen still did not generate valid tests
    # ------------------------------------------------------------

    if not valid_tests:

        print(
            f"❌ Unit test generation failed: "
            f"{validation_message}"
        )

        print(
            "\n========== INVALID TEST CODE =========="
        )
        print(test_code)
        print("=======================================")

        return {
            "test_result": validation_message,
            "test_passed": False
        }

    # ------------------------------------------------------------
    # Print generated tests
    # ------------------------------------------------------------

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
        # Run pytest using the backend's Python interpreter
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
def security_agent(state: WorkflowState):

    import ast
    import json
    import re

    print("\n========== SECURITY AGENT ==========")

    generated_code = state["generated_code"]

    if not generated_code.strip():
        return {
            "security_report": "No generated code available for security analysis.",
            "security_passed": False
        }

    # ------------------------------------------------------------
    # Basic deterministic security checks
    # ------------------------------------------------------------

    security_flags = []

    try:
        tree = ast.parse(generated_code)

        for node in ast.walk(tree):

            # Dangerous dynamic execution
            if isinstance(node, ast.Call):

                if isinstance(node.func, ast.Name):

                    if node.func.id in {
                        "eval",
                        "exec",
                        "__import__"
                    }:
                        security_flags.append(
                            f"Potentially dangerous function: {node.func.id}()"
                        )

                if isinstance(node.func, ast.Attribute):

                    # os.system(...)
                    if (
                        node.func.attr == "system"
                    ):
                        security_flags.append(
                            "Potential command execution through os.system()."
                        )

                    # subprocess calls
                    if (
                        node.func.attr in {
                            "Popen",
                            "call",
                            "run"
                        }
                    ):
                        for keyword in node.keywords:
                            if (
                                keyword.arg == "shell"
                                and isinstance(keyword.value, ast.Constant)
                                and keyword.value.value is True
                            ):
                                security_flags.append(
                                    "subprocess call uses shell=True."
                                )

            # Hardcoded credential-like assignments
            if isinstance(node, ast.Assign):

                for target in node.targets:

                    if isinstance(target, ast.Name):

                        variable_name = target.id.lower()

                        sensitive_names = {
                            "password",
                            "passwd",
                            "secret",
                            "api_key",
                            "apikey",
                            "access_token",
                            "auth_token",
                            "private_key"
                        }

                        if variable_name in sensitive_names:

                            if isinstance(node.value, ast.Constant):

                                if isinstance(
                                    node.value.value,
                                    str
                                ) and node.value.value.strip():

                                    security_flags.append(
                                        f"Potential hardcoded secret in variable '{target.id}'."
                                    )

    except SyntaxError as error:

        return {
            "security_report": (
                f"Generated code could not be parsed for security analysis: {error}"
            ),
            "security_passed": False
        }

    # ------------------------------------------------------------
    # Build deterministic findings
    # ------------------------------------------------------------

    deterministic_findings = "\n".join(
        f"- {flag}"
        for flag in security_flags
    )

    if not deterministic_findings:
        deterministic_findings = "No obvious security issues detected by static checks."

    # ------------------------------------------------------------
    # Ask Qwen for deeper security analysis
    # ------------------------------------------------------------

    prompt = f"""
You are a senior application security engineer reviewing
Python code before it is committed to a GitLab repository.

Analyze the following generated Python code for security risks.

============================================================
GENERATED CODE
============================================================

{generated_code}

============================================================
STATIC SECURITY CHECKS
============================================================

{deterministic_findings}

============================================================
SECURITY REVIEW REQUIREMENTS
============================================================

Look specifically for:

1. Hardcoded passwords, API keys, tokens, or secrets.
2. SQL injection risks.
3. Command injection risks.
4. Unsafe use of eval(), exec(), or dynamic code execution.
5. Unsafe subprocess usage.
6. Path traversal vulnerabilities.
7. Unsafe deserialization.
8. Missing authentication/authorization where clearly required.
9. Insecure handling of user-controlled input.
10. Other serious security vulnerabilities.

Do NOT report something as a vulnerability merely because
it is theoretically possible.

Only report issues that are actually relevant to the code.

============================================================
SEVERITY
============================================================

Use only:

CRITICAL
HIGH
MEDIUM
LOW
NONE

CRITICAL/HIGH:
A serious security vulnerability that should block the change.

MEDIUM:
A meaningful security concern that should be reviewed.

LOW:
A minor security improvement.

NONE:
No meaningful security issue found.

============================================================
OUTPUT
============================================================

Return ONLY valid JSON.

Use exactly this structure:

{{
    "overall_status": "PASS",
    "findings": [
        {{
            "severity": "NONE",
            "issue": "No security issues found.",
            "recommendation": ""
        }}
    ],
    "summary": "..."
}}

Rules:

- overall_status must be either PASS or FAIL.
- Use FAIL only if there is at least one CRITICAL or HIGH issue.
- Use PASS for NONE, LOW, and MEDIUM findings.
- Do not include Markdown.
- Do not include explanations outside the JSON.
- Return valid JSON only.
"""

    print("🔐 Analyzing generated code with Qwen...")

    response = llm1.invoke(prompt)

    security_response = response.content.strip()

    # ------------------------------------------------------------
    # Remove accidental Markdown fences
    # ------------------------------------------------------------

    fenced_match = re.search(
        r"```(?:json)?\s*(.*?)```",
        security_response,
        re.DOTALL | re.IGNORECASE
    )

    if fenced_match:
        security_response = fenced_match.group(1).strip()

    # ------------------------------------------------------------
    # Extract JSON
    # ------------------------------------------------------------

    json_start = security_response.find("{")
    json_end = security_response.rfind("}") + 1

    if json_start == -1 or json_end == 0:

        print("❌ Qwen returned invalid security analysis.")

        return {
            "security_report": (
                "Security analysis failed because the model "
                "did not return valid JSON."
            ),
            "security_passed": False
        }

    json_text = security_response[
        json_start:json_end
    ]

    try:

        security_data = json.loads(json_text)

    except json.JSONDecodeError as error:

        print("❌ Could not parse security analysis.")

        return {
            "security_report": (
                f"Invalid security analysis JSON: {error}"
            ),
            "security_passed": False
        }

    # ------------------------------------------------------------
    # Determine whether security gate passes
    # ------------------------------------------------------------

    findings = security_data.get(
        "findings",
        []
    )

    overall_status = security_data.get(
        "overall_status",
        "FAIL"
    )

    high_risk_findings = []

    for finding in findings:

        severity = str(
            finding.get("severity", "NONE")
        ).upper()

        if severity in {
            "CRITICAL",
            "HIGH"
        }:
            high_risk_findings.append(
                finding
            )

    # ------------------------------------------------------------
    # Combine static findings with AI findings
    # ------------------------------------------------------------

    report_lines = []

    report_lines.append(
        f"Overall Status: {overall_status}"
    )

    report_lines.append(
        f"Summary: {security_data.get('summary', '')}"
    )

    report_lines.append(
        "\nSecurity Findings:"
    )

    if findings:

        for index, finding in enumerate(
            findings,
            start=1
        ):

            severity = finding.get(
                "severity",
                "NONE"
            )

            issue = finding.get(
                "issue",
                ""
            )

            recommendation = finding.get(
                "recommendation",
                ""
            )

            report_lines.append(
                f"{index}. [{severity}] {issue}"
            )

            if recommendation:

                report_lines.append(
                    f"   Recommendation: {recommendation}"
                )

    else:

        report_lines.append(
            "No security findings."
        )

    if security_flags:

        report_lines.append(
            "\nStatic Security Checks:"
        )

        for flag in security_flags:

            report_lines.append(
                f"- {flag}"
            )

    security_report = "\n".join(
        report_lines
    )

    security_passed = (
        overall_status == "PASS"
        and not high_risk_findings
        and not security_flags
    )

    # ------------------------------------------------------------
    # Final output
    # ------------------------------------------------------------

    print("\n========== SECURITY RESULT ==========")
    print(security_report)
    print("=====================================")

    if security_passed:

        print(
            "✅ Security checks passed."
        )

    else:

        print(
            "❌ Security checks failed."
        )

    return {
        "security_report": security_report,
        "security_passed": security_passed
    }

def unit_test_router(state: WorkflowState):

    if state["test_passed"]:
        return "passed"

    return "failed"

def security_router(state: WorkflowState):

    if state["security_passed"]:
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

