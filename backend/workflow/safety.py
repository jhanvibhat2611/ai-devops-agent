"""Prototype checks, NOT a container/VM sandbox."""
import ast
import os
import pathlib
import subprocess
import sys
import tempfile
import threading

SAFE_IMPORTS = {"math", "statistics", "collections", "itertools", "functools", "re",
                "string", "decimal", "fractions", "typing", "dataclasses", "bisect", "heapq"}


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
    allowed = SAFE_IMPORTS | ({"pytest", "generated_feature"} if tests else set())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            if any(m.split(".")[0] not in allowed for m in modules):
                raise ValueError("Execution pre-check: import outside the prototype allowlist.")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("Execution pre-check: introspection is not allowed.")
        if isinstance(node, ast.Name) and (node.id.startswith("__") or node.id in {"open", "exec", "eval", "compile", "__import__", "globals", "locals", "getattr", "setattr", "input", "breakpoint"}):
            raise ValueError("Execution pre-check: unsafe builtin.")
    return tree


def validate_tests(source, code):
    source_tree = precheck(source)
    tree = precheck(code, tests=True)
    functions = {n.name for n in ast.walk(source_tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    tests = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
    if not 1 <= len(tests) <= 5:
        raise ValueError("Expected 1–5 top-level test functions.")
    imported = set()
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "generated_feature":
            for alias in node.names:
                if alias.name not in functions:
                    raise ValueError("Import must refer to a real source function.")
                imported.add(alias.asname or alias.name)
        if isinstance(node, ast.Import):
            modules.update(a.asname or a.name for a in node.names if a.name == "generated_feature")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("test_"):
            raise ValueError("Do not redefine or copy implementation functions.")
        if isinstance(node, (ast.For, ast.While, ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            raise ValueError("Use small fixed test cases, without copied algorithms or loops.")
        if isinstance(node, ast.Attribute) and node.attr in {"patch", "mock", "skip", "skipif", "xfail"}:
            raise ValueError("Mocking and skipped tests are not allowed.")
    if not imported and not modules:
        raise ValueError("Import the implementation from generated_feature.")
    def source_call(node):
        return isinstance(node, ast.Call) and ((isinstance(node.func, ast.Name) and node.func.id in imported) or
            (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id in modules))
    for test in tests:
        assertions = [n for n in ast.walk(test) if isinstance(n, ast.Assert)]
        if not assertions or not any(source_call(n) for n in ast.walk(test)):
            raise ValueError("Each test must call the implementation and assert behavior.")
        tainted = set()
        for node in ast.walk(test):
            if isinstance(node, ast.Assign) and any(source_call(n) or (isinstance(n, ast.Name) and n.id in tainted) for n in ast.walk(node.value)):
                tainted.update(n.id for target in node.targets for n in ast.walk(target) if isinstance(n, ast.Name))
            if isinstance(node, ast.Compare):
                operands = [node.left] + node.comparators
                dependent = [any(source_call(n) or (isinstance(n, ast.Name) and n.id in tainted) for n in ast.walk(v)) for v in operands]
                if sum(dependent) > 1:
                    raise ValueError("Self-oracle: derive expected values independently.")
    return tree


def child_environment(temp_dir):
    env = {k: os.environ[k] for k in ("SYSTEMROOT", "WINDIR", "PATH", "COMSPEC") if k in os.environ}
    env.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONHASHSEED="0", TEMP=temp_dir, TMP=temp_dir, HOME=temp_dir)
    return env


def run_tests(source, tests, timeout=10, output_limit=16000):
    try:
        validate_tests(source, tests)
        with tempfile.TemporaryDirectory(prefix="agent_tests_") as directory:
            pathlib.Path(directory, "generated_feature.py").write_text(source, encoding="utf-8")
            pathlib.Path(directory, "test_generated_feature.py").write_text(tests, encoding="utf-8")
            process = subprocess.Popen([sys.executable, "-m", "pytest", "-q", "-s", "--tb=short", "-p", "no:cacheprovider"],
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
            return code, report
    except (ValueError, SyntaxError, OSError) as error:
        return 2, str(error)
