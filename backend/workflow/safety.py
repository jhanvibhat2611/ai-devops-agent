"""Prototype checks, NOT a container/VM sandbox."""
import ast
from dataclasses import dataclass
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
from workflow.test_errors import (UnsupportedCodeError, UnsafeCodeError,
                                  TestValidationError, PytestExecutionError)

SAFE_IMPORTS = {"math", "statistics", "collections", "itertools", "functools", "re",
                "string", "decimal", "fractions", "typing", "dataclasses", "bisect", "heapq",
                "datetime", "hashlib", "hmac", "base64", "json"}
# PyJWT is already a pinned application dependency. Permit its local signing and
# verification API, not PyJWKClient (HTTP), internal modules, or algorithm registration.
JWT_API = {"encode", "decode", "decode_complete", "get_unverified_header", "exceptions",
           "InvalidTokenError", "DecodeError", "ExpiredSignatureError", "InvalidSignatureError",
           "InvalidAlgorithmError", "InvalidAudienceError", "InvalidIssuerError", "InvalidKeyError",
           "MissingRequiredClaimError", "ImmatureSignatureError", "InvalidIssuedAtError"}
JWT_MODULES = {"jwt", "jwt.exceptions"}
UNSAFE_IMPORTS = {"sys", "subprocess", "socket", "requests", "httpx", "urllib", "http",
                  "pathlib", "shutil", "tempfile", "sqlite3", "ctypes", "importlib", "pickle"}


def target_path(value):
    path = pathlib.PurePosixPath(value.replace("\\", "/"))
    if (not value or path.is_absolute() or ".." in path.parts or ":" in value
            or any(part.lower() == ".git" or part.rstrip(" .") != part for part in path.parts)
            or any(ord(char) < 32 for char in value)):
        raise ValueError("Generated target must be a relative file inside the repository.")
    if str(path) == ".":
        raise ValueError("Generated target must name a file.")
    return str(path)


def precheck(code, tests=False):
    tree = ast.parse(code)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    def reject(error_type, rule, node):
        if tests:
            raise TestValidationError(rule, node)
        raise error_type()
    def test_main_guard(node):
        # Pytest imports test modules: this canonical script guard stays inactive.
        # Do not permit other dunder names, arbitrary __name__ reads or assignment.
        compare = parents.get(node)
        guard = parents.get(compare)
        return (tests and node.id == "__name__" and isinstance(node.ctx, ast.Load)
                and isinstance(compare, ast.Compare) and compare.left is node
                and len(compare.ops) == 1 and isinstance(compare.ops[0], ast.Eq)
                and len(compare.comparators) == 1
                and isinstance(compare.comparators[0], ast.Constant)
                and compare.comparators[0].value == "__main__"
                and isinstance(guard, ast.If) and guard.test is compare
                and guard in tree.body and not guard.orelse)
    allowed = SAFE_IMPORTS | JWT_MODULES | {"os"} | ({"pytest", "generated_feature"} if tests else set())
    jwt_aliases = set()
    config_aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            if isinstance(node, ast.ImportFrom) and node.level:
                reject(UnsupportedCodeError, "unsupported_test_dependency", node)
            if any(m.split(".")[0] in UNSAFE_IMPORTS for m in modules):
                reject(UnsafeCodeError, "unsafe_test_import", node)
            if any(m.startswith("os.") for m in modules):
                reject(UnsafeCodeError, "unsafe_test_import", node)
            if any(m not in allowed and (m.startswith("jwt.") or m.split(".")[0] not in allowed) for m in modules):
                reject(UnsupportedCodeError, "unsupported_test_dependency", node)
            if isinstance(node, ast.Import):
                jwt_aliases.update(a.asname or "jwt" for a in node.names if a.name in JWT_MODULES)
                config_aliases.update((a.asname or "os", "module") for a in node.names if a.name == "os")
            elif node.module == "os":
                if any(a.name not in {"getenv", "environ"} for a in node.names):
                    reject(UnsafeCodeError, "unsafe_test_import", node)
                config_aliases.update((a.asname or a.name, a.name) for a in node.names)
            elif node.module in JWT_MODULES and any(a.name not in JWT_API for a in node.names):
                reject(UnsafeCodeError, "unsafe_test_import", node)
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            reject(UnsafeCodeError, "unsafe_test_attribute", node)
        if isinstance(node, ast.Name) and (node.id.startswith("__") or node.id in {"open", "exec", "eval", "compile", "__import__", "globals", "locals", "getattr", "setattr", "input", "breakpoint"}):
            if not test_main_guard(node):
                reject(UnsafeCodeError, "unsafe_test_name", node)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in config_aliases:
            # Permit only direct calls to getenv or environ.get. Module/mapping
            # escape, mutation, indexing and indirect attribute access stay blocked.
            if not isinstance(node.ctx, ast.Load):
                reject(UnsafeCodeError, "unsafe_test_operation", node)
            kind = config_aliases[node.id]
            access = node
            if kind == "module":
                access = parents.get(access)
                if not isinstance(access, ast.Attribute) or access.attr not in {"getenv", "environ"}:
                    reject(UnsafeCodeError, "unsafe_test_operation", node)
                kind = access.attr
            if kind == "environ":
                access = parents.get(access)
                if not isinstance(access, ast.Attribute) or access.attr != "get":
                    reject(UnsafeCodeError, "unsafe_test_operation", node)
            call = parents.get(access)
            if not isinstance(call, ast.Call) or call.func is not access:
                reject(UnsafeCodeError, "unsafe_test_operation", node)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in jwt_aliases:
            parent = parents.get(node)
            if not isinstance(parent, ast.Attribute) or parent.value is not node or parent.attr not in JWT_API:
                reject(UnsafeCodeError, "unsafe_test_operation", node)
    return tree


def validate_tests(source, code):
    source_tree = precheck(source)
    tree = precheck(code, tests=True)
    functions = {n.name for n in ast.walk(source_tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    tests = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
    if not tests:
        raise TestValidationError("no_test_functions")
    if len(tests) > 5:
        raise TestValidationError("too_many_tests")
    imported = set()
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "generated_feature":
            for alias in node.names:
                if alias.name not in functions:
                    raise TestValidationError("unknown_implementation_function", node)
                imported.add(alias.asname or alias.name)
        if isinstance(node, ast.Import):
            modules.update(a.asname or a.name for a in node.names if a.name == "generated_feature")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("test_"):
            raise TestValidationError("source_reimplementation", node)
        if isinstance(node, (ast.For, ast.While, ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            raise TestValidationError("unsupported_test_control_flow", node)
        if isinstance(node, ast.Attribute) and node.attr in {"patch", "mock", "skip", "skipif", "xfail"}:
            raise TestValidationError("mocked_or_skipped_test", node)
    if not imported and not modules:
        raise TestValidationError("missing_generated_feature_import")
    def source_call(node):
        return isinstance(node, ast.Call) and ((isinstance(node.func, ast.Name) and node.func.id in imported) or
            (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id in modules))
    for test in tests:
        assertions = [n for n in ast.walk(test) if isinstance(n, ast.Assert)]
        if not assertions:
            raise TestValidationError("missing_assertion", test)
        if not any(source_call(n) for n in ast.walk(test)):
            raise TestValidationError("missing_implementation_call", test)
        tainted = set()
        for node in ast.walk(test):
            if isinstance(node, ast.Assign) and any(source_call(n) or (isinstance(n, ast.Name) and n.id in tainted) for n in ast.walk(node.value)):
                tainted.update(n.id for target in node.targets for n in ast.walk(target) if isinstance(n, ast.Name))
            if isinstance(node, ast.Compare):
                operands = [node.left] + node.comparators
                dependent = [any(source_call(n) or (isinstance(n, ast.Name) and n.id in tainted) for n in ast.walk(v)) for v in operands]
                if sum(dependent) > 1:
                    raise TestValidationError("self_oracle", node)
    return tree


def child_environment(temp_dir):
    env = {k: os.environ[k] for k in ("SYSTEMROOT", "WINDIR", "PATH", "COMSPEC") if k in os.environ}
    env.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONHASHSEED="0", TEMP=temp_dir, TMP=temp_dir, HOME=temp_dir)
    return env


@dataclass
class TestExecution:
    return_code: int
    output: str
    failure_category: str | None
    test_count: int = 0


# This is trusted runner code, not model output. Record no exception messages,
# source text, captured stdout or local variables in its machine-readable report.
_REPORT_PLUGIN = '''
import json
from pathlib import Path
import pytest

failures = []
passed = 0

@pytest.hookimpl(tryfirst=True)
def pytest_runtest_makereport(item, call):
    global passed
    if call.when == "call" and call.excinfo is None:
        passed += 1
    if call.excinfo is not None:
        origin = call.excinfo.traceback[-1].path.name
        behavioral = call.when == "call" and (
            call.excinfo.errisinstance(AssertionError) or origin == "generated_feature.py")
        failures.append("implementation_failure" if behavioral else "pytest_execution_failure")

def pytest_sessionfinish(session, exitstatus):
    category = None
    if exitstatus or failures or passed != session.testscollected:
        category = "implementation_failure" if failures and set(failures) == {"implementation_failure"} else "pytest_execution_failure"
    Path("_agent_result.json").write_text(json.dumps({
        "failure_category": category, "test_count": session.testscollected,
        "passed_count": passed}), encoding="utf-8")
'''


def run_tests(source, tests, timeout=10, output_limit=16000, *, detailed=False):
    try:
        validate_tests(source, tests)
        with tempfile.TemporaryDirectory(prefix="agent_tests_") as directory:
            pathlib.Path(directory, "generated_feature.py").write_text(source, encoding="utf-8")
            pathlib.Path(directory, "test_generated_feature.py").write_text(tests, encoding="utf-8")
            pathlib.Path(directory, "_agent_report.py").write_text(_REPORT_PLUGIN, encoding="utf-8")
            process = subprocess.Popen([sys.executable, "-m", "pytest", "-q", "-s", "--tb=short", "-p", "no:cacheprovider", "-p", "_agent_report"],
                cwd=directory, env=child_environment(directory), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            output = bytearray()
            def drain():
                while chunk := process.stdout.read(4096):
                    output.extend(chunk[:max(0, output_limit - len(output))])
            reader = threading.Thread(target=drain, daemon=True)
            reader.start()
            try:
                code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                code = 124
            finally:
                reader.join()
                process.stdout.close()
            report = output.decode("utf-8", errors="replace")
            if code == 124:
                report += "\nHard pytest timeout exceeded."
            metadata = {}
            try:
                metadata = json.loads(pathlib.Path(directory, "_agent_result.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
            category = metadata.get("failure_category")
            if code and category not in {"implementation_failure", "pytest_execution_failure"}:
                category = "pytest_execution_failure"
            count = metadata.get("test_count", 0)
            if code == 0 and (not isinstance(count, int) or not 1 <= count <= 5
                              or metadata.get("passed_count") != count or category):
                code, category = 2, "pytest_execution_failure"
            result = TestExecution(code, report, category, count)
            return result if detailed else (code, report)
    except (ValueError, SyntaxError, OSError) as error:
        if detailed:
            raise PytestExecutionError() from error
        return 2, str(error)
