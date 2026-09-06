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

    generated_code = state.get(
        "generated_code",
        ""
    )

    if not generated_code.strip():
        return {
            "test_result": "No generated code available for testing.",
            "test_passed": False
        }

    # ============================================================
    # VALIDATE GENERATED SOURCE CODE
    # ============================================================

    try:
        source_tree = ast.parse(
            generated_code
        )

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

    # ============================================================
    # CLEAN LLM RESPONSE
    # ============================================================

    def clean_test_code(code):

        if not code:
            return ""

        code = code.strip()

        fenced_match = re.search(
            r"```(?:python|py)?\s*(.*?)```",
            code,
            re.DOTALL | re.IGNORECASE
        )

        if fenced_match:
            return fenced_match.group(1).strip()

        lines = code.splitlines()

        if (
            lines
            and lines[0].strip().startswith("```")
        ):
            lines = lines[1:]

        if (
            lines
            and lines[-1].strip() == "```"
        ):
            lines = lines[:-1]

        return "\n".join(lines).strip()

    # ============================================================
    # PRESERVE IMPORTS
    # ============================================================

    def preserve_original_imports(
        original_test_code,
        corrected_test_code
    ):

        try:
            original_tree = ast.parse(
                original_test_code
            )

            corrected_tree = ast.parse(
                corrected_test_code
            )

        except SyntaxError:
            return corrected_test_code

        original_imports = []
        corrected_imports = set()

        for node in corrected_tree.body:

            if isinstance(
                node,
                (
                    ast.Import,
                    ast.ImportFrom
                )
            ):
                corrected_imports.add(
                    ast.unparse(node)
                )

        for node in original_tree.body:

            if isinstance(
                node,
                (
                    ast.Import,
                    ast.ImportFrom
                )
            ):
                import_text = ast.unparse(
                    node
                )

                if import_text not in corrected_imports:
                    original_imports.append(
                        import_text
                    )

        if not original_imports:
            return corrected_test_code

        return (
            "\n".join(original_imports)
            + "\n\n"
            + corrected_test_code.strip()
        )

    # ============================================================
    # VALIDATE TEST STRUCTURE
    # ============================================================

    def validate_test_code(code):

        if not code.strip():
            return False, "Generated test code is empty."

        try:
            tree = ast.parse(
                code
            )

        except SyntaxError as error:
            return False, (
                f"Generated tests contain invalid Python: {error}"
            )

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
            and node.name.startswith(
                "test_"
            )
        ]

        if not test_functions:
            return False, (
                "Qwen did not generate any pytest test functions."
            )

        if len(test_functions) > 5:
            return False, (
                "Generated more than 5 test functions."
            )

        # --------------------------------------------------------
        # Prevent recreating source functions
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
            and not node.name.startswith(
                "test_"
            )
        ]

        if copied_functions:
            return False, (
                "Qwen recreated source functions instead of testing them: "
                f"{', '.join(copied_functions)}"
            )

        # --------------------------------------------------------
        # Reject Hypothesis
        # --------------------------------------------------------

        for node in ast.walk(tree):

            if isinstance(
                node,
                ast.Import
            ):

                for alias in node.names:

                    if (
                        alias.name == "hypothesis"
                        or alias.name.startswith(
                            "hypothesis."
                        )
                    ):
                        return False, (
                            "Generated tests use Hypothesis."
                        )

            elif isinstance(
                node,
                ast.ImportFrom
            ):

                if (
                    node.module == "hypothesis"
                    or (
                        node.module
                        and node.module.startswith(
                            "hypothesis."
                        )
                    )
                ):
                    return False, (
                        "Generated tests use Hypothesis."
                    )

        # --------------------------------------------------------
        # Reject mocking implementation under test
        # --------------------------------------------------------

        for node in ast.walk(tree):

            if not isinstance(
                node,
                ast.Call
            ):
                continue

            patch_target = None

            if (
                isinstance(
                    node.func,
                    ast.Name
                )
                and node.func.id == "patch"
                and node.args
                and isinstance(
                    node.args[0],
                    ast.Constant
                )
            ):
                patch_target = str(
                    node.args[0].value
                )

            elif (
                isinstance(
                    node.func,
                    ast.Attribute
                )
                and node.func.attr == "patch"
                and node.args
                and isinstance(
                    node.args[0],
                    ast.Constant
                )
            ):
                patch_target = str(
                    node.args[0].value
                )

            if patch_target:

                for function_name in source_function_names:

                    if patch_target.endswith(
                        f".{function_name}"
                    ):
                        return False, (
                            "Generated tests mock the implementation "
                            f"being tested: {function_name}"
                        )

        return True, ""

    # ============================================================
    # RUN PYTEST
    # ============================================================

    def run_tests(
        source_code,
        test_code
    ):

        with tempfile.TemporaryDirectory() as temp_dir:

            source_file = os.path.join(
                temp_dir,
                "generated_feature.py"
            )

            test_file = os.path.join(
                temp_dir,
                "test_generated_feature.py"
            )

            with open(
                source_file,
                "w",
                encoding="utf-8"
            ) as file:
                file.write(
                    source_code.rstrip()
                    + "\n"
                )

            with open(
                test_file,
                "w",
                encoding="utf-8"
            ) as file:
                file.write(
                    test_code.rstrip()
                    + "\n"
                )

            print(
                "\n🧪 Running pytest..."
            )

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

            return (
                result.returncode,
                test_output
            )

    # ============================================================
    # INITIAL TEST GENERATION PROMPT
    # ============================================================

    prompt = f"""
You are a careful senior Python test engineer.

Generate a COMPLETE pytest test file for the exact Python source
code below.

============================================================
SOURCE CODE
============================================================

{generated_code}

============================================================
IMPORTANT
============================================================

The implementation already exists in:

generated_feature.py

Your job is ONLY to test the existing implementation.

Do NOT:

- rewrite the implementation
- redefine implementation functions
- copy implementation code into tests
- invent requirements
- invent validation
- invent exceptions
- invent unsupported behavior
- mock the implementation being tested

============================================================
VALID INPUT DOMAIN
============================================================

Test behavior inside the valid input domain implied by the source
and requirement.

If a function is intended to receive a NON-EMPTY list, do NOT
invent behavior for an empty list unless the implementation
explicitly defines it.

Do NOT expect exceptions simply because an out-of-domain input
exists.

============================================================
EXPECTED VALUES
============================================================

Every expected result must be correct.

Before writing every assertion:

1. Trace the implementation carefully.
2. Calculate the expected output.
3. Verify arithmetic.
4. Prefer small and easily checked values.

Do NOT guess expected outputs.

============================================================
EXPECTED VALUE ORACLES
============================================================

When the expected result can be safely expressed using a simple,
independent Python standard-library expression, prefer that instead
of manually hardcoding arithmetic.

Examples:

For a range calculation:

expected = max(numbers) - min(numbers)

For a sum:

expected = sum(numbers)

For a count:

expected = len([...])

For string reversal:

expected = value[::-1]

Only use such reference expressions when they directly represent
the stated behavior and do NOT simply call the function under test.

============================================================
TEST STRUCTURE
============================================================

- Import from generated_feature.py.
- Generate between 1 and 5 test functions.
- Every test function must start with test_.
- Prefer ONE logical case per test function.
- Prefer one primary assertion per test.
- Use deterministic fixed inputs.
- Keep tests simple and readable.

============================================================
DEPENDENCIES
============================================================

Use ONLY:

- pytest
- Python standard library
- dependencies already used by the source code

Do NOT use:

- hypothesis
- @given
- hypothesis.strategies
- random inputs
- property-based testing
- unnecessary mocks
- extra third-party test libraries

============================================================
FLOATS
============================================================

Use normal finite values.

Do NOT use:

- NaN
- infinity
- extremely large floating-point values

unless explicitly required.

============================================================
SIDE EFFECTS
============================================================

Only mock genuine external dependencies such as:

- HTTP requests
- databases
- subprocess calls
- external APIs

Never mock the function being tested.

============================================================
OUTPUT
============================================================

Return ONLY the COMPLETE executable pytest file.

NO explanations.
NO Markdown.
NO code fences.
"""

    # ============================================================
    # GENERATE INITIAL TESTS
    # ============================================================

    print(
        "🤖 Generating tests using Qwen..."
    )

    response = llm1.invoke(
        prompt
    )

    test_code = clean_test_code(
        response.content
    )

    valid_tests, validation_message = (
        validate_test_code(
            test_code
        )
    )

    # ============================================================
    # ONE STRUCTURAL RETRY
    # ============================================================

    if not valid_tests:

        print(
            "\n⚠️ Generated tests rejected:"
        )

        print(
            validation_message
        )

        retry_prompt = f"""
The previous pytest file was structurally invalid.

REJECTION REASON:

{validation_message}

============================================================
SOURCE CODE
============================================================

{generated_code}

============================================================
YOUR TASK
============================================================

Generate a NEW COMPLETE pytest file.

STRICT RULES:

- Import from generated_feature.py.
- Include all required imports.
- Generate 1 to 5 test functions.
- Every function must start with test_.
- Prefer one logical case per test.
- Use deterministic inputs.
- Stay inside the valid input domain.
- Do not use Hypothesis.
- Do not use random values.
- Do not mock the implementation.
- Do not redefine source functions.
- Do not copy the implementation.
- Do not invent behavior.
- Do not invent exceptions.
- Prefer simple Python reference expressions when they safely
  represent the expected behavior.
- Calculate every expected result carefully.

Return ONLY executable Python code.

NO explanations.
NO Markdown.
NO code fences.
"""

        print(
            "\n🔄 Regenerating tests..."
        )

        response = llm1.invoke(
            retry_prompt
        )

        test_code = clean_test_code(
            response.content
        )

        valid_tests, validation_message = (
            validate_test_code(
                test_code
            )
        )

    # ============================================================
    # STOP IF STRUCTURE STILL INVALID
    # ============================================================

    if not valid_tests:

        print(
            "\n❌ Unit test generation failed:"
        )

        print(
            validation_message
        )

        return {
            "test_result": validation_message,
            "test_passed": False
        }

    # ============================================================
    # SHOW GENERATED TESTS
    # ============================================================

    print(
        "\n========== GENERATED TESTS =========="
    )

    print(
        test_code
    )

    print(
        "====================================="
    )

    # ============================================================
    # INITIAL PYTEST RUN
    # ============================================================

    return_code, test_output = run_tests(
        generated_code,
        test_code
    )

    print(
        "\n========== TEST RESULT =========="
    )

    print(
        test_output
    )

    print(
        "================================="
    )

    # ============================================================
    # INITIAL PASS
    # ============================================================

    if return_code == 0:

        print(
            "✅ All generated tests passed."
        )

        return {
            "test_result": test_output,
            "test_passed": True
        }

    # ============================================================
    # BOUNDED REPAIR LOOP
    # ============================================================

    print(
        "\n⚠️ Generated tests failed."
    )

    max_repair_attempts = 2

    current_test_code = test_code
    current_test_output = test_output

    for repair_attempt in range(
        1,
        max_repair_attempts + 1
    ):

        print(
            f"\n🔄 Test repair attempt "
            f"{repair_attempt}/{max_repair_attempts}..."
        )

        correction_prompt = f"""
You are a senior Python test engineer repairing an existing pytest
test file.

============================================================
SOURCE IMPLEMENTATION
============================================================

{generated_code}

============================================================
CURRENT COMPLETE TEST FILE
============================================================

{current_test_code}

============================================================
PYTEST FAILURE OUTPUT
============================================================

{current_test_output}

============================================================
YOUR TASK
============================================================

Repair the COMPLETE test file.

DO NOT modify the source implementation.

Return the COMPLETE corrected pytest file, including:

- all required imports
- all valid passing tests
- all corrected failing tests

============================================================
CHECK EVERY ASSERTION
============================================================

Do NOT inspect only the traceback.

Pytest may stop a test function at its first failing assertion.

Therefore:

1. Re-check EVERY test function.
2. Re-check EVERY assertion.
3. Recalculate EVERY expected value.
4. Preserve all correct tests.
5. Correct all incorrect expectations you can identify.

============================================================
VALID INPUT DOMAIN
============================================================

Do not invent behavior for inputs outside the valid domain.

If a function is intended for a NON-EMPTY list and the implementation
does not define empty-list behavior, remove any test that invents an
empty-list exception.

Do NOT invent exceptions.

============================================================
EXPECTED VALUE ORACLES
============================================================

When a simple independent Python expression safely represents the
expected result, use it instead of manually guessing arithmetic.

Examples:

Range:
expected = max(numbers) - min(numbers)

Sum:
expected = sum(numbers)

Count:
expected = len([...])

String reversal:
expected = value[::-1]

Do NOT use the function under test to calculate its own expected value.

============================================================
TEST VS IMPLEMENTATION FAILURE
============================================================

A failure can mean:

1. The test is wrong.

OR

2. The implementation is genuinely wrong.

Do NOT blindly change tests until they pass.

If the test expectation is invalid, fix or remove it.

If the implementation genuinely violates a valid test, preserve the
test.

============================================================
STRICT RULES
============================================================

- Return the COMPLETE test file.
- Preserve required imports.
- Preserve valid tests.
- Generate 1 to 5 test functions.
- Every test function must start with test_.
- Prefer one logical case per test.
- Use deterministic inputs.
- Do not use Hypothesis.
- Do not use random inputs.
- Do not use property-based testing.
- Do not mock the implementation.
- Do not redefine source functions.
- Do not reproduce source implementation.
- Do not invent requirements.
- Do not invent exceptions.

============================================================
OUTPUT
============================================================

Return ONLY the COMPLETE executable pytest file.

NO explanations.
NO Markdown.
NO code fences.
"""

        response = llm1.invoke(
            correction_prompt
        )

        corrected_test_code = clean_test_code(
            response.content
        )

        # ========================================================
        # RESTORE IMPORTS
        # ========================================================

        corrected_test_code = (
            preserve_original_imports(
                current_test_code,
                corrected_test_code
            )
        )

        # ========================================================
        # VALIDATE REPAIRED TESTS
        # ========================================================

        valid_tests, validation_message = (
            validate_test_code(
                corrected_test_code
            )
        )

        if not valid_tests:

            print(
                "\n❌ Repaired test file is invalid:"
            )

            print(
                validation_message
            )

            return {
                "test_result": validation_message,
                "test_passed": False
            }

        # ========================================================
        # SHOW REPAIRED TESTS
        # ========================================================

        print(
            "\n========== REPAIRED TESTS =========="
        )

        print(
            corrected_test_code
        )

        print(
            "===================================="
        )

        # ========================================================
        # RUN REPAIRED TESTS
        # ========================================================

        return_code, corrected_test_output = (
            run_tests(
                generated_code,
                corrected_test_code
            )
        )

        print(
            "\n========== REPAIRED TEST RESULT =========="
        )

        print(
            corrected_test_output
        )

        print(
            "=========================================="
        )

        # ========================================================
        # REPAIR SUCCESS
        # ========================================================

        if return_code == 0:

            print(
                "✅ Repaired generated tests passed."
            )

            return {
                "test_result": corrected_test_output,
                "test_passed": True
            }

        # ========================================================
        # NEXT REPAIR ATTEMPT USES LATEST STATE
        # ========================================================

        current_test_code = (
            corrected_test_code
        )

        current_test_output = (
            corrected_test_output
        )

    # ============================================================
    # ALL REPAIR ATTEMPTS FAILED
    # ============================================================

    print(
        "\n❌ Tests still failed after "
        f"{max_repair_attempts} repair attempts."
    )

    return {
        "test_result": current_test_output,
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
    # Fetch remote branch
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
    # Stage generated file
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
    # Check whether there is actually anything to commit
    # --------------------------------------------------------

    diff_result = subprocess.run(
        [
            "git",
            "-C",
            repo_path,
            "diff",
            "--cached",
            "--quiet"
        ],
        check=False
    )

    # --------------------------------------------------------
    # Commit only if changes exist
    # --------------------------------------------------------

    if diff_result.returncode == 0:

        print(
            "\nℹ️ No new changes to commit."
        )

        print(
            "The generated code is already "
            "present on this branch."
        )

    elif diff_result.returncode == 1:

        print("\n💾 Creating commit...")

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

        print(
            commit_result.stdout
        )

        if commit_result.returncode != 0:

            print(
                commit_result.stderr
            )

            raise RuntimeError(
                "Git commit failed.\n"
                f"{commit_result.stdout}\n"
                f"{commit_result.stderr}"
            )

        print(
            "✅ Git commit created successfully."
        )

    else:

        raise RuntimeError(
            "Unable to determine whether "
            "there are staged changes."
        )

    # --------------------------------------------------------
    # Push branch to GitLab
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
        "\n✅ Generated code is available "
        "on the GitLab branch."
    )

    return {
        "generated_code": generated_code
    }

# ============================================================
# CREATE MERGE REQUEST
# ============================================================

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
        status="approved"
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
