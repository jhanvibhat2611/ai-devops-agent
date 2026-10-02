"""Specification-first tests with at most two structural repairs."""
import ast
import json
import re
from workflow.safety import precheck, validate_tests, run_tests
from workflow.test_errors import (
    UnsupportedCodeError, UnsafeCodeError, InvalidSourceError,
    ModelInvocationError, MalformedOutputError, InvalidTestsError,
    AmbiguousSpecificationError, PytestExecutionError, PytestTimeoutError,
    ImplementationFailure, failure_result, log_test_rejection,
)


def clean(code):
    if isinstance(code, list):
        if not all(isinstance(block, dict) and block.get("type") == "text"
                   and isinstance(block.get("text"), str) for block in code):
            raise MalformedOutputError()
        code = "\n".join(block["text"] for block in code)
    if not isinstance(code, str) or not code.strip():
        raise MalformedOutputError()
    match = re.search(r"```(?:python|py|json)?\s*(.*?)```", code, re.S)
    code = (match.group(1) if match else code).strip()
    if code.startswith("{"):
        try:
            data = json.loads(code)
        except ValueError as error:
            raise MalformedOutputError() from error
        if data.get("status") == "clarification_required":
            raise AmbiguousSpecificationError()
        if data.get("status") != "tests" or not isinstance(data.get("code"), str):
            raise MalformedOutputError()
        code = data["code"].strip()
    try:
        ast.parse(code)
    except SyntaxError as error:
        raise MalformedOutputError() from error
    if not code:
        raise MalformedOutputError()
    return code


def invoke_model(llm, prompt):
    try:
        response = llm.invoke(prompt)
    except Exception as error:
        raise ModelInvocationError() from error
    # Output shape failures are distinct from failures thrown by the model call.
    return getattr(response, "content", None)


def preserve_required_imports(previous, code):
    """Keep needed imports, never reintroduce rejected/obsolete imports on repair."""
    try:
        old, current = ast.parse(previous), ast.parse(code)
    except SyntaxError:
        return code
    used = {n.id for n in ast.walk(current) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    bound = {a.asname or a.name.split(".")[0] for n in ast.walk(current)
             if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
    needed = []
    for node in old.body:
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        names = {a.asname or a.name.split(".")[0] for a in node.names}
        if not names & (used - bound):
            continue
        text = ast.unparse(node)
        try:
            precheck(text, tests=True)
        except (UnsupportedCodeError, UnsafeCodeError, InvalidTestsError):
            continue
        needed.append(text)
    return "\n".join([*needed, code])


def test_implementation(state, llm):
    stage = "specification"
    try:
        source = state.get("generated_code", "")
        specification = state.get("user_request", "")
        if not isinstance(specification, str) or not specification.strip():
            raise AmbiguousSpecificationError()
        stage = "source_precheck"
        if not isinstance(source, str) or not source.strip():
            raise InvalidSourceError()
        try:
            precheck(source)
        except SyntaxError as error:
            raise InvalidSourceError() from error
        import_names = ", ".join(node.name for node in ast.parse(source).body
                                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))
        context = f"""Source priority: ORIGINAL REQUEST is the behavioral specification;
analysis clarifies it; source is only the implementation to verify, never the oracle.
ORIGINAL REQUEST: {specification}
ANALYSIS: {state.get('analysis', '')}
IMPLEMENTATION (generated_feature.py):
{source}
Write 1-5 small deterministic pytest tests with independently derived expected values.
MANDATORY TEST MODULE CONTRACT:
The implementation already exists in generated_feature.py, a separate file.
Available implementation function names: {import_names}
Begin with imports from generated_feature using these actual names.
Never include the implementation in the test file, even as a convenience/example.
Only define test_ functions; do not redefine any imported function.
Import actual functions from generated_feature. pytest is an allowed test dependency.
One behavior per test. Fixed inputs. The runner invokes pytest; omit script entrypoints.
No copying/redefining source, loops, random, Hypothesis, mocks, skip or xfail.
No invented validation, exceptions, or out-of-domain inputs. Preserve the specification
even if the implementation is wrong. Return only the complete Python test file.
Supported execution: pure Python functions and local PyJWT signing/verification,
datetime and hashing. No HTTP servers, network calls, filesystem or process access.
Use fixed test-only credentials and keys, never application environment secrets.
JWT tests must verify independently specified claims and authentication behavior,
not derive the expected token by calling the implementation again. Do not expect
an exact token unless the specification defines all claims, timestamps and signing.
If the ORIGINAL REQUEST plus ANALYSIS leaves behavior ambiguous, do not infer it
from the implementation. Return {{"status":"clarification_required"}} instead.
"""
        prompt, previous = context, ""
        for attempt in range(3):
            stage = "model_invocation"
            content = invoke_model(llm, prompt)
            try:
                stage = "model_output"
                try:
                    code = clean(content)
                except AmbiguousSpecificationError:
                    stage = "specification"
                    raise
                code = preserve_required_imports(previous, code)
                stage = "test_validation"
                validate_tests(source, code)
                break
            except (MalformedOutputError, InvalidTestsError) as error:
                if isinstance(error, InvalidTestsError):
                    log_test_rejection(code, error, attempt + 1)
                if attempt == 2:
                    raise
                previous = code if stage == "test_validation" else ""
                prompt = context + f"\nRepair only format/structure: {error.code}: {error.safe_message}\nPrevious tests:\n{previous}"
        stage = "pytest_execution"
        execution = run_tests(source, code, detailed=True)
        if execution.return_code == 124:
            raise PytestTimeoutError()
        if execution.return_code != 0:
            if execution.failure_category == "implementation_failure":
                stage = "implementation_verification"
                raise ImplementationFailure()
            raise PytestExecutionError()
        # Preserve a structurally valid failure instead of weakening assertions.
        return {"test_passed": True, "test_result": f"Pytest passed ({execution.test_count} tests).", "test_failure": None}
    except Exception as error:
        return failure_result(stage, error)
