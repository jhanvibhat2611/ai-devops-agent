"""Public test-agent failures and diagnostics that never serialize exception payloads.

Model/pytest exception messages can contain prompts, source, credentials or local
values. Only application-authored messages are released; tracebacks contain frame
locations, not source lines, locals, exception reprs, or chained exception text.
"""
import ast
import logging
from pathlib import Path
import traceback

logger = logging.getLogger("workflow.test_agent")


class TestAgentError(ValueError):
    category = "internal_test_agent_failure"
    code = "internal_error"
    safe_message = "The test agent encountered an internal error. Check the backend diagnostics."

    def __init__(self, detail=None):
        super().__init__(detail or self.safe_message)


class UnsupportedCodeError(TestAgentError):
    category = "unsupported_generated_code"
    code = "unsupported_dependency"
    safe_message = "Generated code needs a dependency outside the local test runner's supported profile. Use a suitable isolated runner; no code was executed."


class UnsafeCodeError(TestAgentError):
    category = "unsafe_generated_code"
    code = "unsafe_operation"
    safe_message = "The execution pre-check blocked filesystem, network, process access or unsafe introspection. No code was executed."


class InvalidSourceError(TestAgentError):
    category = "unsupported_generated_code"
    code = "invalid_python_source"
    safe_message = "Generated implementation is not valid Python. Regenerate the implementation before testing."


class ModelInvocationError(TestAgentError):
    category = "model_invocation_failure"
    code = "model_call_failed"
    safe_message = "The test model could not complete the request. Check its configuration and availability, then retry."


class MalformedOutputError(TestAgentError):
    category = "malformed_model_output"
    code = "invalid_model_response"
    safe_message = "The test model did not return a complete executable Python test file or a valid clarification response."


class InvalidTestsError(TestAgentError):
    category = "structurally_invalid_tests"
    code = "invalid_test_contract"
    safe_message = "Generated tests violate the test contract (imports, assertions, test count or independent expected values). No code was executed."


# Only these application-authored messages may reach logs, prompts or responses.
TEST_RULES = {
    "missing_generated_feature_import": "Import the implementation from generated_feature.",
    "unsafe_test_import": "Remove imports exposing filesystem, network or process capabilities.",
    "unsafe_test_operation": "Remove unsafe operations or introspection from the tests.",
    "unsafe_test_name": "Remove forbidden builtin or dunder names; only a module-level __name__ main guard is allowed.",
    "unsafe_test_attribute": "Remove dunder attribute access from the tests.",
    "unsupported_test_dependency": "Use only supported test dependencies, including pytest and generated_feature.",
    "no_test_functions": "Define at least one top-level test_ function.",
    "too_many_tests": "Define no more than five top-level test functions.",
    "missing_assertion": "Each test must assert independently specified behavior.",
    "missing_implementation_call": "Each test must call the imported implementation.",
    "self_oracle": "Derive expected values independently; never call the implementation to compute them.",
    "source_reimplementation": "Delete copied implementation definitions entirely. Import the actual function using from generated_feature import function_name; retain only test_ functions.",
    "unknown_implementation_function": "Import only functions present in generated_feature.",
    "unsupported_test_control_flow": "Use fixed test cases without loops, lambdas or comprehensions.",
    "mocked_or_skipped_test": "Do not mock the implementation or skip expected behavior.",
}


class TestValidationError(InvalidTestsError):
    def __init__(self, rule, node=None):
        # Reject arbitrary text rather than letting model-controlled messages leak.
        self.code = rule if rule in TEST_RULES else "invalid_test_contract"
        self.safe_message = TEST_RULES.get(self.code, InvalidTestsError.safe_message)
        self.line = getattr(node, "lineno", None)
        self.node_type = type(node).__name__ if isinstance(node, ast.AST) else "none"
        name = getattr(node, "id", getattr(node, "attr", None))
        self.rejected_name = name if name in {"__name__", "__builtins__", "__import__", "__class__",
            "__dict__", "__globals__", "open", "exec", "eval", "compile", "globals", "locals",
            "getattr", "setattr", "input", "breakpoint"} else "<identifier redacted>"
        super().__init__()


def log_test_rejection(code, error, attempt):
    """Log test structure, never raw model text, literals, comments or identifiers."""
    symbols = {}
    visible = {"pytest", "generated_feature", "__name__", "__import__", "open", "exec",
               "eval", "compile", "globals", "locals", "getattr", "setattr", "input", "breakpoint"}
    def symbol(value):
        if value in visible:
            return value
        if value not in symbols:
            symbols[value] = "symbol_" + str(len(symbols) + 1)
        return symbols[value]
    class Redact(ast.NodeTransformer):
        def generic_visit(self, node):
            # All AST string fields include identifiers, attribute names, import
            # paths, argument names and type comments. No free-form text survives.
            for field, value in ast.iter_fields(node):
                if isinstance(value, str):
                    setattr(node, field, symbol(value))
                elif isinstance(value, list):
                    setattr(node, field, [symbol(v) if isinstance(v, str) else v for v in value])
            return super().generic_visit(node)
        def visit_Constant(self, node):
            return ast.copy_location(ast.Constant(value="<literal redacted>"), node)
    try:
        sanitized = ast.unparse(Redact().visit(ast.parse(code)))[:8000]
    except Exception:
        sanitized = "<test code unavailable for safe structural rendering>"
    logger.warning("UNIT TEST AGENT rejected tests attempt=%s rule=%s line=%s ast=%s rejected_name=%s sanitized_reason=%s\n"
                   "Generated test code (redacted structure; identifiers/literals/comments removed):\n%s",
                   attempt, error.code, getattr(error, "line", None), getattr(error, "node_type", "none"),
                   getattr(error, "rejected_name", "<identifier redacted>"), error.safe_message, sanitized)


class AmbiguousSpecificationError(TestAgentError):
    category = "ambiguous_specification"
    code = "clarification_required"
    safe_message = "The request and analysis do not define enough behavior to derive tests. Clarify the public interface, valid inputs, expected outputs and failure behavior; for JWT login also specify credential rules, token claims and lifetime."


class PytestExecutionError(TestAgentError):
    category = "pytest_execution_failure"
    code = "pytest_could_not_run"
    safe_message = "Pytest could not complete the tests. Check runner dependencies and generated test setup."


class PytestTimeoutError(PytestExecutionError):
    code = "pytest_timeout"
    safe_message = "Generated tests exceeded the execution time limit and were stopped."


class ImplementationFailure(TestAgentError):
    category = "implementation_failure"
    code = "behavioral_test_failed"
    safe_message = "The implementation failed a generated behavioral test. Check it against the original request; test expectations were preserved."


_INTERNAL_FILES = {str(Path(__file__).with_name(name).resolve()).replace("\\", "/").casefold(): name
                   for name in ("test_agent.py", "test_errors.py", "safety.py")}
_EXCEPTION_TYPES = {"ValueError", "TypeError", "AttributeError", "RuntimeError", "OSError",
    "FileNotFoundError", "PermissionError", "TimeoutError", "TimeoutExpired", "ConnectionError",
    "HTTPError", "HTTPStatusError", "ReadTimeout", "ConnectTimeout", "ConnectError",
    "TimeoutException", "ResponseError", "ValidationError", "JSONDecodeError", "SyntaxError",
    "ImportError", "ModuleNotFoundError", "NotImplementedError", "Exception"}


def _exception_type(error):
    name = type(error).__name__
    return name if name in _EXCEPTION_TYPES or type(error) in _KNOWN_ERRORS else "ExternalException"


_KNOWN_ERRORS = {TestAgentError, UnsupportedCodeError, UnsafeCodeError,
    InvalidSourceError, ModelInvocationError, MalformedOutputError, InvalidTestsError, TestValidationError,
    AmbiguousSpecificationError, PytestExecutionError, PytestTimeoutError, ImplementationFailure}


def failure_result(stage, error):
    """Log controlled text and frame-only traceback, return the public contract."""
    # Do not use str(error), logger.exception(), exc_info=True, or traceback.format_exc().
    # Their payloads can include secrets even when local-variable capture is disabled.
    known = type(error) in _KNOWN_ERRORS
    policy = error if known else TestAgentError
    frames = []
    seen = set()
    current = error
    while current is not None and id(current) not in seen and len(seen) < 8:
        seen.add(id(current))
        frames.append(f"Exception type: {_exception_type(current)}")
        for frame, lineno in traceback.walk_tb(current.__traceback__):
            code = frame.f_code
            filename = _INTERNAL_FILES.get(code.co_filename.replace("\\", "/").casefold())
            # External filenames/function names can also embed dynamic payloads.
            frames.append(f"  {filename}:{lineno} in {code.co_name}" if filename else f"  <external frame>:{lineno}")
        current = current.__cause__ or current.__context__
    logger.error("UNIT TEST AGENT failure stage=%s category=%s exception_type=%s sanitized_message=%s\n"
                 "Traceback (frame locations only; source, locals and raw exception text omitted):\n%s",
                 stage, policy.category, _exception_type(error), policy.safe_message, "\n".join(frames))
    return {"test_passed": False, "test_result": policy.safe_message,
            "test_failure": {"stage": stage, "error_category": policy.category,
                             "error_code": policy.code, "safe_message": policy.safe_message}}
