from types import SimpleNamespace
import pytest
from workflow.safety import run_tests, validate_tests, child_environment, target_path
from workflow.test_agent import test_implementation as generate_tests


@pytest.mark.parametrize("spec,correct,wrong,assertion", [
    ("Multiply a number by 3", "return x * 3", "return x * 2", "f(4) == 12"),
    ("Sum a list", "return sum(x)", "return len(x)", "f([2, 5, -1]) == 6"),
    ("Check palindrome", "return x == x[::-1]", "return True", "f('abc') is False"),
    ("Maximum of a non-empty list", "return max(x)", "return min(x)", "f([-3, 2, 9]) == 9"),
])
def test_independent_oracles_fail_wrong_implementations(spec, correct, wrong, assertion):
    tests = f"from generated_feature import f\ndef test_behavior():\n    assert {assertion}\n"
    assert run_tests(f"def f(x):\n    {correct}\n", tests)[0] == 0
    assert run_tests(f"def f(x):\n    {wrong}\n", tests)[0] == 1


def test_timeout_is_real_and_output_bounded():
    code, output = run_tests("def f(x):\n    while True:\n        print('bounded output')", "from generated_feature import f\ndef test_value():\n    assert f(1) == 3", timeout=0.8, output_limit=400)
    assert code == 124
    assert "timeout" in output
    assert len(output) < 500


def test_child_has_no_secrets(monkeypatch):
    for key in ("JWT_SECRET_KEY", "GITLAB_TOKEN", "ENCRYPTION_KEY", "PYTHONPATH", "PYTEST_ADDOPTS", "AWS_SECRET_ACCESS_KEY"):
        monkeypatch.setenv(key, "secret")
        assert key not in child_environment("temporary")


@pytest.mark.parametrize("tests", [
    "def test_fake():\n    assert True",
    "from generated_feature import f\ndef test_self():\n    assert f(1) == f(1)",
    "from generated_feature import f\ndef test_self():\n    expected = f(1)\n    assert f(1) == expected",
    "import random\nfrom generated_feature import f\ndef test_value():\n    assert f(1) == 3",
    "from generated_feature import f\ndef f(x):\n    return x*3\ndef test_value():\n    assert f(1) == 3",
    "from generated_feature import invented\ndef test_value():\n    assert invented(1) == 3",
    "import pytest\nfrom generated_feature import f\n@pytest.mark.xfail\ndef test_value():\n    assert f(1) == 3",
])
def test_structural_rejections(tests):
    with pytest.raises(ValueError):
        validate_tests("def f(x): return x*3", tests)


def test_no_execution_before_precheck():
    code, output = run_tests("import os\ndef f(x): return os.system(x)", "from generated_feature import f\ndef test_value(): assert f(1) == 1")
    assert code == 2
    assert "pre-check" in output


def test_specification_is_in_generation_and_bounded_repair():
    prompts = []
    class LLM:
        def invoke(self, prompt):
            prompts.append(prompt)
            return SimpleNamespace(content="invalid syntax ?")
    result = generate_tests({"user_request": "Multiply by 3", "analysis": "Use integers", "generated_code": "def f(x): return x*2"}, LLM())
    assert not result["test_passed"] and result["test_result"]
    assert len(prompts) == 3
    assert all("Multiply by 3" in p and "Use integers" in p and "return x*2" in p for p in prompts)


def test_failure_never_repairs_expectation_to_match_wrong_code():
    calls = []
    class LLM:
        def invoke(self, prompt):
            calls.append(prompt)
            return SimpleNamespace(content="from generated_feature import f\ndef test_triple(): assert f(4) == 12")
    result = generate_tests({"user_request": "Multiply by 3", "analysis": "", "generated_code": "def f(x): return x*2"}, LLM())
    assert not result["test_passed"]
    assert len(calls) == 1


@pytest.mark.parametrize("path", ["../x.py", "/x.py", "C:\\x.py", "foo/../../x.py", ".git/config", "", "."])
def test_target_path_rejects_escape(path):
    with pytest.raises(ValueError):
        target_path(path)
