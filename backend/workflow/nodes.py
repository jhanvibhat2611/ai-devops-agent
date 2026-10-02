import json
import os
import subprocess

from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langgraph.types import interrupt

from workflow.state import WorkflowState
from elasticsearch_client import search_merge_requests

from storage.approval_history import (
    save_merge_request_approval
)


# ============================================================
# ENVIRONMENT + LLM
# ============================================================

load_dotenv()

llm1 = ChatOllama(model=os.getenv("OLLAMA_AI_MODEL"))
test_llm = ChatOllama(model=os.getenv("OLLAMA_TEST_MODEL") or os.getenv("OLLAMA_AI_MODEL"), temperature=0)


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
        state["user_request"], state["gitlab_project_id"]
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
    print("\n========== LANGGRAPH STATE ==========")
    print("User:", state.get("username"))
    print(
        "Project ID:",
        state.get("gitlab_project_id")
    )
    print(
        "Default branch:",
        state.get("gitlab_default_branch")
    )
    print("=====================================\n")

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
- Keep module imports free of demo/example execution unless the user explicitly requests it.
- Normally emit only functions, classes, routes and configuration definitions.
- Do not issue example tokens, print examples, call feature functions or start servers
  (such as app.run()) at module scope. Put explicitly requested demos behind a main guard.
- Never hardcode real secrets. Use environment configuration where appropriate;
  require a configured production signing key rather than an insecure default secret.
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
    from workflow.test_agent import test_implementation
    return test_implementation(state, test_llm)


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

    if state.get("test_passed", False):
        return "passed"

    return "failed"

def security_router(state: WorkflowState):

    if state["security_passed"]:
        return "passed"

    return "failed"
# ============================================================
# CREATE GITLAB BRANCH
# ============================================================


def create_branch(
    state: WorkflowState
):

    from main import create_gitlab_branch
    from storage.auth import get_gitlab_token

    branch_name = state[
        "branch_name"
    ]

    username = state[
        "username"
    ]

    project_id = state[
        "gitlab_project_id"
    ]

    default_branch = (
        state.get(
            "gitlab_default_branch"
        )
        or "main"
    )

    use_existing_branch = state.get(
        "use_existing_branch",
        False
    )

    gitlab_token = get_gitlab_token(
        username
    )

    if not gitlab_token:

        raise RuntimeError(
            "GitLab token not found "
            f"for user: {username}"
        )

    print(
        "\n========== CREATE / SELECT BRANCH =========="
    )

    print(
        "User:",
        username
    )

    print(
        "Project ID:",
        project_id
    )

    print(
        "Branch:",
        branch_name
    )

    print(
        "Default branch:",
        default_branch
    )

    print(
        "Use existing:",
        use_existing_branch
    )

    # ========================================================
    # USE EXISTING BRANCH
    # ========================================================

    if use_existing_branch:

        print(
            f"✅ Using existing branch: "
            f"{branch_name}"
        )

        return {
            "branch_name": branch_name,
            "use_existing_branch": True
        }

    # ========================================================
    # CREATE NEW BRANCH
    # ========================================================

    result = create_gitlab_branch(
        branch_name=branch_name,
        ref=default_branch,
        project_id=project_id,
        gitlab_token=gitlab_token
    )

    print(
        "GitLab branch response:"
    )

    print(
        result
    )

    if (
        isinstance(result, dict)
        and "error" in result
    ):

        raise RuntimeError(
            "Unable to create GitLab branch: "
            f"{result.get('message', result)}"
        )

    return {
        "branch_name": branch_name,
        "use_existing_branch": False
    }
# ============================================================
# COMMIT GENERATED CODE LOCALLY
# ============================================================

def commit_generated_code(state: WorkflowState):
    from workflow.workspace import commit_generated_code as commit
    return commit(state)


def create_merge_request(
    state: WorkflowState
):

    from main import (
        create_gitlab_merge_request
    )

    from storage.auth import (
        get_gitlab_token
    )

    print(
        "\n========== CREATE MERGE REQUEST =========="
    )

    username = state[
        "username"
    ]

    project_id = state[
        "gitlab_project_id"
    ]

    default_branch = (
        state.get(
            "gitlab_default_branch"
        )
        or "main"
    )

    gitlab_token = get_gitlab_token(
        username
    )

    if not gitlab_token:

        raise RuntimeError(
            "GitLab token not found "
            f"for user: {username}"
        )

    result = create_gitlab_merge_request(
        source=state[
            "branch_name"
        ],
        target=default_branch,
        title=state[
            "mr_title"
        ],
        project_id=project_id,
        gitlab_token=gitlab_token
    )

    print(
        "Merge Request Response:",
        result
    )

    if (
        isinstance(result, dict)
        and "error" in result
    ):

        raise RuntimeError(
            "Unable to create Merge Request: "
            f"{result.get('message', result)}"
        )

    return {
        "mr_iid": result.get(
            "iid"
        ),
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
        "generated_code": state.get("generated_code", ""),
        "target_file": state["target_file"]
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

def save_approval_history(
    state: WorkflowState
):

    mr_iid = state.get(
        "mr_iid"
    )

    username = state.get(
        "username"
    )

    if not mr_iid:

        print(
            "⚠️ No MR IID found. Approval history not saved."
        )

        return {}

    if not username:

        print(
            "⚠️ No username found. Approval history not saved."
        )

        return {}

    save_merge_request_approval(
        mr_iid=mr_iid,
        username=username,
        status="approved",
        project_id=state["gitlab_project_id"],
        thread_id=state.get("thread_id")
    )

    print(
        "\n========== APPROVAL HISTORY =========="
    )

    print(
        "MR IID:",
        mr_iid
    )

    print(
        "Username:",
        username
    )

    print(
        "Status: approved"
    )

    print(
        "======================================"
    )

    return {}
