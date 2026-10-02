"""Specification-first tests with at most two structural repairs."""
import ast
import re
from workflow.safety import precheck, validate_tests, run_tests


def clean(code):
    match = re.search(r"```(?:python|py)?\s*(.*?)```", code, re.S)
    return (match.group(1) if match else code).strip()


def test_implementation(state, llm):
    source = state.get("generated_code", "")
    specification = state.get("user_request", "")
    if not source.strip() or not specification.strip():
        return {"test_passed": False, "test_result": "Source and original specification are required."}
    try:
        precheck(source)
        context = f"""Source priority: ORIGINAL REQUEST is the behavioral specification;
analysis clarifies it; source is only the implementation to verify, never the oracle.
ORIGINAL REQUEST: {specification}
ANALYSIS: {state.get('analysis', '')}
IMPLEMENTATION (generated_feature.py):
{source}
Write 1-5 small deterministic pytest tests with independently derived expected values.
Import actual functions from generated_feature. One behavior per test. Fixed inputs.
No copying/redefining source, loops, random, Hypothesis, mocks, skip or xfail.
No invented validation, exceptions, or out-of-domain inputs. Preserve the specification
even if the implementation is wrong. Return only the complete Python test file.
"""
        code = clean(llm.invoke(context).content)
        for attempt in range(3):
            try:
                validate_tests(source, code)
                break
            except (ValueError, SyntaxError) as error:
                if attempt == 2:
                    return {"test_passed": False, "test_result": str(error)}
                previous = code
                code = clean(llm.invoke(context + f"\nRepair structural error only: {error}\nPrevious tests:\n{code}").content)
                try:
                    imports = [ast.unparse(n) for n in ast.parse(previous).body if isinstance(n, (ast.Import, ast.ImportFrom))]
                    current = {ast.unparse(n) for n in ast.parse(code).body if isinstance(n, (ast.Import, ast.ImportFrom))}
                    code = "\n".join(i for i in imports if i not in current) + "\n" + code
                except SyntaxError:
                    pass
        status, output = run_tests(source, code)
        # Preserve a structurally valid failure instead of weakening assertions.
        return {"test_passed": status == 0, "test_result": output}
    except Exception as error:
        return {"test_passed": False, "test_result": f"Test generation failed ({type(error).__name__})."}
